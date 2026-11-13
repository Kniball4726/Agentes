"""Fachada de diálogos y pantallas de autenticación, perfil y configuración inicial."""

from .auth_account import (
    mostrar_cambiar_mi_clave,
    mostrar_cambio_clave_obligatorio,
    mostrar_configuracion_inicial,
    mostrar_mi_perfil,
)
from .auth_login import mostrar_inicio_sesion
from .auth_styles import (
    _borde_espejo,
    _estilizar_campo_espejo,
    _gradiente_fondo_espejo,
    _gradiente_tarjeta_espejo,
    _sombra_espejo,
)

__all__ = [
    "mostrar_inicio_sesion",
    "mostrar_cambio_clave_obligatorio",
    "mostrar_cambiar_mi_clave",
    "mostrar_mi_perfil",
    "mostrar_configuracion_inicial",
    "_borde_espejo",
    "_sombra_espejo",
    "_gradiente_fondo_espejo",
    "_gradiente_tarjeta_espejo",
    "_estilizar_campo_espejo",
]
