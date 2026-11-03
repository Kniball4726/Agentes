"""Módulo de compatibilidad. Ver implementación modular en src.parsers.mercado_libre_parser."""
from .parsers.mercado_libre_parser import *  # noqa: F401, F403
from .parsers.mercado_libre_parser import (  # noqa: F401
    _buscar_codigo,
    _normalizar_descripcion,
    _normalizar_para_busqueda,
    _extraer_producto_numerado,
)
