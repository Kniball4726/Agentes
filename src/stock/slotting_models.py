"""Modelos de datos, constantes de layout y cálculo de ubicaciones para optimización de slotting."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import List


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

        es_dorada = nivel == 2
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
    h = int(hashlib.md5(clean.encode("utf-8"), usedforsecurity=False).hexdigest(), 16)
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
