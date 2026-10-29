"""Diálogos y ventanas modales de la interfaz de usuario."""

from .dlg_auth import (
    mostrar_inicio_sesion,
    mostrar_cambio_clave_obligatorio,
    mostrar_cambiar_mi_clave,
    mostrar_mi_perfil,
    mostrar_configuracion_inicial,
)
from .dlg_clientes import mostrar_dialogo_gestion_clientes
from .dlg_usuarios import mostrar_dialogo_gestion_usuarios
from .dlg_smtp import mostrar_dialogo_configuracion_smtp
from .dlg_backup import mostrar_dialogo_backup
from .dlg_productos import (
    mostrar_dialogo_gestion_productos,
    mostrar_dialogo_historial_movimientos_stock,
    mostrar_dialogo_formulario_producto,
)
from .dlg_escaner import mostrar_dialogo_escaner_qr_despacho
from .dlg_cierre import mostrar_dialogo_cierre_jornada
from .dlg_pedidos import (
    mostrar_dialogo_crear_pedido,
    mostrar_dialogo_confirmar_anulacion_pedido,
    mostrar_dialogo_editar_pedido,
    mostrar_dialogo_confirmar_desarmar_pedido,
)
from .dlg_historial_pedidos import (
    mostrar_historial_pedidos,
    mostrar_imprimir_descuentos,
)
from .dlg_email import (
    compartir_correo,
    compartir_whatsapp,
    enviar_correo_cierre,
    mostrar_dialogo_compartir_cierre,
    mostrar_dialogo_enviar_correo,
)
from .dlg_analytics import (
    mostrar_dashboard_metricas,
    mostrar_registro_auditoria,
    mostrar_estadisticas,
    mostrar_notificaciones_admin,
)
from .dlg_stock_ops import (
    generar_pedido_fabrica,
    mostrar_ingreso_fabrica,
    mostrar_descuento_mercado_full,
    mostrar_descuento_mercado_libre,
    mostrar_stock_fisico_operario,
    mostrar_comparativa_stock_fisico_admin,
)
from .dlg_inventario_vivo import mostrar_dialogo_inventario_vivo

__all__ = [
    # Auth & Profile
    "mostrar_inicio_sesion",
    "mostrar_cambio_clave_obligatorio",
    "mostrar_cambiar_mi_clave",
    "mostrar_mi_perfil",
    "mostrar_configuracion_inicial",
    # Clientes & Usuarios
    "mostrar_dialogo_gestion_clientes",
    "mostrar_dialogo_gestion_usuarios",
    # Config & Backup
    "mostrar_dialogo_configuracion_smtp",
    "mostrar_dialogo_backup",
    # Catálogo & Productos
    "mostrar_dialogo_gestion_productos",
    "mostrar_dialogo_historial_movimientos_stock",
    "mostrar_dialogo_formulario_producto",
    # Escáner & Despacho
    "mostrar_dialogo_escaner_qr_despacho",
    # Cierre de Jornada
    "mostrar_dialogo_cierre_jornada",
    # Pedidos
    "mostrar_dialogo_crear_pedido",
    "mostrar_dialogo_confirmar_anulacion_pedido",
    "mostrar_dialogo_editar_pedido",
    "mostrar_dialogo_confirmar_desarmar_pedido",
    "mostrar_historial_pedidos",
    "mostrar_imprimir_descuentos",
    # Correo & Compartir
    "compartir_correo",
    "compartir_whatsapp",
    "enviar_correo_cierre",
    "mostrar_dialogo_compartir_cierre",
    "mostrar_dialogo_enviar_correo",
    # Métricas & Auditoría
    "mostrar_dashboard_metricas",
    "mostrar_registro_auditoria",
    "mostrar_estadisticas",
    "mostrar_notificaciones_admin",
    # Operaciones de Stock & Fábrica
    "generar_pedido_fabrica",
    "mostrar_ingreso_fabrica",
    "mostrar_descuento_mercado_full",
    "mostrar_descuento_mercado_libre",
    "mostrar_stock_fisico_operario",
    "mostrar_comparativa_stock_fisico_admin",
    "mostrar_dialogo_inventario_vivo",
]
