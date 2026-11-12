"""Módulo de compatibilidad para ProductStore.

Redirige a la implementación modular en src.products.
"""

from .products import ProductStore

__all__ = ["ProductStore"]
