"""
Módulo del Agente Verificador y Gestor de Stock.
Orquesta el flujo completo para remitos PDF, canjes Excel y pedidos de Mercado Libre:
1. Percepción: Extrae remitos PDF, canjes Excel y pedidos DOCX de Mercado Libre.
2. Razonamiento: Consolida y suma duplicados de productos entre todas las fuentes.
3. Acción: Consulta el catálogo SQLite y emite un informe de auditoría detallado.
"""

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Dict, List, Optional
from .consolidator import ItemConsolidado, consolidar_productos
from .inventory import StockManager
from .parsers.canjes_parser import parsear_canje_excel
from .parsers.mercado_libre_parser import parsear_pedido_mercado_libre
from .parsers.remito_parser import ItemRemito, ResultadoRemito, parsear_remito
from .stock.models import ReporteStock

logger = logging.getLogger("stockagent.agent")


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
        logger.info(
            "Iniciando misión de verificación y descuento de stock%s "
            "(PDF=%d, Canjes=%d, MercadoLibre=%d)",
            modo_txt,
            len(rutas_pdf),
            len(rutas_canjes),
            len(rutas_mercado_libre),
        )

        documentos_resultados: List[ResultadoRemito] = []
        todos_los_items: List[ItemRemito] = []

        # 1. PERCEPCIÓN:
        # A) Procesar Remitos Mayoristas (PDF)
        if rutas_pdf:
            logger.info("[1.A Percepción] Procesando %d remito(s) mayorista(s) (PDF)", len(rutas_pdf))
            for ruta in rutas_pdf:
                path = Path(ruta)
                resultado = parsear_remito(path)
                documentos_resultados.append(resultado)
                todos_los_items.extend(resultado.items)

                estado = "OK" if resultado.verificacion_ok else "DISCREPANCIA"
                log_fn = logger.info if resultado.verificacion_ok else logger.warning
                log_fn(
                    "[PDF] Remito %s (%s) | Cliente=%s | Fecha=%s | Declarados=%s | Extraídos=%s -> %s",
                    resultado.numero_remito,
                    path.name,
                    resultado.cliente,
                    resultado.fecha,
                    resultado.articulos_declarados,
                    resultado.articulos_extraidos,
                    estado,
                )

        # B) Procesar Canjes (Excel)
        if rutas_canjes:
            logger.info("[1.B Percepción] Procesando %d planilla(s) de canjes (Excel)", len(rutas_canjes))
            for ruta in rutas_canjes:
                path = Path(ruta)
                resultado = parsear_canje_excel(path)
                documentos_resultados.append(resultado)
                todos_los_items.extend(resultado.items)

                logger.info(
                    "[EXCEL] Canje %s (%s) | Beneficiario=%s | Artículos=%s",
                    resultado.numero_remito,
                    path.name,
                    resultado.cliente,
                    resultado.articulos_extraidos,
                )

        # C) Procesar publicaciones/pedidos sin código de Mercado Libre
        if rutas_mercado_libre:
            logger.info(
                "[1.C Percepción] Procesando %d pedido(s) de Mercado Libre (DOCX)",
                len(rutas_mercado_libre),
            )
            productos_catalogo = [
                (codigo, nombre)
                for _, codigo, nombre, _ in self.stock_manager.productos_base
            ]
            for ruta in rutas_mercado_libre:
                path = Path(ruta)
                resultado = parsear_pedido_mercado_libre(path, productos_catalogo)
                documentos_resultados.append(resultado)
                todos_los_items.extend(resultado.items)

                logger.info(
                    "[MERCADO LIBRE] %s: %s/%s unidades asociadas al catálogo",
                    path.name,
                    resultado.articulos_extraidos,
                    resultado.articulos_declarados,
                )
                for descripcion, motivo in resultado.descripciones_sin_coincidencia:
                    logger.warning("[NO DESCONTADO] %s — %s", descripcion, motivo)

        # 2. RAZONAMIENTO: Consolidación y suma de duplicados entre todas las fuentes
        logger.info("[2. Razonamiento] Consolidando productos y sumando duplicados...")
        consolidados = consolidar_productos(todos_los_items)

        # Detectar cuáles tuvieron repeticiones
        conteo_apariciones = {}
        for it in todos_los_items:
            conteo_apariciones[it.codigo] = conteo_apariciones.get(it.codigo, 0) + 1

        duplicados = [consolidados[c] for c, count in conteo_apariciones.items() if count > 1]

        if duplicados:
            logger.info("Se detectaron %d código(s) repetido(s) que fueron consolidados.", len(duplicados))
            for dup in duplicados:
                logger.debug(
                    "Código %s (%s): total=%s unidades (origen=%s)",
                    dup.codigo,
                    dup.descripcion[:35],
                    dup.cantidad_total,
                    dup.remitos_origen,
                )
        else:
            logger.debug("No se detectaron códigos repetidos entre las fuentes.")

        # 3. ACCIÓN: Generar el informe desde SQLite y usar Productos.xlsx como plantilla visual.
        debe_guardar = guardar_archivo and not simulacion
        if debe_guardar:
            logger.info("[3. Acción] Generando planilla de descuentos desde el catálogo SQLite...")
        else:
            logger.info("[3. Acción] Calculando descuentos de stock (sin generación de documento individual)...")

        reporte_stock = self.stock_manager.aplicar_descuentos(
            items_consolidados=consolidados,
            carpeta_destino=carpeta_descuentos,
            pedidos_procesados=documentos_resultados,
            guardar_archivo=debe_guardar,
        )

        nuevos = [d for d in reporte_stock.descuentos_aplicados if d.es_nuevo_agregado]

        if debe_guardar:
            logger.info(
                "Planilla generada con %d producto(s) descontado(s).",
                len(reporte_stock.descuentos_aplicados),
            )
            if reporte_stock.archivo_pdf:
                logger.info("Informe PDF generado: %s", reporte_stock.archivo_pdf)
        else:
            logger.info(
                "%d producto(s) procesado(s) (el informe se generará en el Cierre de Jornada).",
                len(reporte_stock.descuentos_aplicados),
            )
        if nuevos:
            logger.info("Se incluyeron %d producto(s) no encontrados en el informe.", len(nuevos))

        return ReporteMisionAgente(
            total_documentos=total_docs,
            documentos_verificados=documentos_resultados,
            items_consolidados=consolidados,
            duplicados_detectados=duplicados,
            reporte_stock=reporte_stock
        )
