"""Módulo de Análisis de Rotación ABC, Mapa de Calor (Heatmap) y Optimización de Slotting para Depósito."""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


# Configuración del Layout Estándar del Depósito
DEFAULT_RACKS = ("A", "B", "C", "D")
DEFAULT_MODULES = (1, 2, 3, 4)
DEFAULT_LEVELS = (1, 2, 3)  # 1: Piso / Suelo, 2: Golden Zone (Cintura/Pecho), 3: Nivel Alto

# Pesos de accesibilidad ergonómica y distancia al área de empaque/despacho
RACK_DISTANCES = {"A": 1, "B": 2, "C": 3, "D": 4}
LEVEL_FACTORS = {2: 1.0, 1: 1.3, 3: 1.6}  # Golden zone tiene el mejor factor (1.0)


@dataclass
class SlotInfo:
    rack: str
    modulo: int
    nivel: int
    codigo: str
    es_zona_dorada: bool
    distancia: int
    factor_ergonomico: float
    score_accesibilidad: float

    @classmethod
    def from_codigo(cls, codigo: str) -> SlotInfo:
        parts = codigo.upper().split("-")
        rack = parts[0] if parts and parts[0] in DEFAULT_RACKS else "B"
        try:
            modulo = int(parts[1]) if len(parts) > 1 else 1
        except ValueError:
            modulo = 1
        try:
            nivel = int(parts[2]) if len(parts) > 2 else 2
        except ValueError:
            nivel = 2

        es_dorada = (nivel == 2)
        dist = RACK_DISTANCES.get(rack, 2)
        erg = LEVEL_FACTORS.get(nivel, 1.3)
        score = round(dist * erg, 2)
        return cls(
            rack=rack,
            modulo=modulo,
            nivel=nivel,
            codigo=f"{rack}-{modulo:02d}-{nivel}",
            es_zona_dorada=es_dorada,
            distancia=dist,
            factor_ergonomico=erg,
            score_accesibilidad=score,
        )


@dataclass
class ProductoRotacion:
    codigo: str
    nombre: str
    stock_actual: int
    total_despachos: int
    unidades_despachadas: int
    categoria_abc: str  # 'A', 'B', 'C'
    porcentaje_salidas: float
    porcentaje_acumulado: float
    ubicacion_actual: str
    ubicacion_sugerida: str
    desalineado: bool = False
    motivo_desalineacion: str = ""


@dataclass
class HeatmapSlot:
    ubicacion: str
    rack: str
    modulo: int
    nivel: int
    picks_totales: int
    unidades_totales: int
    heat_score: float  # 0.0 a 100.0
    temperatura: str  # 'muy_caliente', 'caliente', 'templado', 'frio'
    color_hex: str
    es_zona_dorada: bool
    skus_alojados: List[str] = field(default_factory=list)


@dataclass
class SlottingSuggestion:
    sku: str
    nombre: str
    categoria_abc: str
    ubicacion_actual: str
    ubicacion_sugerida: str
    motivo: str
    impacto: str
    tipo_alerta: str  # 'fast_mover_en_fondo', 'slow_mover_en_dorada', 'ergonomia'


@dataclass
class WarehouseMetrics:
    total_picks: int
    total_unidades: int
    total_skus: int
    skus_clase_a: int
    skus_clase_b: int
    skus_clase_c: int
    eficiencia_slotting_pct: float
    reubicaciones_sugeridas: int
    zona_mas_caliente: str


