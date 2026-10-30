"""Diálogo modal para Sincronización y Configuración de Mercado Libre API."""

from datetime import datetime
from typing import Any
import flet as ft

from ...mercado_libre_api import (
    cargar_config_mercadolibre,
    consultar_ordenes_ml,
    descontar_orden_ml_api,
    guardar_config_mercadolibre,
    mapear_orden_ml_a_items,
    verificar_credenciales_ml,
)
from ..theme import ROJO


def mostrar_dialogo_mercadolibre(interfaz: Any, _e: ft.Event | None = None) -> None:
    """Ventana para sincronizar desatendidamente pedidos de Mercado Libre y configurar la API."""
    if not interfaz.exigir_roles("operador", "administrador", "master"):
        return

    cfg = cargar_config_mercadolibre()

    # Variables de estado de la vista
    ordenes_cargadas: list[dict[str, Any]] = []
    seleccionados: dict[str, bool] = {}

    # Controles de Configuración
    input_app_id = ft.TextField(
        label="App ID (Client ID)",
        value=cfg.get("app_id", ""),
        hint_text="Ej: 1234567890123456",
        dense=True,
    )
    input_client_secret = ft.TextField(
        label="Client Secret",
        value=cfg.get("client_secret", ""),
        password=True,
        can_reveal_password=True,
        dense=True,
    )
    input_seller_id = ft.TextField(
        label="Seller ID (ID de Vendedor)",
        value=cfg.get("seller_id", ""),
        hint_text="Ej: 123456789 (se completa automáticamente al probar conexión)",
        dense=True,
    )
    input_access_token = ft.TextField(
        label="Access Token",
        value=cfg.get("access_token", ""),
        password=True,
        can_reveal_password=True,
        dense=True,
        multiline=False,
    )
    input_refresh_token = ft.TextField(
        label="Refresh Token",
        value=cfg.get("refresh_token", ""),
        password=True,
        can_reveal_password=True,
        dense=True,
    )
    switch_activo = ft.Switch(
        label="Habilitar sincronización con Mercado Libre",
        value=cfg.get("activo", False),
    )
    texto_estado_config = ft.Text("", size=12)

    # Controles de Lista de Órdenes
    lista_ordenes_view = ft.ListView(
        expand=True,
        spacing=8,
        height=320,
    )
    texto_resumen_sincronizacion = ft.Text(
        "Presiona 'Sincronizar Ahora' para consultar las órdenes recientes en Mercado Libre.",
        size=12,
        color=interfaz.secundario,
    )
    chk_solo_pendientes = ft.Checkbox(
        label="Mostrar solo órdenes pendientes de descuento",
        value=True,
    )

    def probar_conexion_api(_e: ft.Event | None = None) -> None:
        tok = (input_access_token.value or "").strip()
        if not tok:
            texto_estado_config.value = "⚠️ Debes ingresar un Access Token para probar la conexión."
            texto_estado_config.color = ft.Colors.AMBER_400
            interfaz.page.update()
            return

        test_cfg = {
            "app_id": (input_app_id.value or "").strip(),
            "client_secret": (input_client_secret.value or "").strip(),
            "seller_id": (input_seller_id.value or "").strip(),
            "access_token": tok,
            "refresh_token": (input_refresh_token.value or "").strip(),
            "activo": bool(switch_activo.value),
        }
        texto_estado_config.value = "Comprobando conexión con Mercado Libre..."
        texto_estado_config.color = interfaz.secundario
        interfaz.page.update()

        ok, msg, data = verificar_credenciales_ml(test_cfg)
        if ok:
            texto_estado_config.value = f"✅ {msg}"
            texto_estado_config.color = ft.Colors.GREEN_400
            if data.get("id") and not input_seller_id.value:
                input_seller_id.value = str(data["id"])
        else:
            texto_estado_config.value = f"❌ {msg}"
            texto_estado_config.color = ft.Colors.RED_400
        interfaz.page.update()

    def guardar_config_api(_e: ft.Event | None = None) -> None:
        nueva_cfg = {
            "app_id": (input_app_id.value or "").strip(),
            "client_secret": (input_client_secret.value or "").strip(),
            "seller_id": (input_seller_id.value or "").strip(),
            "access_token": (input_access_token.value or "").strip(),
            "refresh_token": (input_refresh_token.value or "").strip(),
            "activo": bool(switch_activo.value),
            "filtro_estado": "paid",
            "horas_atras": 48,
            "auto_descontar": False,
            "ultima_sincronizacion": cfg.get("ultima_sincronizacion", ""),
        }
        guardar_config_mercadolibre(nueva_cfg)
        cfg.update(nueva_cfg)
        interfaz.notificar("Configuración de Mercado Libre API guardada correctamente.")

    def renderizar_lista_ordenes() -> None:
        lista_ordenes_view.controls.clear()
        if not ordenes_cargadas:
            lista_ordenes_view.controls.append(
                ft.Container(
                    padding=20,
                    alignment=ft.alignment.center,
                    content=ft.Text(
                        "No hay órdenes para mostrar en este período.",
                        color=interfaz.secundario,
                        size=13,
                    ),
                )
            )
            interfaz.page.update()
            return

        solo_pendientes = bool(chk_solo_pendientes.value)

        for ord_info in ordenes_cargadas:
            ref = ord_info["ref_pedido"]
            ya_procesado = interfaz.order_store.existe_nota_pedido(ref)

            if solo_pendientes and ya_procesado:
                continue

            seleccionada = seleccionados.get(ref, not ya_procesado and ord_info["stock_suficiente"])

            # Chips de estado
            if ya_procesado:
                chip_estado = ft.Container(
                    content=ft.Text("YA DESCONTADO", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_300),
                    bgcolor=ft.Colors.GREY_800,
                    padding=ft.Padding(6, 2, 6, 2),
                    border_radius=4,
                )
            elif not ord_info["stock_suficiente"]:
                chip_estado = ft.Container(
                    content=ft.Text("FALTA STOCK", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_100),
                    bgcolor=ft.Colors.RED_900,
                    padding=ft.Padding(6, 2, 6, 2),
                    border_radius=4,
                )
            else:
                chip_estado = ft.Container(
                    content=ft.Text("LISTO P/ DESCUENTO", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_100),
                    bgcolor=ft.Colors.GREEN_800,
                    padding=ft.Padding(6, 2, 6, 2),
                    border_radius=4,
                )

            def on_check_change(e: ft.Event, r=ref):
                seleccionados[r] = bool(e.control.value)

            filas_items = []
            for it in ord_info["items_coincidentes"]:
                stk_post = it["stock_actual"] - it["cantidad"]
                stk_color = ft.Colors.RED_400 if stk_post < 0 else interfaz.secundario
                filas_items.append(
                    ft.Row(
                        [
                            ft.Text(f"[{it['codigo']}]", weight=ft.FontWeight.BOLD, size=11, width=70),
                            ft.Text(it["nombre"], size=11, expand=True, no_wrap=True),
                            ft.Text(f"-{it['cantidad']} un.", color=ft.Colors.RED_400, weight=ft.FontWeight.BOLD, size=11, width=60),
                            ft.Text(f"Stock: {it['stock_actual']} -> {stk_post}", size=11, color=stk_color, width=130),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    )
                )

            for no_it in ord_info["items_no_coincidentes"]:
                filas_items.append(
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.WARNING_AMBER, color=ft.Colors.AMBER_400, size=14),
                            ft.Text(f"No reconocido: {no_it['titulo']} (Cant: {no_it['cantidad']})", size=11, color=ft.Colors.AMBER_400, expand=True),
                        ],
                    )
                )

            tarjeta = ft.Container(
                bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
                border=ft.Border.all(1, ft.Colors.WHITE_24 if interfaz.modo_oscuro else ft.Colors.GREY_300),
                border_radius=8,
                padding=10,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Checkbox(
                                    value=seleccionada,
                                    disabled=ya_procesado,
                                    on_change=on_check_change,
                                ),
                                ft.Column(
                                    [
                                        ft.Text(f"{ref} · {ord_info['cliente']}", weight=ft.FontWeight.BOLD, size=12),
                                        ft.Text(f"Fecha: {ord_info['fecha']} | {ord_info['total_unidades']} un. | Total: ${ord_info['total_importe']:,.2f}", size=11, color=interfaz.secundario),
                                    ],
                                    expand=True,
                                    spacing=2,
                                ),
                                chip_estado,
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Container(
                            padding=ft.Padding(left=28, top=4, right=4, bottom=4),
                            content=ft.Column(filas_items, spacing=2),
                        ),
                    ],
                    spacing=4,
                ),
            )
            lista_ordenes_view.controls.append(tarjeta)

        interfaz.page.update()

    chk_solo_pendientes.on_change = lambda _e: renderizar_lista_ordenes()

    def ejecutar_sincronizacion_api(_e: ft.Event | None = None) -> None:
        texto_resumen_sincronizacion.value = "Consultando órdenes recientes en la API de Mercado Libre..."
        texto_resumen_sincronizacion.color = interfaz.secundario
        interfaz.page.update()

        def tarea_sincronizar() -> None:
            ok, msg, ordenes_raw = consultar_ordenes_ml(cfg)
            if not ok:
                texto_resumen_sincronizacion.value = f"❌ {msg}"
                texto_resumen_sincronizacion.color = ft.Colors.RED_400
                interfaz.page.update()
                return

            from ...stock_manager import StockManager
            sm = StockManager(interfaz.menu.ruta_excel_base)

            ordenes_cargadas.clear()
            seleccionados.clear()

            nuevas_pendientes = 0
            for ord_data in ordenes_raw:
                mapeada = mapear_orden_ml_a_items(ord_data, sm.catalogo)
                ordenes_cargadas.append(mapeada)
                ref = mapeada["ref_pedido"]
                ya_descontado = interfaz.order_store.existe_nota_pedido(ref)
                if not ya_descontado:
                    nuevas_pendientes += 1
                    seleccionados[ref] = mapeada["stock_suficiente"]
                else:
                    seleccionados[ref] = False

            texto_resumen_sincronizacion.value = (
                f"✅ Se sincronizaron {len(ordenes_cargadas)} órdenes ({nuevas_pendientes} listas para descontar)."
            )
            texto_resumen_sincronizacion.color = ft.Colors.GREEN_400
            renderizar_lista_ordenes()

        import threading
        threading.Thread(target=tarea_sincronizar, daemon=True).start()

    def confirmar_descuento_seleccionadas(_e: ft.Event | None = None) -> None:
        ordenes_a_descontar = [
            o for o in ordenes_cargadas
            if seleccionados.get(o["ref_pedido"], False)
            and not interfaz.order_store.existe_nota_pedido(o["ref_pedido"])
        ]

        if not ordenes_a_descontar:
            interfaz.notificar("No has seleccionado ninguna orden nueva con stock para descontar.")
            return

        armador = interfaz.usuario_actual.nombre_identificador if interfaz.usuario_actual else "Operario"

        def tarea_descuento_masivo() -> None:
            from ...stock_manager import StockManager
            sm = StockManager(interfaz.menu.ruta_excel_base)

            exitos = 0
            errores = []
            total_unidades = 0

            for ord_info in ordenes_a_descontar:
                ok, msg = descontar_orden_ml_api(ord_info, sm, interfaz.order_store, armador=armador)
                if ok:
                    exitos += 1
                    total_unidades += ord_info["total_unidades"]
                else:
                    errores.append(f"{ord_info['ref_pedido']}: {msg}")

            interfaz.actualizar_listas()
            if hasattr(interfaz, "actualizar_estado"):
                interfaz.actualizar_estado()

            renderizar_lista_ordenes()
            resumen_msg = f"Se descontaron con éxito {exitos} órdenes de Mercado Libre ({total_unidades} un.)."
            if errores:
                resumen_msg += f" Hubo {len(errores)} con advertencias."
            interfaz.notificar(resumen_msg)

        import threading
        threading.Thread(target=tarea_descuento_masivo, daemon=True).start()

    # Contenedor de Pestañas
    vista_ordenes = ft.Column(
        [
            ft.Row(
                [
                    ft.Button(
                        "Sincronizar Ahora",
                        icon=ft.Icons.SYNC,
                        bgcolor=ROJO,
                        color=ft.Colors.WHITE,
                        on_click=ejecutar_sincronizacion_api,
                    ),
                    chk_solo_pendientes,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            texto_resumen_sincronizacion,
            ft.Divider(height=10, color=interfaz.borde),
            lista_ordenes_view,
        ],
        spacing=6,
        expand=True,
    )

    vista_config = ft.Column(
        [
            ft.Text(
                "Configuración de credenciales de la aplicación en Mercado Libre Developers:",
                size=12,
                color=interfaz.secundario,
            ),
            input_app_id,
            input_client_secret,
            input_seller_id,
            input_access_token,
            input_refresh_token,
            switch_activo,
            texto_estado_config,
            ft.Row(
                [
                    ft.OutlinedButton("Probar Conexión", icon=ft.Icons.CHECK_CIRCLE, on_click=probar_conexion_api),
                    ft.Button("Guardar Configuración", icon=ft.Icons.SAVE, bgcolor=ROJO, color=ft.Colors.WHITE, on_click=guardar_config_api),
                ],
                alignment=ft.MainAxisAlignment.END,
            ),
        ],
        spacing=8,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    tabs = ft.Tabs(
        length=2,
        expand=True,
        content=ft.Column(
            expand=True,
            controls=[
                ft.TabBar(
                    tabs=[
                        ft.Tab(label="Órdenes Sincronizadas", icon=ft.Icons.LIST_ALT),
                        ft.Tab(label="Credenciales API", icon=ft.Icons.SETTINGS),
                    ]
                ),
                ft.TabBarView(
                    expand=True,
                    controls=[vista_ordenes, vista_config],
                ),
            ],
        ),
    )

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.CLOUD_SYNC, color=ROJO),
                ft.Text("Mercado Libre API · Sincronización Oficial", size=16, weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Container(
            content=tabs,
            width=680,
            height=460,
        ),
        actions=[
            ft.Button(
                "Descontar Seleccionadas",
                icon=ft.Icons.CHECK,
                bgcolor=ROJO,
                color=ft.Colors.WHITE,
                on_click=confirmar_descuento_seleccionadas,
            ),
            ft.TextButton("Cerrar", on_click=lambda _e: interfaz.page.pop_dialog()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    interfaz.page.show_dialog(dialogo)
    # Si ya tiene token, disparar sincronización inicial automática
    if cfg.get("access_token") and cfg.get("activo"):
        ejecutar_sincronizacion_api()
