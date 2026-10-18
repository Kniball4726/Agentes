"""
Módulo de Consolidación de Productos.
Toma los ítems extraídos de uno o más remitos y, si se repiten los códigos de producto,
los agrupa y suma sus cantidades totales para calcular el descuento neto.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List
from remito_parser import ItemRemito, normalizar_codigo


@dataclass
class ItemConsolidado:
    codigo: str
    descripcion: str
    cantidad_total: int
    remitos_origen: List[str] = field(default_factory=list)


def consolidar_productos(items: List[ItemRemito]) -> Dict[str, ItemConsolidado]:
    """
    Agrupa los ítems por código y suma sus cantidades acumuladas.
    
    Retorna un diccionario { codigo: ItemConsolidado }.
    """
    agrupados: Dict[str, ItemConsolidado] = {}

    for item in items:
        cod = normalizar_codigo(item.codigo)
        
        if cod not in agrupados:
            agrupados[cod] = ItemConsolidado(
                codigo=cod,
                descripcion=item.descripcion,
                cantidad_total=item.cantidad,
                remitos_origen=[item.origen_remito]
            )
        else:
            # Si el código ya existe, sumamos la cantidad
            agrupados[cod].cantidad_total += item.cantidad
            if item.origen_remito not in agrupados[cod].remitos_origen:
                agrupados[cod].remitos_origen.append(item.origen_remito)

    return agrupados
