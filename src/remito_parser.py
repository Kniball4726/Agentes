"""Módulo de compatibilidad. Ver implementación modular en src.parsers.remito_parser."""
from pypdf import PdfReader  # noqa: F401
from .parsers.remito_parser import *  # noqa: F401, F403
