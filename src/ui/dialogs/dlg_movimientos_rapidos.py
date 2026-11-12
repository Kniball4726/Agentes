"""Diálogo modal para Entrada Rápida y Salida Rápida de Stock (Operadores).

Permite el escaneo rápido de productos con pistola de código de barras o ingreso de SKU,
solicitando motivo obligatorio tipificado (Enum) y actualizando inmediatamente
el inventario en memoria, base de datos SQLite, registro de movimientos y auditoría.
Incluye soporte para modo continuo (pistoleo automático) e integración con Webhooks.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

import flet as ft

from ..theme import ROJO
from ...webhook_manager import despachar_evento_webhook


class MotivoIngresoRapido(str, Enum):
    DEVOLUCION_CLIENTE = "Devolución de Cliente"
    MOVIMIENTO_INTERNO = "Movimiento Interno"
    SOBRANTE_INVENTARIO = "Sobrante de Inventario / Ajuste"
    MUESTRA_SIN_REMITO = "Muestra / Ingreso Especial"


class MotivoSalidaRapida(str, Enum):
    ROTURA_MERMA = "Rotura / Merma / Dañado"
    MUESTRA_COMERCIAL = "Muestra Comercial / Exhibición"
    USO_INTERNO = "Consumo / Uso Interno"
    DEVOLUCION_PROVEEDOR = "Devolución a Proveedor"
    FALTANTE_INVENTARIO = "Faltante / Ajuste de Inventario"


def mostrar_dialogo_ingreso_rapido(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Abre el diálogo modal de Entrada Rápida de Stock."""
    _mostrar_dialogo_movimiento_rapido(interfaz, tipo="ingreso")


