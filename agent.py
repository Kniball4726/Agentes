"""
Módulo del Agente Verificador y Gestor de Stock.
Orquesta el flujo completo para múltiples fuentes de descuento (Remitos PDF y Canjes Excel):
1. Percepción: Extrae y verifica cada remito PDF y planilla Excel de canjes.
2. Razonamiento: Consolida y suma duplicados de productos entre todas las fuentes.
3. Acción: Descuenta el stock en la planilla (exclusivamente en columna C),
   agrega los no catalogados al final y emite un informe de auditoría detallado.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
from canjes_parser import parsear_canje_excel
from consolidator import ItemConsolidado, consolidar_productos
from remito_parser import ItemRemito, ResultadoRemito, parsear_remito
from stock_manager import ReporteStock, StockManager


@dataclass
class ReporteMisionAgente:
    total_documentos: int
    documentos_verificados: List[ResultadoRemito]
    items_consolidados: Dict[str, ItemConsolidado]
    duplicados_detectados: List[ItemConsolidado]
    reporte_stock: ReporteStock


class AgenteRemitosStock:
    """
    Agente inteligente encargado de verificar remitos (PDF) y canjes (Excel),
    consolidar productos y aplicar los descuentos en la lista de stock preestablecida.
    """
    def __init__(self, stock_manager: StockManager):
        self.stock_manager = stock_manager

    def ejecutar(
        self, 
        rutas_pdf: Optional[List[str | Path]] = None,
        rutas_canjes: Optional[List[str | Path]] = None,
        carpeta_descuentos: Optional[str | Path] = None,
        simulacion: bool = False
    ) -> ReporteMisionAgente:
        rutas_pdf = rutas_pdf or []
        rutas_canjes = rutas_canjes or []
        total_docs = len(rutas_pdf) + len(rutas_canjes)
        carpeta_descuentos = carpeta_descuentos or Path(self.stock_manager.ruta_excel_base).parent / "descuentos"

        modo_txt = " [MODO SIMULACION - SOLO LECTURA]" if simulacion else ""
        print("\n" + "=" * 70)
        print(f"[AGENTE] Iniciando mision de verificacion y descuento de stock...{modo_txt}")
        print(f"         Fuentes: {len(rutas_pdf)} Remitos (PDF) | {len(rutas_canjes)} Canjes (Excel)")
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

        # 3. ACCIÓN: Generar planilla de descuento (Stock Inicial | Descuento | Stock Final)
        print("\n[3. Accion] Generando planilla de descuento con control de inventario...")
        reporte_stock = self.stock_manager.aplicar_descuentos(
            items_consolidados=consolidados,
            carpeta_destino=carpeta_descuentos,
            pedidos_procesados=documentos_resultados,
            guardar_archivo=not simulacion
        )

        existentes = [d for d in reporte_stock.descuentos_aplicados if not d.es_nuevo_agregado]
        nuevos = [d for d in reporte_stock.descuentos_aplicados if d.es_nuevo_agregado]

        print(f"   [OK] Planilla generada con {len(existentes)} productos descontados (SI → Desc → SF).")
        if nuevos:
            print(f"   [INFO] Se agregaron {len(nuevos)} productos no encontrados al final de la lista.")

        # 3b. ACTUALIZACIÓN DE STOCK BASE: Stock Final → Stock Inicial de la próxima corrida
        if not simulacion:
            print("\n[3b. Actualizacion] Escribiendo Stock Final en Productos.xlsx para la próxima corrida...")
            actualizados = self.stock_manager.actualizar_stock_base(reporte_stock.descuentos_aplicados)
            print(f"   [OK] {actualizados} producto(s) actualizados en el catálogo base.")
        else:
            print("\n[SIMULACION] Productos.xlsx no fue modificado (modo solo lectura).")

        return ReporteMisionAgente(
            total_documentos=total_docs,
            documentos_verificados=documentos_resultados,
            items_consolidados=consolidados,
            duplicados_detectados=duplicados,
            reporte_stock=reporte_stock
        )

