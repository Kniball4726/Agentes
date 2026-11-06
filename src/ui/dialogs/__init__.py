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
from .dlg_cierre import (
    mostrar_dialogo_cierre_jornada,
    mostrar_dialogo_cierres_operarios,
    mostrar_detalle_pedidos_cierre,
)
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
from .dlg_mercadolibre_descuento import (
    MercadoLibreScannerComponent,
    MercadoLibreDocxComponent,
)
from .dlg_inventario_vivo import mostrar_dialogo_inventario_vivo
from .dlg_command_palette import mostrar_command_palette
from .dlg_quiebre import actualizar_alerta_quiebre, mostrar_detalle_quiebre
from .dlg_restaurar import confirmar_restaurar, restaurar_documentos
from .dlg_preferencias import mostrar_dialogo_preferencias
from .dlg_movimientos_rapidos import (
    mostrar_dialogo_ingreso_rapido,
    mostrar_dialogo_salida_rapida,
    MotivoIngresoRapido,
    MotivoSalidaRapida,
)

__all__ = [
    # Auth & Profile
    "mostrar_inicio_sesion",
    "mostrar_cambio_clave_obligatorio",
    "mostrar_cambiar_mi_clave",
    "mostrar_mi_perfil",
    "mostrar_configuracion_inicial",
    "mostrar_dialogo_preferencias",
    # Clientes & Usuarios
    "mostrar_dialogo_gestion_clientes",
    "mostrar_dialogo_gestion_usuarios",
    # Config & Backup & Restauración
    "mostrar_dialogo_configuracion_smtp",
    "mostrar_dialogo_backup",
    "confirmar_restaurar",
    # Catálogo & Productos
    "mostrar_dialogo_gestion_productos",
    "mostrar_dialogo_historial_movimientos_stock",
    "mostrar_dialogo_formulario_producto",
    # Escáner & Despacho
    "mostrar_dialogo_escaner_qr_despacho",
    # Cierre de Jornada
    "mostrar_dialogo_cierre_jornada",
    "mostrar_dialogo_cierres_operarios",
    "mostrar_detalle_pedidos_cierre",
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
    # Métricas & Auditoría & Quiebres
    "mostrar_dashboard_metricas",
    "mostrar_registro_auditoria",
    "mostrar_estadisticas",
    "mostrar_notificaciones_admin",
    "actualizar_alerta_quiebre",
    "mostrar_detalle_quiebre",
    # Operaciones de Stock & Fábrica
    "generar_pedido_fabrica",
    "mostrar_ingreso_fabrica",
    "mostrar_descuento_mercado_full",
    "mostrar_descuento_mercado_libre",
    "MercadoLibreScannerComponent",
    "MercadoLibreDocxComponent",
    "mostrar_stock_fisico_operario",
    "mostrar_comparativa_stock_fisico_admin",
    "mostrar_dialogo_inventario_vivo",
    "mostrar_command_palette",
    "mostrar_dialogo_ingreso_rapido",
    "mostrar_dialogo_salida_rapida",
    "MotivoIngresoRapido",
    "MotivoSalidaRapida",
]
