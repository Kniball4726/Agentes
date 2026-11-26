"""Diálogo modal para Sincronización y Configuración de Mercado Libre API."""

import threading
from typing import Any
import flet as ft

from ...integrations.mercado_libre_api import (
    cargar_config_mercadolibre,
    consultar_ordenes_ml,
    descontar_orden_ml_api,
    guardar_config_mercadolibre,
    mapear_orden_ml_a_items,
    verificar_credenciales_ml,
)
from ..design import campo_secreto_seguro, colores_de, resolver_secreto
from ..theme import ROJO
from .mercadolibre_api_cards import (
    construir_contenido_dialogo_ml,
    construir_tarjeta_orden_ml,
)


def mostrar_dialogo_mercadolibre(interfaz: Any, _e: ft.Event | None = None) -> None:
    """Ventana para sincronizar desatendidamente pedidos de Mercado Libre y configurar la API."""
    if not interfaz.exigir_roles("administrador", "master"):
        return

    colores = colores_de(interfaz)
    cfg = cargar_config_mercadolibre()
    secret_guardado = str(cfg.get("client_secret", "") or "")
    access_guardado = str(cfg.get("access_token", "") or "")
    refresh_guardado = str(cfg.get("refresh_token", "") or "")

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
    input_client_secret = campo_secreto_seguro(
        "Client Secret",
        secret_guardado,
        dense=True,
    )
    input_seller_id = ft.TextField(
        label="Seller ID (ID de Vendedor)",
        value=cfg.get("seller_id", ""),
        hint_text="Ej: 123456789 (se completa automáticamente al probar conexión)",
        dense=True,
    )
    input_access_token = campo_secreto_seguro(
        "Access Token",
        access_guardado,
        dense=True,
        multiline=False,
    )
    input_refresh_token = campo_secreto_seguro(
        "Refresh Token",
        refresh_guardado,
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
        tok = resolver_secreto(input_access_token, cfg.get("access_token", "") or access_guardado)
        if not tok:
            texto_estado_config.value = "⚠️ Debes ingresar un Access Token para probar la conexión."
            texto_estado_config.color = colores.advertencia
            interfaz.page.update()
            return

        test_cfg = {
            "app_id": (input_app_id.value or "").strip(),
            "client_secret": resolver_secreto(input_client_secret, cfg.get("client_secret", "") or secret_guardado),
            "seller_id": (input_seller_id.value or "").strip(),
            "access_token": tok,
            "refresh_token": resolver_secreto(input_refresh_token, cfg.get("refresh_token", "") or refresh_guardado),
            "activo": bool(switch_activo.value),
        }
        texto_estado_config.value = "Comprobando conexión con Mercado Libre..."
        texto_estado_config.color = interfaz.secundario
        interfaz.page.update()

        ok, msg, data = verificar_credenciales_ml(test_cfg)
        if ok:
            texto_estado_config.value = f"✅ {msg}"
            texto_estado_config.color = colores.exito
            if data.get("id") and not input_seller_id.value:
                input_seller_id.value = str(data["id"])
        else:
            texto_estado_config.value = f"❌ {msg}"
            texto_estado_config.color = colores.error
        interfaz.page.update()

    def guardar_config_api(_e: ft.Event | None = None) -> None:
        nonlocal secret_guardado, access_guardado, refresh_guardado
        secret_guardado = resolver_secreto(input_client_secret, cfg.get("client_secret", "") or secret_guardado)
        access_guardado = resolver_secreto(input_access_token, cfg.get("access_token", "") or access_guardado)
        refresh_guardado = resolver_secreto(input_refresh_token, cfg.get("refresh_token", "") or refresh_guardado)
        nueva_cfg = {
            "app_id": (input_app_id.value or "").strip(),
            "client_secret": secret_guardado,
            "seller_id": (input_seller_id.value or "").strip(),
            "access_token": access_guardado,
            "refresh_token": refresh_guardado,
            "activo": bool(switch_activo.value),
            "filtro_estado": "paid",
            "horas_atras": 48,
            "auto_descontar": False,
            "ultima_sincronizacion": cfg.get("ultima_sincronizacion", ""),
        }
        guardar_config_mercadolibre(nueva_cfg)
        cfg.update(nueva_cfg)
        order_store = getattr(interfaz, "order_store", None)
        if order_store and hasattr(order_store, "registrar_auditoria"):
            usr_nom = getattr(getattr(interfaz, "usuario_actual", None), "username", "Master")
            order_store.registrar_auditoria(
                usr_nom,
                "CONFIG_MERCADOLIBRE_ACTUALIZADA",
                f"App ID: {nueva_cfg['app_id'] or 'N/A'} (activo={nueva_cfg['activo']})",
            )
        interfaz.notificar("Configuración de Mercado Libre API guardada correctamente.")

    def renderizar_lista_ordenes() -> None:
        lista_ordenes_view.controls.clear()
        if not ordenes_cargadas:
            lista_ordenes_view.controls.append(
                ft.Container(
                    padding=20,
                    alignment=ft.Alignment.CENTER,
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

            def on_check_change(e: ft.Event, r=ref):
                seleccionados[r] = bool(e.control.value)

            tarjeta = construir_tarjeta_orden_ml(
                interfaz=interfaz,
                ord_info=ord_info,
                ya_procesado=ya_procesado,
                seleccionada=seleccionada,
                on_check_change=on_check_change,
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

            from ...inventory import StockManager
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
            from ...inventory import StockManager
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

        threading.Thread(target=tarea_descuento_masivo, daemon=True).start()

    es_master = bool(interfaz.usuario_actual and interfaz.usuario_actual.role == "master")
    contenido_dialogo = construir_contenido_dialogo_ml(
        interfaz=interfaz,
        es_master=es_master,
        on_sincronizar=ejecutar_sincronizacion_api,
        chk_solo_pendientes=chk_solo_pendientes,
        texto_resumen_sincronizacion=texto_resumen_sincronizacion,
        lista_ordenes_view=lista_ordenes_view,
        controles_config=[
            input_app_id,
            input_client_secret,
            input_seller_id,
            input_access_token,
            input_refresh_token,
            switch_activo,
        ],
        texto_estado_config=texto_estado_config,
        on_probar_conexion=probar_conexion_api,
        on_guardar_config=guardar_config_api,
    )

    ancho_dlg = interfaz.ancho_adaptable(680) if hasattr(interfaz, "ancho_adaptable") else 680
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
            content=contenido_dialogo,
            width=ancho_dlg,
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
            interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    interfaz.page.show_dialog(dialogo)
    # Si ya tiene token, disparar sincronización inicial automática
    if cfg.get("access_token") and cfg.get("activo"):
        ejecutar_sincronizacion_api()
