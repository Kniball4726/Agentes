"""Mixin con motor de descuentos, ingresos de fábrica, Mercado Full, historial y notificaciones."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import openpyxl

from ..consolidator import ItemConsolidado
from ..remito_parser import ResultadoRemito, normalizar_codigo
from ..stock.models import RegistroDescuento, ReporteStock
from ..stock.reports import copiar_estilo_fila, guardar_informe_pdf, guardar_informe_xls
from .excel_sync import crear_informe_desde_plantilla


class DiscountEngineMixin:
    """Encapsula cálculo de descuentos, aplicación de stock e informes de movimientos."""

    ruta_excel_base: Path
    nombre_hoja: str
    product_store: object
    productos_base: List[Tuple[int, str, str, int]]
    filas_catalogo: List[Tuple[int, str, str, int]]
    catalogo: Dict[str, Tuple[int, str, int]]
    _col_codigo: int
    _col_nombre: int
    _col_descuento: Optional[int]
    _col_stock: int
    _col_stock_inicial: Optional[int]
    _col_stock_final: Optional[int]
    _fila_inicio_datos: int

    def aplicar_descuentos(
        self,
        items_consolidados: Dict[str, ItemConsolidado],
        carpeta_destino: str | Path,
        pedidos_procesados: Optional[List[ResultadoRemito]] = None,
        guardar_archivo: bool = True,
        prefijo_archivo: str = "Descuento",
        descuento_ya_aplicado: bool = False,
    ) -> ReporteStock:
        """Genera un informe con el diseño del catálogo, sin modificarlo."""
        carpeta_destino = Path(carpeta_destino)
        fecha_generacion = datetime.now()
        fecha_hora_str = fecha_generacion.strftime("%d-%m-%Y_%H-%M-%S")
        nombre_archivo = (
            f"{prefijo_archivo}_{fecha_hora_str}.xls"
            if prefijo_archivo != "Descuento"
            else f"Descuento{fecha_hora_str}.xls"
        )
        ruta_guardado = carpeta_destino / nombre_archivo
        ruta_pdf = ruta_guardado.with_suffix(".pdf")

        descuentos: List[RegistroDescuento] = []
        for _, cod, nombre, stock_ant in self.productos_base:
            item = items_consolidados.get(cod)
            if item is None:
                continue
            if descuento_ya_aplicado:
                stk_ant_calc = int(stock_ant + item.cantidad_total)
                stk_nvo_calc = int(stock_ant)
            else:
                stk_ant_calc = int(stock_ant)
                stk_nvo_calc = int(stock_ant - item.cantidad_total)

            descuentos.append(
                RegistroDescuento(
                    codigo=cod,
                    nombre_producto=nombre,
                    fila_excel=4 + len(descuentos),
                    stock_anterior=stk_ant_calc,
                    cantidad_descontada=item.cantidad_total,
                    stock_nuevo=stk_nvo_calc,
                )
            )

        filas_productos = []
        for fila_original, cod, nombre, _ in self.filas_catalogo:
            item = items_consolidados.get(cod)
            filas_productos.append((
                fila_original,
                cod,
                item.cantidad_total if item else None,
                nombre,
                -item.cantidad_total if item else None,
            ))

        codigos_descontados = {registro.codigo for registro in descuentos}
        pedidos_descontados = [
            documento
            for documento in (pedidos_procesados or [])
            if not documento.items
            or any(normalizar_codigo(item.codigo) in codigos_descontados for item in documento.items)
        ]
        productos_sin_coincidencia = [
            (cod, ", ".join(item.remitos_origen), item.descripcion, "Código no encontrado en el catálogo SQLite")
            for cod, item in items_consolidados.items()
            if cod not in self.catalogo
        ]
        productos_sin_coincidencia.extend(
            ("", documento.numero_remito or documento.archivo, descripcion, motivo)
            for documento in (pedidos_procesados or [])
            for descripcion, motivo in documento.descripciones_sin_coincidencia
        )

        if guardar_archivo:
            wb_salida, _ = self._crear_informe_desde_plantilla(
                len(descuentos),
                sum(d.cantidad_descontada for d in descuentos),
                fecha_generacion.strftime("%d/%m/%y"),
                filas_productos,
                pedidos_descontados,
                productos_sin_coincidencia,
            )
            try:
                carpeta_destino.mkdir(parents=True, exist_ok=True)
                self._guardar_informe_xls(wb_salida, ruta_guardado)
                self._guardar_informe_pdf(wb_salida, ruta_pdf)
            finally:
                wb_salida.close()
            archivo_final = str(ruta_guardado)
            archivo_pdf: Optional[str] = str(ruta_pdf)
        else:
            archivo_final = ""
            archivo_pdf = None

        return ReporteStock(
            descuentos_aplicados=descuentos,
            archivo_guardado=archivo_final,
            archivo_pdf=archivo_pdf,
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
        return crear_informe_desde_plantilla(
            ruta_excel_base=self.ruta_excel_base,
            nombre_hoja=self.nombre_hoja,
            col_codigo=self._col_codigo,
            col_nombre=self._col_nombre,
            col_descuento=self._col_descuento,
            col_stock=self._col_stock,
            col_stock_inicial=self._col_stock_inicial,
            fila_inicio_datos=self._fila_inicio_datos,
            cantidad_descuentos=cantidad_descuentos,
            unidades_descontadas=unidades_descontadas,
            fecha_generacion=fecha_generacion,
            filas_productos=filas_productos,
            pedidos_descontados=pedidos_descontados,
            productos_sin_coincidencia=productos_sin_coincidencia,
        )

    def _copiar_estilo_fila(
        self,
        hoja_plantilla,
        hoja_salida,
        fila_plantilla: int,
        fila_salida: int,
        cantidad_columnas: int,
    ) -> None:
        columnas_plantilla = (
            self._col_codigo,
            self._col_nombre,
            self._col_descuento or self._col_stock,
            self._col_stock_final or self._col_stock,
        )
        copiar_estilo_fila(
            hoja_plantilla=hoja_plantilla,
            hoja_salida=hoja_salida,
            fila_plantilla=fila_plantilla,
            fila_salida=fila_salida,
            cantidad_columnas=cantidad_columnas,
            columnas_plantilla=columnas_plantilla,
        )

    @staticmethod
    def _guardar_informe_xls(libro: openpyxl.Workbook, ruta: Path) -> None:
        guardar_informe_xls(libro, ruta)

    @staticmethod
    def _guardar_informe_pdf(libro: openpyxl.Workbook, ruta: Path) -> None:
        guardar_informe_pdf(libro, ruta)

    def registrar_movimientos_historial(self, stocks_delta: Dict[str, int], tipo: str) -> None:
        """Persiste movimientos en `stock_movements` para estadísticas."""
        movimientos = [
            (cod, self.catalogo.get(cod, (0, cod, 0))[1], delta, tipo)
            for cod, delta in stocks_delta.items()
        ]
        self.product_store.register_movements(movimientos)

    def consultar_movimientos(
        self,
        fecha_desde: str,
        fecha_hasta: str,
        tipo: Optional[str] = None,
        top_n: Optional[int] = None,
    ) -> List:
        """Consulta historial agrupado de movimientos en SQLite."""
        hasta_inclusive = fecha_hasta if "T" in fecha_hasta else fecha_hasta + "T23:59:59"
        desde_inclusive = fecha_desde if "T" in fecha_desde else fecha_desde + "T00:00:00"
        return self.product_store.query_movements(
            date_from=desde_inclusive,
            date_to=hasta_inclusive,
            movement_type=tipo,
            top_n=top_n,
        )

    def registrar_ingreso_fabrica(
        self,
        ingresos: Dict[str, int],
        sobrescribir: bool = False,
    ) -> Dict[str, Tuple[int, int]]:
        """Aplica ingreso, ajuste o restablecimiento de stock y retorna `{codigo: (ant, nvo)}`."""
        if not ingresos:
            return {}

        resumen: Dict[str, Tuple[int, int]] = {}
        actualizaciones: Dict[str, int] = {}
        for codigo_raw, cantidad in ingresos.items():
            cod = normalizar_codigo(codigo_raw)
            if cod not in self.catalogo:
                raise ValueError(f"El código '{cod}' no se encuentra en el catálogo de productos.")
            _, _, stock_actual = self.catalogo[cod]
            nuevo_stock = max(0, int(cantidad)) if sobrescribir else int(stock_actual) + int(cantidad)
            actualizaciones[cod] = nuevo_stock
            resumen[cod] = (stock_actual, nuevo_stock)

        self.sincronizar_stocks(actualizaciones)
        return resumen

    def actualizar_stock_base(
        self,
        descuentos: List[RegistroDescuento],
        sincronizar_excel: bool = False,
        nombre_archivo: str = "Descuento",
        usuario: str = "sistema",
    ) -> int:
        """Persiste en SQLite los saldos nuevos de cada producto descontado."""
        existentes = [d for d in descuentos if not d.es_nuevo_agregado]
        if not existentes:
            return 0

        actualizaciones = {d.codigo: d.stock_nuevo for d in existentes}
        total_unidades = sum(d.cantidad_descontada for d in existentes)
        try:
            detalles = [(d.codigo, d.cantidad_descontada, d.stock_anterior, d.stock_nuevo) for d in existentes]
            self.product_store.record_dispatch(
                tipo_origen="Descuento",
                nombre_archivo=nombre_archivo,
                total_articulos=total_unidades,
                detalles=detalles,
                usuario=usuario,
            )
        except Exception as e:
            print(f"[AVISO] No se pudo registrar detalle de despacho: {e}")

        if usuario and usuario.lower() not in ("sistema", "administrador", "admin"):
            try:
                self.product_store.create_admin_notification(
                    title=f"Descuento procesado por operario '{usuario}'",
                    message=(
                        f"El operario '{usuario}' ejecutó un descuento de stock de {total_unidades} unidades "
                        f"en {len(existentes)} producto(s) desde {nombre_archivo}."
                    ),
                    operator_username=usuario,
                    notification_type="descuento",
                    details=f"Archivo: {nombre_archivo} | Unidades: {total_unidades} | Productos: {len(existentes)}",
                )
            except Exception as notif_err:
                print(f"[AVISO] No se pudo generar notificación para administrador: {notif_err}")

        if sincronizar_excel:
            return self.sincronizar_stocks(actualizaciones)

        filas_actualizadas = self.product_store.update_stocks(actualizaciones)
        self._actualizar_stocks_en_memoria(actualizaciones)
        return filas_actualizadas

    def obtener_notificaciones_admin(self, solo_no_leidas: bool = False) -> list:
        """Lista notificaciones administrativas pendientes o históricas."""
        return self.product_store.list_admin_notifications(unread_only=solo_no_leidas)

    def contar_notificaciones_no_leidas(self) -> int:
        """Retorna cantidad de notificaciones administrativas sin leer."""
        return self.product_store.get_unread_notifications_count()

    def marcar_notificaciones_leidas(self, notificacion_id: int | None = None) -> None:
        """Marca una o todas las notificaciones administrativas como leídas."""
        if notificacion_id is not None:
            self.product_store.mark_notification_as_read(notificacion_id)
        else:
            self.product_store.mark_all_notifications_as_read()

    def descontar_mercado_full(
        self,
        descuentos: Dict[str, int],
        nombre_archivo: str = "MercadoFull",
        sincronizar_excel: bool = True,
    ) -> Dict[str, Tuple[int, int]]:
        """Descuenta unidades enviadas a Mercado Envíos Full del stock actual."""
        if not descuentos:
            return {}

        resumen: Dict[str, Tuple[int, int]] = {}
        actualizaciones: Dict[str, int] = {}
        detalles_despacho = []

        for codigo_raw, cant_descontar in descuentos.items():
            cod = normalizar_codigo(codigo_raw)
            if cod not in self.catalogo:
                raise ValueError(f"El código '{cod}' no se encuentra en el catálogo de productos.")
            cant = int(cant_descontar)
            if cant <= 0:
                continue
            _, _, stock_actual = self.catalogo[cod]
            nuevo_stock = int(stock_actual) - cant
            actualizaciones[cod] = nuevo_stock
            resumen[cod] = (stock_actual, nuevo_stock)
            detalles_despacho.append((cod, cant, stock_actual, nuevo_stock))

        if not actualizaciones:
            return {}

        try:
            self.product_store.record_dispatch(
                tipo_origen="MercadoFull",
                nombre_archivo=nombre_archivo,
                total_articulos=sum(cant for _, cant, _, _ in detalles_despacho),
                detalles=detalles_despacho,
            )
        except Exception as e:
            print(f"[AVISO] No se pudo registrar despacho de Mercado Full: {e}")

        if sincronizar_excel:
            self.sincronizar_stocks(actualizaciones)
        else:
            self.product_store.update_stocks(actualizaciones)
            self._cargar_catalogo()

        return resumen
