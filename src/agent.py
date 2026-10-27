"""
Módulo del Agente Verificador y Gestor de Stock.
Orquesta el flujo completo para remitos PDF, canjes Excel y pedidos de Mercado Libre:
1. Percepción: Extrae remitos PDF, canjes Excel y pedidos DOCX de Mercado Libre.
2. Razonamiento: Consolida y suma duplicados de productos entre todas las fuentes.
3. Acción: Consulta el catálogo SQLite y emite un informe de auditoría detallado.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
from .canjes_parser import parsear_canje_excel
from .consolidator import ItemConsolidado, consolidar_productos
from .mercado_libre_parser import parsear_pedido_mercado_libre
from .remito_parser import ItemRemito, ResultadoRemito, parsear_remito
from .stock_manager import ReporteStock, StockManager


@dataclass
class ReporteMisionAgente:
    total_documentos: int
    documentos_verificados: List[ResultadoRemito]
    items_consolidados: Dict[str, ItemConsolidado]
    duplicados_detectados: List[ItemConsolidado]
    reporte_stock: ReporteStock


class AgenteRemitosStock:
    """
    Verifica las fuentes de pedidos, consolida productos y aplica descuentos
    al catálogo de stock preestablecido.
    """
    def __init__(self, stock_manager: StockManager):
        self.stock_manager = stock_manager

    def ejecutar(
        self, 
        rutas_pdf: Optional[List[str | Path]] = None,
        rutas_canjes: Optional[List[str | Path]] = None,
        carpeta_descuentos: Optional[str | Path] = None,
        simulacion: bool = False,
        rutas_mercado_libre: Optional[List[str | Path]] = None,
        guardar_archivo: bool = True,
    ) -> ReporteMisionAgente:
        rutas_pdf = rutas_pdf or []
        rutas_canjes = rutas_canjes or []
        rutas_mercado_libre = rutas_mercado_libre or []
        total_docs = len(rutas_pdf) + len(rutas_canjes) + len(rutas_mercado_libre)
        carpeta_descuentos = carpeta_descuentos or Path(self.stock_manager.ruta_excel_base).parent / "descuentos"

        modo_txt = " [MODO SIMULACION - SOLO LECTURA]" if simulacion else ""
        print("\n" + "=" * 70)
        print(f"[AGENTE] Iniciando mision de verificacion y descuento de stock...{modo_txt}")
        print(
            f"         Fuentes: {len(rutas_pdf)} Remitos (PDF) | "
            f"{len(rutas_canjes)} Canjes (Excel) | "
            f"{len(rutas_mercado_libre)} Pedidos Mercado Libre (DOCX)"
        )
        print("=" * 70)

        documentos_resultados: List[ResultadoRemito] = []
        todos_los_items: List[ItemRemito] = []

        # 1. PERCEPCIÓN:
        # A) Procesar Remitos Mayoristas (PDF)
        if rutas_pdf:
            print("\n--- [1.A Percepcion] Procesando Remitos Mayoristas (PDF) ---")
            for ruta in rutas_pdf:
                path = Path(ruta)
                resultado = parsear_remito(path)
                documentos_resultados.append(resultado)
                todos_los_items.extend(resultado.items)

                estado = "[OK] Verificacion Correcta" if resultado.verificacion_ok else "[ALERTA] DISCREPANCIA"
                print(f"   * [PDF] Remito {resultado.numero_remito} ({path.name})")
                print(f"     Cliente: {resultado.cliente} | Fecha: {resultado.fecha}")
                print(f"     Articulos declarados: {resultado.articulos_declarados} | Extraidos: {resultado.articulos_extraidos} -> {estado}")

        # B) Procesar Canjes (Excel)
        if rutas_canjes:
            print("\n--- [1.B Percepcion] Procesando Planillas de Canjes (Excel) ---")
            for ruta in rutas_canjes:
                path = Path(ruta)
                resultado = parsear_canje_excel(path)
                documentos_resultados.append(resultado)
                todos_los_items.extend(resultado.items)

                print(f"   * [EXCEL] Canje {resultado.numero_remito} ({path.name})")
                print(f"     Beneficiario: {resultado.cliente}")
                print(f"     Articulos solicitados: {resultado.articulos_extraidos}")

        # C) Procesar publicaciones/pedidos sin código de Mercado Libre
        if rutas_mercado_libre:
            print("\n--- [1.C Percepcion] Procesando pedidos de Mercado Libre (DOCX) ---")
            productos_catalogo = [
                (codigo, nombre)
                for _, codigo, nombre, _ in self.stock_manager.productos_base
            ]
            for ruta in rutas_mercado_libre:
                path = Path(ruta)
                resultado = parsear_pedido_mercado_libre(path, productos_catalogo)
                documentos_resultados.append(resultado)
                todos_los_items.extend(resultado.items)

                print(
                    f"   * [MERCADO LIBRE] {path.name}: "
                    f"{resultado.articulos_extraidos}/{resultado.articulos_declarados} "
                    "unidades asociadas al catálogo"
                )
                for descripcion, motivo in resultado.descripciones_sin_coincidencia:
                    print(f"     [NO DESCONTADO] {descripcion} — {motivo}")

        # 2. RAZONAMIENTO: Consolidación y suma de duplicados entre todas las fuentes
        print("\n[2. Razonamiento] Consolidando productos y sumando duplicados...")
        consolidados = consolidar_productos(todos_los_items)

        # Detectar cuáles tuvieron repeticiones
        conteo_apariciones = {}
        for it in todos_los_items:
            conteo_apariciones[it.codigo] = conteo_apariciones.get(it.codigo, 0) + 1
        
        duplicados = [consolidados[c] for c, count in conteo_apariciones.items() if count > 1]

        if duplicados:
            print(f"   [REPETICIONES] Se detectaron {len(duplicados)} codigos repetidos que fueron sumados:")
            for dup in duplicados:
                print(f"      - Codigo {dup.codigo} ({dup.descripcion[:35]}): Total consolidado = {dup.cantidad_total} unidades (en {dup.remitos_origen})")
        else:
            print("   [INFO] No se detectaron codigos repetidos.")

        # 3. ACCIÓN: Generar el informe desde SQLite y usar Productos.xlsx como plantilla visual.
        debe_guardar = guardar_archivo and not simulacion
        if debe_guardar:
            print("\n[3. Accion] Generando planilla de descuentos desde el catálogo SQLite...")
        else:
            print("\n[3. Accion] Calculando descuentos de stock (sin generación de documento individual)...")

        reporte_stock = self.stock_manager.aplicar_descuentos(
            items_consolidados=consolidados,
            carpeta_destino=carpeta_descuentos,
            pedidos_procesados=documentos_resultados,
            guardar_archivo=debe_guardar,
        )

        nuevos = [d for d in reporte_stock.descuentos_aplicados if d.es_nuevo_agregado]

        if debe_guardar:
            print(f"   [OK] Planilla generada con {len(reporte_stock.descuentos_aplicados)} productos descontados.")
            if reporte_stock.archivo_pdf:
                print(f"   [OK] Informe PDF generado: {reporte_stock.archivo_pdf}")
        else:
            print(f"   [OK] {len(reporte_stock.descuentos_aplicados)} productos procesados (el informe se generará en el Cierre de Jornada).")
        if nuevos:
            print(f"   [INFO] Se incluyeron {len(nuevos)} productos no encontrados en el informe.")
        print("   [INFO] El catálogo y el orden provienen de SQLite; Productos.xlsx aporta el formato.")

        return ReporteMisionAgente(
            total_documentos=total_docs,
            documentos_verificados=documentos_resultados,
            items_consolidados=consolidados,
            duplicados_detectados=duplicados,
            reporte_stock=reporte_stock
        )
