"""Modelos de datos para el dominio de gestión de stock y reportes."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class RegistroDescuento:
    """Representa el descuento aplicado a un producto individual."""
    codigo: str
    nombre_producto: str
    fila_excel: int
    stock_anterior: int
    cantidad_descontada: int
    stock_nuevo: int
    es_nuevo_agregado: bool = False


@dataclass
class ReporteStock:
    """Resultado del procesamiento de un lote de descuentos."""
    descuentos_aplicados: List[RegistroDescuento]
    archivo_guardado: str
    archivo_pdf: Optional[str] = None

    @property
    def articulos_quiebre(self) -> List[RegistroDescuento]:
        """Artículos cuyo stock quedó en 0 o negativo tras el descuento."""
        return [r for r in self.descuentos_aplicados if r.stock_nuevo <= 0]

    @property
    def articulos_criticos(self) -> List[RegistroDescuento]:
        """Artículos con stock bajo (entre 1 y 5 unidades) tras el descuento."""
        return [r for r in self.descuentos_aplicados if 0 < r.stock_nuevo <= 5]