def mostrar_dialogo_salida_rapida(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Abre el diálogo modal de Salida Rápida de Stock."""
    _mostrar_dialogo_movimiento_rapido(interfaz, tipo="salida")


def _mostrar_dialogo_movimiento_rapido(interfaz: Any, tipo: str = "ingreso") -> None:
    """Genera y muestra el diálogo para ingreso o salida rápida de mercadería."""
    if not getattr(interfaz, "usuario_actual", None) or not getattr(interfaz, "page", None):
        return

    rol = str(getattr(interfaz.usuario_actual, "role", "")).lower()
    if rol not in ("master", "administrador", "operador", "picker"):
        interfaz.notificar(
            "Tu rol de usuario no tiene permisos para registrar movimientos rápidos de stock.",
            ft.Colors.RED_700,
        )
        return

    es_ingreso = tipo == "ingreso"
    color_tema = ft.Colors.GREEN_700 if es_ingreso else ft.Colors.AMBER_800
    icono_accion = ft.Icons.INPUT if es_ingreso else ft.Icons.OUTBOX
    titulo_texto = "Entrada Rápida de Stock" if es_ingreso else "Salida Rápida de Stock"
    enum_motivos = MotivoIngresoRapido if es_ingreso else MotivoSalidaRapida

    producto_seleccionado: dict[str, Any] = {}

    # Campos UI
    texto_estado = ft.Text("", size=12, italic=True)

    switch_modo_continuo = ft.Switch(
        label="Modo pistoleo continuo (automático)",
        value=False,
        active_color=color_tema,
        tooltip="Aplica el movimiento al disparar el código de barras sin presionar Confirmar",
    )

    txt_codigo_busqueda = ft.TextField(
        label="Escanear Código de Barras o ingresar SKU",
        hint_text="Enfoque aquí con la lectora o escriba y presione Enter",
        autofocus=True,
        dense=True,
        text_size=13,
        expand=True,
    )

    txt_cantidad = ft.TextField(
        value="1",
        label="Cantidad",
        text_align=ft.TextAlign.CENTER,
        dense=True,
        width=100,
        text_size=14,
    )

    dropdown_motivo = ft.Dropdown(
        label="Motivo obligatorio *",
        hint_text="Seleccione un motivo justificado...",
        dense=True,
        text_size=13,
        expand=True,
        options=[ft.dropdown.Option(m.value) for m in enum_motivos],
    )

    txt_observaciones = ft.TextField(
        label="Observaciones / Detalle adicional (opcional)",
        hint_text="Ej: Remito provisorio, cliente García, caja golpeada...",
        multiline=True,
        min_lines=2,
        max_lines=3,
        dense=True,
        text_size=12,
    )

    # Tarjeta de producto encontrado
    lbl_prod_nombre = ft.Text("Ningún producto seleccionado", size=13, weight=ft.FontWeight.BOLD, color=interfaz.texto)
    lbl_prod_codigo = ft.Text("SKU: -", size=12, color=interfaz.secundario)
    lbl_prod_barras = ft.Text("Código de barras: -", size=12, color=interfaz.secundario)
    lbl_prod_stock_actual = ft.Text("Stock actual: -", size=13, weight=ft.FontWeight.W_500, color=interfaz.texto)
    lbl_prod_stock_proyectado = ft.Text("Stock resultante: -", size=13, weight=ft.FontWeight.BOLD, color=color_tema)

    tarjeta_producto = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.INVENTORY_2_OUTLINED, size=20, color=color_tema),
                        lbl_prod_nombre,
                    ],
                    spacing=8,
                ),
                ft.Row(
                    [lbl_prod_codigo, lbl_prod_barras],
                    spacing=20,
                ),
                ft.Row(
                    [lbl_prod_stock_actual, ft.Icon(ft.Icons.ARROW_FORWARD, size=14, color=interfaz.secundario), lbl_prod_stock_proyectado],
                    spacing=10,
                ),
            ],
            spacing=4,
            tight=True,
        ),
        padding=10,
        border_radius=8,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.3, interfaz.borde)),
        bgcolor=ft.Colors.with_opacity(0.04, interfaz.texto),
    )

    def _safe_update(ctrl: Any) -> None:
        if getattr(interfaz, "page", None):
            try:
                ctrl.update()
            except Exception:
                pass

    def _obtener_cantidad_int() -> int:
        try:
            val = int(str(txt_cantidad.value or "").strip())
            return max(1, val)
        except Exception:
            return 1

    def _actualizar_proyeccion() -> None:
        if not producto_seleccionado:
            lbl_prod_stock_proyectado.value = "Stock resultante: -"
            return
        qty = _obtener_cantidad_int()
        actual = int(producto_seleccionado.get("stock_actual", 0))
        resultante = (actual + qty) if es_ingreso else (actual - qty)
        lbl_prod_stock_proyectado.value = f"Stock resultante: {resultante} u."
        if not es_ingreso and resultante < 0:
            lbl_prod_stock_proyectado.color = ft.Colors.RED_600
        else:
            lbl_prod_stock_proyectado.color = color_tema
        _safe_update(tarjeta_producto)

    def _ejecutar_transaccion(codigo: str, nombre: str, qty: int, motivo: str, obs: str, cerrar_al_final: bool = True) -> bool:
        """Aplica la transacción de stock, historial, auditoría y webhooks."""
        usuario_nom = getattr(interfaz.usuario_actual, "nombre_identificador", None) or getattr(interfaz.usuario_actual, "username", "Operador")
        sm = getattr(interfaz, "stock_manager", None)
        if not sm:
            texto_estado.value = "Error crítico: Gestor de stock no encontrado."
            texto_estado.color = ft.Colors.RED_600
            _safe_update(texto_estado)
            return False

        cantidad_ajuste = qty if es_ingreso else -qty

        try:
            # 1. Ajuste atómico en catálogo y SQLite
            sm.registrar_ingreso_fabrica({codigo: cantidad_ajuste}, sobrescribir=False)

            # 2. Historial de movimientos
            mtype = "ingreso_rapido" if es_ingreso else "salida_rapida"
            detalle_mov = f"[{motivo}] {obs}".strip()
            if hasattr(sm, "product_store") and sm.product_store:
                sm.product_store.register_movements(
                    [(codigo, nombre, cantidad_ajuste, mtype)],
                    usuario=usuario_nom,
                    detalle=detalle_mov,
                )

            # 3. Log de auditoría
            if hasattr(interfaz, "order_store") and interfaz.order_store:
                accion_audit = "INGRESO_RAPIDO" if es_ingreso else "SALIDA_RAPIDA"
                detalle_audit = f"[{motivo}] {codigo} ({nombre}) x{qty} u. - {obs}".strip()
                interfaz.order_store.registrar_auditoria(
                    usuario=usuario_nom,
                    accion=accion_audit,
                    detalle=detalle_audit,
                )

            # 4. Despacho asíncrono de Webhook
            try:
                despachar_evento_webhook(
                    "MOVIMIENTO_RAPIDO",
                    {
                        "tipo": "ingreso" if es_ingreso else "salida",
                        "codigo": codigo,
                        "nombre": nombre,
                        "cantidad": qty,
                        "motivo": motivo,
                        "usuario": usuario_nom,
                    },
                )
            except Exception:
                pass

            msg_tipo = "Entrada registrada" if es_ingreso else "Salida registrada"
            interfaz.notificar(
                f"✅ {msg_tipo}: {codigo} ({qty} u.) por '{motivo}'",
                color_tema,
            )

            # Refrescar UI general
            if hasattr(interfaz, "actualizar_estado"):
                try:
                    interfaz.actualizar_estado()
                except Exception:
                    pass

            if cerrar_al_final:
                _al_cerrar()
            return True

        except Exception as ex:
            texto_estado.value = f"Error al registrar movimiento: {ex}"
            texto_estado.color = ft.Colors.RED_600
            _safe_update(texto_estado)
            return False

    def _buscar_producto(_e: Any = None) -> None:
        query = (txt_codigo_busqueda.value or "").strip()
        if not query:
            return

        sm = getattr(interfaz, "stock_manager", None)
        if not sm:
            texto_estado.value = "Gestor de stock no disponible."
            texto_estado.color = ft.Colors.RED_600
            _safe_update(texto_estado)
            return

        row = None
        if hasattr(sm, "buscar_producto_por_codigo_o_barras"):
            row = sm.buscar_producto_por_codigo_o_barras(query)
        elif hasattr(sm, "product_store") and sm.product_store:
            row = sm.product_store.find_product_by_code_or_barcode(query)

        if not row:
            texto_estado.value = f"❌ Producto '{query}' no encontrado en el catálogo."
            texto_estado.color = ft.Colors.RED_600
            producto_seleccionado.clear()
            lbl_prod_nombre.value = "Ningún producto seleccionado"
            lbl_prod_codigo.value = "SKU: -"
            lbl_prod_barras.value = "Código de barras: -"
            lbl_prod_stock_actual.value = "Stock actual: -"
            lbl_prod_stock_proyectado.value = "Stock resultante: -"
            if hasattr(interfaz, "reproducir_sonido"):
                interfaz.reproducir_sonido("error")
        else:
            codigo = row["code"] if "code" in row.keys() else row[0]
            nombre = row["name"] if "name" in row.keys() else row[1]
            barcode = row["barcode"] if "barcode" in row.keys() else ""

            stock_actual = 0
            if hasattr(sm, "catalogo") and codigo in sm.catalogo:
                stock_actual = int(sm.catalogo[codigo][2])
            elif "stock" in row.keys():
                stock_actual = int(row["stock"])

            producto_seleccionado["codigo"] = codigo
            producto_seleccionado["nombre"] = nombre
            producto_seleccionado["barcode"] = barcode
            producto_seleccionado["stock_actual"] = stock_actual

            lbl_prod_nombre.value = str(nombre)
            lbl_prod_codigo.value = f"SKU: {codigo}"
            lbl_prod_barras.value = f"Código de barras: {barcode or 'Sin código'}"
            lbl_prod_stock_actual.value = f"Stock actual: {stock_actual} u."
            texto_estado.value = "✅ Producto identificado correctamente."
            texto_estado.color = ft.Colors.GREEN_600
            _actualizar_proyeccion()

            # En modo continuo: si el motivo ya está seleccionado, ejecutar de inmediato
            if switch_modo_continuo.value:
                motivo = dropdown_motivo.value
                if not motivo:
                    texto_estado.value = "⚠️ En modo continuo debes preseleccionar el motivo primero."
                    texto_estado.color = ft.Colors.RED_600
                else:
                    qty = _obtener_cantidad_int()
                    obs = (txt_observaciones.value or "").strip()
                    ok = _ejecutar_transaccion(codigo, nombre, qty, motivo, obs, cerrar_al_final=False)
                    if ok:
                        if hasattr(interfaz, "reproducir_sonido"):
                            interfaz.reproducir_sonido("exito")
                        texto_estado.value = f"⚡ {('Entrada' if es_ingreso else 'Salida')} automática: {codigo} x{qty}. Listo para siguiente disparo."
                        texto_estado.color = color_tema
                        txt_codigo_busqueda.value = ""
                        try:
                            txt_codigo_busqueda.focus()
                        except Exception:
                            pass
                        _safe_update(txt_codigo_busqueda)

        _safe_update(texto_estado)
        _safe_update(tarjeta_producto)

    txt_codigo_busqueda.on_submit = _buscar_producto

    def _modificar_cantidad(delta: int) -> None:
        actual = _obtener_cantidad_int()
        nuevo = max(1, actual + delta)
        txt_cantidad.value = str(nuevo)
        _safe_update(txt_cantidad)
        _actualizar_proyeccion()

    def _fijar_cantidad(cant: int) -> None:
        txt_cantidad.value = str(max(1, cant))
        _safe_update(txt_cantidad)
        _actualizar_proyeccion()

    txt_cantidad.on_change = lambda _e: _actualizar_proyeccion()

    def _al_cerrar(_e: Any = None) -> None:
        if interfaz.page and hasattr(interfaz.page, "pop_dialog"):
            try:
                interfaz.page.pop_dialog()
            except Exception:
                pass

    def _confirmar_movimiento(_e: Any = None) -> None:
        if not producto_seleccionado:
            texto_estado.value = "⚠️ Primero debes escanear o seleccionar un producto."
            texto_estado.color = ft.Colors.RED_600
            _safe_update(texto_estado)
            return

        motivo = dropdown_motivo.value
        if not motivo:
            texto_estado.value = "⚠️ Debes seleccionar un motivo justificado obligatorio."
            texto_estado.color = ft.Colors.RED_600
            _safe_update(texto_estado)
            return

        qty = _obtener_cantidad_int()
        if qty <= 0:
            texto_estado.value = "⚠️ La cantidad debe ser mayor a 0."
            texto_estado.color = ft.Colors.RED_600
            _safe_update(texto_estado)
            return

        codigo = producto_seleccionado["codigo"]
        nombre = producto_seleccionado["nombre"]
        obs = (txt_observaciones.value or "").strip()

        _ejecutar_transaccion(codigo, nombre, qty, motivo, obs, cerrar_al_final=True)

    # Botones rápidos de cantidad (+1, +5, +10, +50)
    fila_stepper = ft.Row(
        [
            ft.IconButton(ft.Icons.REMOVE, on_click=lambda _: _modificar_cantidad(-1), tooltip="Restar 1"),
            txt_cantidad,
            ft.IconButton(ft.Icons.ADD, on_click=lambda _: _modificar_cantidad(1), tooltip="Sumar 1"),
            ft.Container(width=10),
            ft.Button("+1", on_click=lambda _: _fijar_cantidad(_obtener_cantidad_int() + 1), height=32),
            ft.Button("+5", on_click=lambda _: _fijar_cantidad(_obtener_cantidad_int() + 5), height=32),
            ft.Button("+10", on_click=lambda _: _fijar_cantidad(_obtener_cantidad_int() + 10), height=32),
            ft.Button("+50", on_click=lambda _: _fijar_cantidad(_obtener_cantidad_int() + 50), height=32),
        ],
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    contenido = ft.Column(
        [
            switch_modo_continuo,
            ft.Row(
                [
                    txt_codigo_busqueda,
                    ft.IconButton(
                        ft.Icons.SEARCH,
                        icon_color=color_tema,
                        tooltip="Buscar producto (o presione Enter)",
                        on_click=_buscar_producto,
                    ),
                ],
                spacing=6,
            ),
            texto_estado,
            tarjeta_producto,
            ft.Divider(height=1, color=ft.Colors.with_opacity(0.2, interfaz.borde)),
            ft.Text("Cantidad a mover:", size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto),
            fila_stepper,
            ft.Container(height=4),
            dropdown_motivo,
            txt_observaciones,
        ],
        spacing=10,
        tight=True,
        width=520,
    )

    btn_confirmar = ft.Button(
        content=ft.Row(
            [
                ft.Icon(icono_accion, size=18, color=ft.Colors.WHITE),
                ft.Text("Confirmar " + ("Entrada" if es_ingreso else "Salida"), color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
            ],
            spacing=6,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        bgcolor=color_tema,
        on_click=_confirmar_movimiento,
    )

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(icono_accion, color=color_tema, size=24),
                ft.Text(titulo_texto, weight=ft.FontWeight.BOLD, size=18, color=interfaz.texto),
            ],
            spacing=10,
        ),
        content=contenido,
        actions=[
            ft.Button("Cerrar / Cancelar", on_click=_al_cerrar),
            btn_confirmar,
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    try:
        interfaz.page.show_dialog(dialogo)
        interfaz.page.update()
    except Exception:
        pass
