# -*- coding: utf-8 -*-
"""Paquete modular de manuales procedimentales por rol y orquestación PDF."""

from .fichas import (
    VERSION_PROC_ACTUAL,
    agregar_ficha_boton,
    agregar_fichas_modulo,
    construir_cierre_manual_rol,
    iniciar_manual_rol,
)
from .rol_administrador import construir_manual_administrador
from .rol_consulta import construir_manual_consulta
from .rol_despachador import construir_manual_despachador
from .rol_master import construir_manual_master
from .rol_operador import construir_manual_operador
from .rol_picker import construir_manual_picker
from .runner import (
    construir_manual_general,
    construir_manual_maestro_imprimible,
    generar_todos_los_manuales,
)

__all__ = [
    "VERSION_PROC_ACTUAL",
    "agregar_ficha_boton",
    "agregar_fichas_modulo",
    "construir_cierre_manual_rol",
    "iniciar_manual_rol",
    "construir_manual_operador",
    "construir_manual_picker",
    "construir_manual_despachador",
    "construir_manual_administrador",
    "construir_manual_master",
    "construir_manual_consulta",
    "construir_manual_general",
    "construir_manual_maestro_imprimible",
    "generar_todos_los_manuales",
]