def generar_ubicacion_default(sku: str) -> str:
    """Genera una ubicación determinística estándar para un producto si no tiene asignada."""
    clean = sku.strip().upper()
    if not clean:
        return "B-01-2"
    h = int(hashlib.md5(clean.encode("utf-8")).hexdigest(), 16)
    rack = DEFAULT_RACKS[h % len(DEFAULT_RACKS)]
    modulo = ((h // 4) % len(DEFAULT_MODULES)) + 1
    nivel = ((h // 16) % len(DEFAULT_LEVELS)) + 1
    return f"{rack}-{modulo:02d}-{nivel}"


def _calcular_ubicacion_optima(categoria: str, index: int) -> str:
    """Asigna una ubicación recomendada óptima según la categoría ABC."""
    if categoria == "A":
        # Zona Dorada (Nivel 2) en Rack A o B
        rack = "A" if (index % 2 == 0) else "B"
        modulo = (index % 4) + 1
        return f"{rack}-{modulo:02d}-2"
    elif categoria == "B":
        # Racks B y C, niveles 1 o 2
        rack = "B" if (index % 2 == 0) else "C"
        modulo = (index % 4) + 1
        nivel = 1 if (index % 3 == 0) else 2
        return f"{rack}-{modulo:02d}-{nivel}"
    else:
        # Clase C: Racks C o D, niveles 1 o 3 (fuera de la Golden Zone)
        rack = "D" if (index % 2 == 0) else "C"
        modulo = (index % 4) + 1
        nivel = 3 if (index % 3 == 0) else 1
        return f"{rack}-{modulo:02d}-{nivel}"


def analizar_rotacion_abc(
    product_store: Any,
    order_store: Optional[Any] = None,
    dias: int = 30,
) -> List[ProductoRotacion]:
    """Realiza la clasificación ABC de Pareto sobre los productos del catálogo."""
    # 1. Obtener todos los productos activos
    productos_dict: Dict[str, Dict[str, Any]] = {}
    with closing(product_store._connect()) as conn:
        cursor = conn.execute(
            """
            SELECT code, name, stock, COALESCE(ubicacion, '') AS ubicacion
            FROM products
            WHERE active = 1
            """
        )
        for row in cursor.fetchall():
            code = str(row["code"]).strip()
            ubic = str(row["ubicacion"]).strip()
            if not ubic:
                ubic = generar_ubicacion_default(code)
            productos_dict[code] = {
                "name": str(row["name"]),
                "stock": int(row["stock"] or 0),
                "ubicacion": ubic,
                "picks": 0,
                "unidades": 0,
            }

    if not productos_dict:
        return []

    # 2. Consultar movimientos de salida en ProductStore (stock_movements)
    fecha_limite = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%S")
    with closing(product_store._connect()) as conn:
        try:
            cursor = conn.execute(
                """
                SELECT product_code, COUNT(*) AS picks, ABS(SUM(quantity)) AS unidades
                FROM stock_movements
                WHERE quantity < 0
                  AND (registered_at >= ? OR registered_at IS NULL)
                GROUP BY product_code
                """,
                (fecha_limite,),
            )
            for row in cursor.fetchall():
                code = str(row["product_code"]).strip()
                if code in productos_dict:
                    productos_dict[code]["picks"] += int(row["picks"] or 0)
                    productos_dict[code]["unidades"] += int(row["unidades"] or 0)
        except Exception:
            pass

    # 3. Si hay OrderStore, consultar también pedido_items
    if order_store is not None:
        try:
            with order_store._connect() as conn:
                cursor = conn.execute(
                    """
                    SELECT pi.codigo, COUNT(DISTINCT pi.pedido_id) AS picks, SUM(pi.cantidad) AS unidades
                    FROM pedido_items pi
                    JOIN pedidos p ON p.id = pi.pedido_id
                    WHERE p.estado != 'anulado'
                      AND p.created_at >= ?
                    GROUP BY pi.codigo
                    """,
                    (fecha_limite,),
                )
                for row in cursor.fetchall():
                    code = str(row["codigo"]).strip()
                    if code in productos_dict:
                        productos_dict[code]["picks"] = max(
                            productos_dict[code]["picks"], int(row["picks"] or 0)
                        )
                        productos_dict[code]["unidades"] = max(
                            productos_dict[code]["unidades"], int(row["unidades"] or 0)
                        )
        except Exception:
            pass

    # 4. Ordenar productos por volumen de picks descendente (y unidades como desempate)
    items_ordenados = sorted(
        productos_dict.items(),
        key=lambda x: (x[1]["picks"], x[1]["unidades"], x[1]["stock"]),
        reverse=True,
    )

    total_picks = sum(item[1]["picks"] for item in items_ordenados)
    if total_picks == 0:
        total_picks = 1  # Evitar división por cero

    # 5. Calcular porcentajes acumulados y categorizar ABC
    acumulado = 0.0
    resultado: List[ProductoRotacion] = []

    for idx, (code, data) in enumerate(items_ordenados):
        picks = data["picks"]
        unidades = data["unidades"]
        pct_relativo = round((picks / total_picks) * 100, 2)
        acumulado += pct_relativo
        pct_acumulado = min(100.0, round(acumulado, 2))

        # Pareto 75/15/10
        if picks > 0:
            if pct_acumulado <= 75.0 or idx < max(1, len(items_ordenados) // 10):
                cat = "A"
            elif pct_acumulado <= 92.0:
                cat = "B"
            else:
                cat = "C"
        else:
            cat = "C"

        ubic_actual = data["ubicacion"]
        slot_actual = SlotInfo.from_codigo(ubic_actual)
        ubic_optima = _calcular_ubicacion_optima(cat, idx)

        # Evaluar desalineación
        desalineado = False
        motivo = ""

        if cat == "A":
            # Alta rotación en zona fría (Rack C o D) o fuera de nivel 2
            if slot_actual.rack in ("C", "D"):
                desalineado = True
                motivo = f"Producto Clase A ubicado en fondo ({slot_actual.rack}). Genera sobre-recorrido."
            elif slot_actual.nivel == 3:
                desalineado = True
                motivo = f"Producto Clase A ubicado en altura (Nivel 3). Requiere escalera."
        elif cat == "C":
            # Baja rotación ocupando Golden Zone en Rack A
            if slot_actual.rack == "A" and slot_actual.es_zona_dorada:
                desalineado = True
                motivo = "Producto Clase C ocupa ubicación dorada en Rack A. Desperdicia espacio prioritario."

        resultado.append(
            ProductoRotacion(
                codigo=code,
                nombre=data["name"],
                stock_actual=data["stock"],
                total_despachos=picks,
                unidades_despachadas=unidades,
                categoria_abc=cat,
                porcentaje_salidas=pct_relativo,
                porcentaje_acumulado=pct_acumulado,
                ubicacion_actual=ubic_actual,
                ubicacion_sugerida=ubic_optima,
                desalineado=desalineado,
                motivo_desalineacion=motivo,
            )
        )

    return resultado


def generar_mapa_calor(
    analisis_abc: List[ProductoRotacion],
) -> List[HeatmapSlot]:
    """Genera la matriz térmica (Heatmap) de todas las ubicaciones del depósito."""
    slots_map: Dict[str, Dict[str, Any]] = {}

    # Inicializar todos los 48 slots del layout estándar
    for rack in DEFAULT_RACKS:
        for mod in DEFAULT_MODULES:
            for niv in DEFAULT_LEVELS:
                cod = f"{rack}-{mod:02d}-{niv}"
                slots_map[cod] = {
                    "rack": rack,
                    "modulo": mod,
                    "nivel": niv,
                    "picks": 0,
                    "unidades": 0,
                    "skus": [],
                }

    # Asignar productos a slots
    for prod in analisis_abc:
        slot_info = SlotInfo.from_codigo(prod.ubicacion_actual)
        cod = slot_info.codigo
        if cod not in slots_map:
            slots_map[cod] = {
                "rack": slot_info.rack,
                "modulo": slot_info.modulo,
                "nivel": slot_info.nivel,
                "picks": 0,
                "unidades": 0,
                "skus": [],
            }
        slots_map[cod]["picks"] += prod.total_despachos
        slots_map[cod]["unidades"] += prod.unidades_despachadas
        slots_map[cod]["skus"].append(f"{prod.codigo} ({prod.categoria_abc})")

    max_picks = max((s["picks"] for s in slots_map.values()), default=1)
    if max_picks == 0:
        max_picks = 1

    resultado: List[HeatmapSlot] = []
    for cod, data in sorted(slots_map.items()):
        picks = data["picks"]
        heat_score = round((picks / max_picks) * 100.0, 1)

        # Gradiente térmico
        if heat_score >= 70.0 and picks > 0:
            temperatura = "muy_caliente"
            color_hex = "#D32F2F"  # Rojo fuego
        elif heat_score >= 40.0 and picks > 0:
            temperatura = "caliente"
            color_hex = "#FF9800"  # Naranja
        elif heat_score >= 15.0 and picks > 0:
            temperatura = "templado"
            color_hex = "#FFC107"  # Ámbar
        else:
            temperatura = "frio"
            color_hex = "#37474F"  # Azul/gris frío

        resultado.append(
            HeatmapSlot(
                ubicacion=cod,
                rack=data["rack"],
                modulo=data["modulo"],
                nivel=data["nivel"],
                picks_totales=picks,
                unidades_totales=data["unidades"],
                heat_score=heat_score,
                temperatura=temperatura,
                color_hex=color_hex,
                es_zona_dorada=(data["nivel"] == 2),
                skus_alojados=data["skus"],
            )
        )

    return resultado


def generar_sugerencias_slotting(
    analisis_abc: List[ProductoRotacion],
) -> List[SlottingSuggestion]:
    """Genera recomendaciones accionables de reubicación ordenadas por impacto operativo."""
    sugerencias: List[SlottingSuggestion] = []

    for prod in analisis_abc:
        if not prod.desalineado:
            continue

        slot_actual = SlotInfo.from_codigo(prod.ubicacion_actual)
        if prod.categoria_abc == "A":
            if slot_actual.rack in ("C", "D"):
                sugerencias.append(
                    SlottingSuggestion(
                        sku=prod.codigo,
                        nombre=prod.nombre,
                        categoria_abc="A",
                        ubicacion_actual=prod.ubicacion_actual,
                        ubicacion_sugerida=prod.ubicacion_sugerida,
                        motivo=prod.motivo_desalineacion,
                        impacto="Alta prioridad: ahorra hasta 45% en recorrido de operarios hacia el fondo",
                        tipo_alerta="fast_mover_en_fondo",
                    )
                )
            elif slot_actual.nivel == 3:
                sugerencias.append(
                    SlottingSuggestion(
                        sku=prod.codigo,
                        nombre=prod.nombre,
                        categoria_abc="A",
                        ubicacion_actual=prod.ubicacion_actual,
                        ubicacion_sugerida=prod.ubicacion_sugerida,
                        motivo=prod.motivo_desalineacion,
                        impacto="Prioridad ergonómica: evita uso de escalera en picking frecuente",
                        tipo_alerta="ergonomia",
                    )
                )
        elif prod.categoria_abc == "C":
            if slot_actual.rack == "A" and slot_actual.es_zona_dorada:
                sugerencias.append(
                    SlottingSuggestion(
                        sku=prod.codigo,
                        nombre=prod.nombre,
                        categoria_abc="C",
                        ubicacion_actual=prod.ubicacion_actual,
                        ubicacion_sugerida=prod.ubicacion_sugerida,
                        motivo=prod.motivo_desalineacion,
                        impacto="Reubicación recomendada: libera posición estratégica para artículos clase A",
                        tipo_alerta="slow_mover_en_dorada",
                    )
                )

    # Ordenar sugerencias: Clase A primero
    sugerencias.sort(key=lambda s: (0 if s.categoria_abc == "A" else 1, s.sku))
    return sugerencias


def calcular_metricas_deposito(
    analisis_abc: List[ProductoRotacion],
    mapa_calor: List[HeatmapSlot],
) -> WarehouseMetrics:
    """Calcula indicadores KPI de eficiencia de almacenamiento y picking."""
    total_skus = len(analisis_abc)
    total_picks = sum(p.total_despachos for p in analisis_abc)
    total_unidades = sum(p.unidades_despachadas for p in analisis_abc)

    clase_a = sum(1 for p in analisis_abc if p.categoria_abc == "A")
    clase_b = sum(1 for p in analisis_abc if p.categoria_abc == "B")
    clase_c = sum(1 for p in analisis_abc if p.categoria_abc == "C")

    desalineados = sum(1 for p in analisis_abc if p.desalineado)
    if total_skus > 0:
        eficiencia = round((1.0 - (desalineados / total_skus)) * 100.0, 1)
    else:
        eficiencia = 100.0

    # Ubicación más caliente
    slot_top = max(mapa_calor, key=lambda s: s.picks_totales, default=None)
    zona_top = f"{slot_top.ubicacion} ({slot_top.picks_totales} picks)" if slot_top and slot_top.picks_totales > 0 else "Sin movimientos recientes"

    return WarehouseMetrics(
        total_picks=total_picks,
        total_unidades=total_unidades,
        total_skus=total_skus,
        skus_clase_a=clase_a,
        skus_clase_b=clase_b,
        skus_clase_c=clase_c,
        eficiencia_slotting_pct=max(0.0, eficiencia),
        reubicaciones_sugeridas=desalineados,
        zona_mas_caliente=zona_top,
    )


def aplicar_reubicacion_slotting(
    product_store: Any,
    sku: str,
    nueva_ubicacion: str,
) -> bool:
    """Aplica la reubicación en la base de datos de productos."""
    return product_store.actualizar_ubicacion(sku, nueva_ubicacion)
