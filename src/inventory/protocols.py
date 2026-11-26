"""Contratos estructurales (Protocols) para composición de servicios de inventario."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable


@runtime_checkable
class InventoryHostProtocol(Protocol):
    """Contrato mínimo que los servicios de inventario requieren del orquestador `StockManager`."""

    ruta_excel_base: Path
    nombre_hoja: str
    product_store: Any
    productos_base: List[Tuple[int, str, str, int]]
    filas_catalogo: List[Tuple[int, str, str, int]]
    catalogo: Dict[str, Tuple[int, str, int]]
    _filas_por_codigo: Dict[str, List[int]]
    _col_codigo: int
    _col_nombre: int
    _col_stock: int
    _col_stock_inicial: Optional[int]
    _col_descuento: Optional[int]
    _col_stock_final: Optional[int]
    _fila_inicio_datos: int

    def _cargar_catalogo(self, forzar_excel: bool = False) -> None: ...
    def _actualizar_stocks_en_memoria(self, stocks: Dict[str, int]) -> None: ...
    def _detectar_esquema(self, sheet: Any) -> None: ...
    def _leer_stock(self, sheet: Any, fila: int) -> int: ...
    def sincronizar_stocks(self, stocks: Dict[str, int]) -> int: ...
    def exportar_catalogo_a_excel(self, ruta_destino: Path | str | None = None) -> int: ...
    def _crear_informe_desde_plantilla(
        self,
        cantidad_descuentos: int,
        unidades_descontadas: int,
        fecha_generacion: str,
        filas_productos: List[Tuple[int, str, Optional[int], str, Optional[int]]],
        pedidos_descontados: List[Any],
        productos_sin_coincidencia: List[Tuple[str, str, str, str]],
    ) -> Any: ...
    @staticmethod
    def _guardar_informe_xls(libro: Any, ruta: Path) -> None: ...
    @staticmethod
    def _guardar_informe_pdf(libro: Any, ruta: Path) -> None: ...
