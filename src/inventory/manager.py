"""Gestor de inventario, sincronización de stock y generación de reportes."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import openpyxl

from ..consolidator import ItemConsolidado
from ..parsers.remito_parser import ResultadoRemito
from ..products import ProductStore
from ..stock.models import RegistroDescuento, ReporteStock
from ..stock.physical_inventory import (
    comparar_stock_fisico_dict,
    generar_documento_comparativo_excel,
)
from ..stock.replenishment import generar_pedido_sugerido_fabrica_excel
from .catalog_loader import CatalogLoaderService
from .discount_engine import DiscountEngineService
from .template_sync import ResultadoSincronizacionExcel, TemplateSyncService


class StockManager:
    """Orquestador unificado del inventario SQLite, plantilla Excel y reportes por composición."""

    _excel_locks: dict[str, threading.RLock] = {}
    _excel_timers: dict[str, threading.Timer] = {}
    _meta_lock = threading.Lock()

    @classmethod
    def _obtener_lock_excel(cls, ruta: Path) -> threading.RLock:
        key = str(ruta.resolve()) if ruta.exists() else str(ruta)
        with cls._meta_lock:
            lock = cls._excel_locks.get(key)
            if lock is None:
                lock = threading.RLock()
                cls._excel_locks[key] = lock
            return lock

    def programar_sincronizacion_excel(self, delay_s: float = 0.6) -> None:
        """Programa la sincronización de Productos.xlsx en segundo plano (con debounce) sin bloquear la UI."""
        if not getattr(self, "ruta_excel_base", None) or not self.ruta_excel_base.exists():
            return
        key = str(self.ruta_excel_base.resolve()) if self.ruta_excel_base.exists() else str(self.ruta_excel_base)
        ruta_excel = self.ruta_excel_base
        nombre_hoja = self.nombre_hoja
        ruta_db = self.ruta_base_datos

        def _ejecutar_bg() -> None:
            with self._meta_lock:
                self._excel_timers.pop(key, None)
            try:
                with self._obtener_lock_excel(ruta_excel):
                    sm_bg = StockManager(ruta_excel, nombre_hoja=nombre_hoja, ruta_base_datos=ruta_db)
                    sm_bg.sincronizar_catalogo_completo_excel()
            except Exception as exc_bg:
                print(f"[AVISO] Sincronización diferida de Excel: {exc_bg}")

        with self._meta_lock:
            timer_previo = self._excel_timers.pop(key, None)
            if timer_previo is not None:
                timer_previo.cancel()
            nuevo_timer = threading.Timer(delay_s, _ejecutar_bg)
            nuevo_timer.daemon = True
            self._excel_timers[key] = nuevo_timer
            nuevo_timer.start()

    def __init__(
        self,
        ruta_excel_base: str | Path | None = None,
        nombre_hoja: str = "Stock",
        ruta_base_datos: str | Path | None = None,
    ):
        if ruta_excel_base is not None:
            self.ruta_excel_base = Path(ruta_excel_base)
        else:
            from ..paths import get_descuentos_dir
            self.ruta_excel_base = get_descuentos_dir() / "Productos.xlsx"

        self.nombre_hoja = nombre_hoja
        if ruta_base_datos is not None:
            self.ruta_base_datos = Path(ruta_base_datos)
        else:
            parent_name = self.ruta_excel_base.parent.name.casefold()
            carpeta_base_datos = (
                self.ruta_excel_base.parent.parent
                if parent_name in ("descuentos", "descuentos_qa")
                else self.ruta_excel_base.parent
            )
            from ..core.environment import is_qa_environment
            dir_data = "data_qa" if is_qa_environment() or parent_name == "descuentos_qa" else "data"
            candidato_db = carpeta_base_datos / dir_data / "productos.sqlite3"
            if not candidato_db.exists() and (carpeta_base_datos / "data" / "productos.sqlite3").exists():
                candidato_db = carpeta_base_datos / "data" / "productos.sqlite3"
            self.ruta_base_datos = candidato_db
        self.product_store = ProductStore(self.ruta_base_datos)
        self.productos_base: List[Tuple[int, str, str, int]] = []
        self.filas_catalogo: List[Tuple[int, str, str, int]] = []
        self.catalogo: Dict[str, Tuple[int, str, int]] = {}
        self._filas_por_codigo: Dict[str, List[int]] = {}
        self._col_codigo = 1
        self._col_nombre = 2
        self._col_stock = 3
        self._col_stock_inicial: Optional[int] = None
        self._col_descuento: Optional[int] = None
        self._col_stock_final: Optional[int] = None
        self._fila_inicio_datos = 3
        self.catalog_loader = CatalogLoaderService(self)
        self.template_sync = TemplateSyncService(self)
        self.discount_engine = DiscountEngineService(self)
        self._cargar_catalogo()

    def buscar_producto_por_codigo_o_barras(self, query: str) -> Optional[sqlite3.Row]:
        """Busca un producto por su código interno (SKU) o por su código de barras."""
        return self.product_store.find_product_by_code_or_barcode(query)

    def asignar_codigo_barras(self, codigo: str, cod_barras: str) -> None:
        """Asocia o actualiza el código de barras de un producto."""
        self.product_store.set_product_barcode(codigo, cod_barras)

    def obtener_analisis_reposicion(self, solo_criticos: bool = True) -> List:
        """Consulta la vista de la base de datos `v_analisis_reposicion`."""
        return self.product_store.get_replenishment_analysis(only_critical=solo_criticos)

    def generar_pedido_sugerido_fabrica(
        self,
        ruta_salida: Path | str | None = None,
        solo_criticos: bool = True,
    ) -> Path:
        """Genera un archivo Excel con el pedido sugerido a fábrica."""
        analisis = self.obtener_analisis_reposicion(solo_criticos=solo_criticos)
        return generar_pedido_sugerido_fabrica_excel(
            analisis=analisis,
            ruta_excel_base=self.ruta_excel_base,
            ruta_salida=ruta_salida,
        )

    def comparar_stock_fisico(self, conteo_fisico: Dict[str, int]) -> List[Dict]:
        """Compara un diccionario `{codigo: stock_fisico}` con el stock digital actual."""
        return comparar_stock_fisico_dict(self.catalogo, conteo_fisico)

    def procesar_stock_fisico(
        self,
        conteo_fisico: Dict[str, int],
        usuario: str = "operador",
        nombre_archivo: str = "StockFisico.xlsx",
        ruta_salida: Path | str | None = None,
    ) -> Tuple[Path, List[Dict]]:
        """Registra inventario físico en SQLite, genera comparativa Excel y notifica al admin."""
        comparativa = self.comparar_stock_fisico(conteo_fisico)
        ruta_doc = self.generar_documento_comparativo_stock_fisico(
            comparativa=comparativa,
            usuario=usuario,
            nombre_archivo_origen=nombre_archivo,
            ruta_salida=ruta_salida,
        )

        detalles_db = [
            (
                str(item["code"]),
                str(item["name"]),
                int(item["stock_digital"]),
                int(item["stock_fisico"]),
                int(item["diferencia"]),
                str(item["estado"]),
            )
            for item in comparativa
        ]
        self.product_store.record_physical_inventory(
            usuario=usuario,
            nombre_archivo=nombre_archivo,
            reporte_unificado=str(ruta_doc),
            detalles=detalles_db,
        )

        total_relevados = len(comparativa)
        total_coinciden = sum(1 for i in comparativa if i["diferencia"] == 0 and i["en_catalogo"])
        total_faltantes = sum(1 for i in comparativa if i["diferencia"] < 0 and i["en_catalogo"])
        total_sobrantes = sum(1 for i in comparativa if i["diferencia"] > 0 and i["en_catalogo"])
        total_diferencias = total_faltantes + total_sobrantes

        try:
            self.product_store.create_admin_notification(
                title=f"Inventario físico cargado por operario '{usuario}'",
                message=(
                    f"El operario '{usuario}' cargó un inventario físico desde '{nombre_archivo}' "
                    f"({total_relevados} productos relevados: {total_coinciden} coinciden, "
                    f"{total_faltantes} con faltante, {total_sobrantes} con sobrante). "
                    f"Documento unificado: {ruta_doc.name}."
                ),
                operator_username=usuario,
                notification_type="stock_fisico",
                details=f"Archivo: {ruta_doc.name} | Relevados: {total_relevados} | Diferencias: {total_diferencias}",
            )
        except Exception as notif_err:
            print(f"[AVISO] No se pudo crear notificación de stock físico: {notif_err}")

        return ruta_doc, comparativa

    def generar_documento_comparativo_stock_fisico(
        self,
        comparativa: List[Dict],
        usuario: str = "operador",
        nombre_archivo_origen: str = "",
        ruta_salida: Path | str | None = None,
    ) -> Path:
        """Genera un archivo Excel unificado con la comparativa de stock físico vs digital."""
        return generar_documento_comparativo_excel(
            comparativa=comparativa,
            ruta_excel_base=self.ruta_excel_base,
            product_store=self.product_store,
            usuario=usuario,
            nombre_archivo_origen=nombre_archivo_origen,
            ruta_salida=ruta_salida,
        )

    def obtener_ultima_comparativa_fisica(self):
        return self.product_store.get_latest_physical_inventory()

    def listar_inventarios_fisicos(self, limit: int = 20):
        return self.product_store.list_physical_inventories(limit=limit)

    def obtener_detalle_inventario_fisico(self, inventario_id: int):
        return self.product_store.get_physical_inventory_details(inventario_id)

    # Delegación explícita a servicios de carga, sincronización y descuentos

    @staticmethod
    def _normalizar_encabezado(valor) -> str:
        return CatalogLoaderService._normalizar_encabezado(valor)

    def _detectar_esquema(self, sheet) -> None:
        self.catalog_loader._detectar_esquema(sheet)

    def _leer_stock(self, sheet, fila: int) -> int:
        return self.catalog_loader._leer_stock(sheet, fila)

    def _asegurar_esquema(self) -> None:
        self.catalog_loader._asegurar_esquema()

    def _serializar_esquema_meta(self) -> dict[str, str]:
        return self.catalog_loader._serializar_esquema_meta()

    def _aplicar_esquema_meta(self, meta: dict[str, str]) -> None:
        self.catalog_loader._aplicar_esquema_meta(meta)

    def _cargar_desde_sqlite(
        self,
        meta_precargada: Optional[dict[str, str]] = None,
        filas_precargadas: Optional[list[sqlite3.Row]] = None,
    ) -> None:
        self.catalog_loader._cargar_desde_sqlite(meta_precargada, filas_precargadas)

    def _cargar_catalogo(self, forzar_excel: bool = False) -> None:
        self.catalog_loader._cargar_catalogo(forzar_excel=forzar_excel)

    def listar_productos(self) -> List[sqlite3.Row]:
        return self.catalog_loader.listar_productos()

    def _actualizar_stocks_en_memoria(self, stocks: Dict[str, int]) -> None:
        self.catalog_loader._actualizar_stocks_en_memoria(stocks)

    def _escribir_stock_en_celdas(self, hoja, fila: int, stock: int) -> None:
        self.template_sync._escribir_stock_en_celdas(hoja, fila, stock)

    def _abrir_libro_editable(self) -> tuple[openpyxl.Workbook, object]:
        return self.template_sync._abrir_libro_editable()

    def _restaurar_desde_bytes(self, contenido_original: bytes) -> None:
        self.template_sync._restaurar_desde_bytes(contenido_original)

    def actualizar_producto(
        self,
        codigo_actual: str,
        codigo_nuevo: str,
        nombre: str,
        stock: int,
        stock_minimo: Optional[int] = None,
        stock_maximo: Optional[int] = None,
        cod_barras: Optional[str] = None,
    ) -> None:
        self.template_sync.actualizar_producto(
            codigo_actual=codigo_actual,
            codigo_nuevo=codigo_nuevo,
            nombre=nombre,
            stock=stock,
            stock_minimo=stock_minimo,
            stock_maximo=stock_maximo,
            cod_barras=cod_barras,
        )

    def cambiar_estado_producto(self, codigo: str, activo: bool) -> None:
        self.template_sync.cambiar_estado_producto(codigo, activo)

    def agregar_producto_en_posicion(
        self,
        codigo_nuevo: str,
        nombre_nuevo: str,
        codigo_arriba: str,
        stock_inicial: Optional[int] = None,
        cod_barras: str = "",
    ) -> Tuple[bool, str, Optional[int]]:
        return self.template_sync.agregar_producto_en_posicion(
            codigo_nuevo=codigo_nuevo,
            nombre_nuevo=nombre_nuevo,
            codigo_arriba=codigo_arriba,
            stock_inicial=stock_inicial,
            cod_barras=cod_barras,
        )

    def sincronizar_stocks(self, stocks: Dict[str, int]) -> int:
        return self.template_sync.sincronizar_stocks(stocks)

    def exportar_catalogo_a_excel(self, ruta_destino: Path | str | None = None) -> int:
        return self.template_sync.exportar_catalogo_a_excel(ruta_destino=ruta_destino)

    def sincronizar_catalogo_completo_excel(self) -> int:
        return self.template_sync.sincronizar_catalogo_completo_excel()

    def importar_catalogo_desde_excel(
        self, ruta_excel: Path | str | None = None
    ) -> ResultadoSincronizacionExcel:
        return self.template_sync.importar_catalogo_desde_excel(ruta_excel=ruta_excel)

    def aplicar_descuentos(
        self,
        items_consolidados: Dict,
        carpeta_destino: str | Path,
        pedidos_procesados: Optional[List[ResultadoRemito]] = None,
        guardar_archivo: bool = True,
        prefijo_archivo: str = "Descuento",
        descuento_ya_aplicado: bool = False,
    ) -> ReporteStock:
        return self.discount_engine.aplicar_descuentos(
            items_consolidados=items_consolidados,
            carpeta_destino=carpeta_destino,
            pedidos_procesados=pedidos_procesados,
            guardar_archivo=guardar_archivo,
            prefijo_archivo=prefijo_archivo,
            descuento_ya_aplicado=descuento_ya_aplicado,
        )

    def _crear_informe_desde_plantilla(
        self,
        cantidad_descuentos: int,
        unidades_descontadas: int,
        fecha_generacion: str,
        filas_productos: List[Tuple[int, str, Optional[int], str, Optional[int]]],
        pedidos_descontados: List[ResultadoRemito],
        productos_sin_coincidencia: List[Tuple[str, str, str, str]],
    ):
        return self.discount_engine._crear_informe_desde_plantilla(
            cantidad_descuentos,
            unidades_descontadas,
            fecha_generacion,
            filas_productos,
            pedidos_descontados,
            productos_sin_coincidencia,
        )

    def _copiar_estilo_fila(
        self,
        hoja_plantilla,
        hoja_salida,
        fila_plantilla: int,
        fila_salida: int,
        cantidad_columnas: int,
    ) -> None:
        self.discount_engine._copiar_estilo_fila(
            hoja_plantilla, hoja_salida, fila_plantilla, fila_salida, cantidad_columnas
        )

    @staticmethod
    def _guardar_informe_xls(libro: openpyxl.Workbook, ruta: Path) -> None:
        DiscountEngineService._guardar_informe_xls(libro, ruta)

    @staticmethod
    def _guardar_informe_pdf(libro: openpyxl.Workbook, ruta: Path) -> None:
        DiscountEngineService._guardar_informe_pdf(libro, ruta)

    def registrar_movimientos_historial(self, stocks_delta: Dict[str, int], tipo: str) -> None:
        self.discount_engine.registrar_movimientos_historial(stocks_delta, tipo)

    def consultar_movimientos(
        self,
        fecha_desde: str,
        fecha_hasta: str,
        tipo: Optional[str] = None,
        top_n: Optional[int] = None,
    ) -> List:
        return self.discount_engine.consultar_movimientos(
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            tipo=tipo,
            top_n=top_n,
        )

    def registrar_ingreso_fabrica(
        self,
        ingresos: Dict[str, int],
        sobrescribir: bool = False,
    ) -> Dict[str, Tuple[int, int]]:
        return self.discount_engine.registrar_ingreso_fabrica(ingresos, sobrescribir=sobrescribir)

    def actualizar_stock_base(
        self,
        descuentos: List[RegistroDescuento],
        sincronizar_excel: bool = False,
        nombre_archivo: str = "Descuento",
        usuario: str = "sistema",
    ) -> int:
        return self.discount_engine.actualizar_stock_base(
            descuentos=descuentos,
            sincronizar_excel=sincronizar_excel,
            nombre_archivo=nombre_archivo,
            usuario=usuario,
        )

    def obtener_notificaciones_admin(self, solo_no_leidas: bool = False) -> list:
        return self.discount_engine.obtener_notificaciones_admin(solo_no_leidas=solo_no_leidas)

    def contar_notificaciones_no_leidas(self) -> int:
        return self.discount_engine.contar_notificaciones_no_leidas()

    def marcar_notificaciones_leidas(self, notificacion_id: int | None = None) -> None:
        self.discount_engine.marcar_notificaciones_leidas(notificacion_id=notificacion_id)

    def descontar_mercado_full(
        self,
        descuentos: Dict[str, int],
        nombre_archivo: str = "MercadoFull",
        sincronizar_excel: bool = True,
    ) -> Dict[str, Tuple[int, int]]:
        return self.discount_engine.descontar_mercado_full(
            descuentos=descuentos,
            nombre_archivo=nombre_archivo,
            sincronizar_excel=sincronizar_excel,
        )
