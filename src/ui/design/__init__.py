"""Sistema de diseño unificado de la UI Flet (tokens, botones, diálogos y formularios).

Importar desde aquí en lugar de definir estilos ad-hoc en cada diálogo::

    from ..design import boton_cancelar, boton_primario, confirmar_accion_destructiva
"""

from .buttons import (
    COLOR_PELIGRO,
    MARCA_NEUTRO,
    MARCA_PELIGRO,
    MARCA_PRIMARIO,
    boton_cancelar,
    boton_dialogo_semantico,
    boton_peligro,
    boton_primario,
    es_accion_neutra,
    es_accion_peligrosa,
    fijar_ocupado,
)
from .dialogs import (
    MENSAJE_SIN_PERMISO,
    boton_confirmacion,
    confirmar_accion_destructiva,
    crear_dialogo_estandar,
    encabezado_dialogo,
)
from .forms import (
    FORMATO_FECHA,
    HINT_SECRETO_GUARDADO,
    MASCARA_SECRETO,
    campo_numerico,
    campo_secreto_seguro,
    limpiar_errores,
    marcar_error,
    parsear_fecha_ddmmaaaa,
    resolver_secreto,
    validar_entero_no_negativo,
    validar_fecha_ddmmaaaa,
)
from .responsive import (
    ancho_viewport,
    barra_chips_responsiva,
    es_viewport_estrecho,
    fila_cabecera_responsiva,
    grilla_tarjetas_responsiva,
    par_accion_tarjeta,
    resolver_columnas_grilla,
)
from .tokens import ColoresSemanticos, colores_de, colores_semanticos, fondo_tenue, tono_legible

__all__ = [
    "COLOR_PELIGRO",
    "ColoresSemanticos",
    "FORMATO_FECHA",
    "HINT_SECRETO_GUARDADO",
    "MARCA_NEUTRO",
    "MARCA_PELIGRO",
    "MARCA_PRIMARIO",
    "MASCARA_SECRETO",
    "MENSAJE_SIN_PERMISO",
    "ancho_viewport",
    "barra_chips_responsiva",
    "boton_cancelar",
    "boton_confirmacion",
    "boton_dialogo_semantico",
    "boton_peligro",
    "boton_primario",
    "campo_numerico",
    "campo_secreto_seguro",
    "colores_de",
    "colores_semanticos",
    "confirmar_accion_destructiva",
    "crear_dialogo_estandar",
    "encabezado_dialogo",
    "es_accion_neutra",
    "es_accion_peligrosa",
    "es_viewport_estrecho",
    "fijar_ocupado",
    "fila_cabecera_responsiva",
    "fondo_tenue",
    "grilla_tarjetas_responsiva",
    "limpiar_errores",
    "marcar_error",
    "par_accion_tarjeta",
    "parsear_fecha_ddmmaaaa",
    "resolver_columnas_grilla",
    "resolver_secreto",
    "tono_legible",
    "validar_entero_no_negativo",
    "validar_fecha_ddmmaaaa",
]
