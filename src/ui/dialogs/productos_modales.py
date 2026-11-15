"""Diálogos auxiliares del catálogo de productos: edición, baja/alta lógica, alta e historial."""

from __future__ import annotations

import sys
from typing import Any, Callable

import flet as ft

from ...inventory import StockManager as _DefaultStockManager


def _resolver_stock_manager_cls():
    """Resuelve StockManager respetando patches sobre dlg_productos o src.flet_gui."""
    mod_prod = sys.modules.get("src.ui.dialogs.dlg_productos")
    if mod_prod is not None and hasattr(mod_prod, "_get_stock_manager_cls"):
        return mod_prod._get_stock_manager_cls()
    mod_gui = sys.modules.get("src.flet_gui")
    if mod_gui is not None and hasattr(mod_gui, "StockManager"):
        return getattr(mod_gui, "StockManager")
    return _DefaultStockManager


def mostrar_dialogo_editar_producto(
    interfaz: Any,
    stock_manager: Any,
    producto: Any,
    on_guardado: Callable[[], None],
) -> None:
    """Abre el diálogo modal de edición de un producto existente del catálogo."""
    if not interfaz.exigir_roles("administrador"):
        return
    codigo_original = str(producto["code"])
    campo_codigo = ft.TextField(label="Código", value=codigo_original)
    campo_nombre = ft.TextField(label="Nombre", value=str(producto["name"]))
    campo_stock = ft.TextField(label="Stock", value=str(producto["stock"]), keyboard_type=ft.KeyboardType.NUMBER)

    try:
        stock_min_val = int(producto["stock_minimo"])
    except Exception:
        stock_min_val = 5
    try:
        stock_max_val = int(producto["stock_maximo"])
    except Exception:
        stock_max_val = 100

    campo_min = ft.TextField(label="Stock mínimo (alerta quiebre)", value=str(stock_min_val), keyboard_type=ft.KeyboardType.NUMBER)
    campo_max = ft.TextField(label="Stock máximo (alerta sobrestock)", value=str(stock_max_val), keyboard_type=ft.KeyboardType.NUMBER)
    barras_init = str(producto["cod_barras"] or "").strip() if "cod_barras" in producto.keys() else ""
    campo_barras = ft.TextField(
        label="Código de barras (EAN-13, QR, etc.)",
        value=barras_init,
        hint_text="Escanear o ingresar código de barras",
    )
    campos: list[ft.Control] = [campo_codigo, campo_nombre, campo_barras, campo_stock, campo_min, campo_max]

    async def guardar_edicion(_evento: ft.Event) -> None:
        if not interfaz.exigir_roles("administrador"):
            return
        codigo = (campo_codigo.value or "").strip()
        nombre = (campo_nombre.value or "").strip()
        stock_texto = (campo_stock.value or "").strip()
        if not codigo or not nombre or not stock_texto:
            interfaz.notificar("Completa el código, el nombre y el stock.")
            return
        try:
            stock = int(stock_texto)
        except ValueError:
            interfaz.notificar("El stock debe ser un número entero.")
            return
        try:
            s_min = int((campo_min.value or "5").strip())
            s_max = int((campo_max.value or "100").strip())
            if s_min < 0 or s_max < s_min:
                interfaz.notificar("El mínimo debe ser >= 0 y el máximo >= mínimo.")
                return
        except ValueError:
            interfaz.notificar("Los stocks mínimo y máximo deben ser números enteros.")
            return

        interfaz.page.pop_dialog()
        actualizado = await interfaz.ejecutar_tarea(
            "Edición de producto",
            lambda: stock_manager.actualizar_producto(
                codigo_original,
                codigo,
                nombre,
                stock,
                s_min,
                s_max,
                cod_barras=(campo_barras.value or "").strip(),
            ),
        )
        if actualizado:
            on_guardado()

    dialogo_edicion = ft.AlertDialog(
        modal=True,
        title=ft.Text(f"Editar producto {codigo_original}"),
        content=ft.Column(campos, tight=True, width=380),
        actions=[
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
            interfaz.boton_dialogo("Guardar", guardar_edicion),
        ],
    )
    interfaz.page.show_dialog(dialogo_edicion)


def confirmar_cambio_estado_producto(
    interfaz: Any,
    stock_manager: Any,
    codigo: str,
    activo: bool,
    on_actualizado: Callable[[], None],
) -> None:
    """Pide confirmación y ejecuta la activación o desactivación lógica de un producto."""
    if not interfaz.exigir_roles("administrador"):
        return
    accion = "reactivar" if activo else "desactivar"

    async def aceptar_estado(_evento: ft.Event) -> None:
        if not interfaz.exigir_roles("administrador"):
            return
        interfaz.page.pop_dialog()
        actualizado = await interfaz.ejecutar_tarea(
            "Actualización del estado del producto",
            lambda: stock_manager.cambiar_estado_producto(codigo, activo),
        )
        if actualizado:
            on_actualizado()

    dialogo_estado = ft.AlertDialog(
        modal=True,
        title=ft.Text(f"Confirmar {accion}"),
        content=ft.Text(
            f"El producto {codigo} volverá a incluirse en futuros informes."
            if activo
            else f"El producto {codigo} se conservará en el catálogo, pero no se incluirá en futuros informes."
        ),
        actions=[
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
            interfaz.boton_dialogo(accion.capitalize(), aceptar_estado),
        ],
    )
    interfaz.page.show_dialog(dialogo_estado)


def mostrar_dialogo_historial_movimientos_stock(interfaz: Any, codigo_inicial: str = "") -> None:
    """Muestra el historial detallado de movimientos de stock registrado en SQLite."""
    if not interfaz.exigir_roles("administrador"):
        return
    stock_manager = _resolver_stock_manager_cls()(interfaz.menu.ruta_excel_base)
    filtro_prod = ft.TextField(
        label="Filtrar por código o nombre de producto",
        value=codigo_inicial.strip(),
        prefix_icon=ft.Icons.SEARCH,
        dense=True,
        expand=True,
    )
    filtro_tipo = ft.Dropdown(
        label="Tipo",
        value="",
        options=[
            ft.DropdownOption(key="", text="Todos"),
            ft.DropdownOption(key="descuento", text="Descuentos (-)"),
            ft.DropdownOption(key="ingreso_fabrica", text="Ingresos / Ajustes (+)"),
        ],
        width=190,
        dense=True,
    )
    lista_movs = ft.ListView(expand=True, spacing=6, height=380)
    resumen_txt = ft.Text("", size=11, color=interfaz.secundario)

    def recargar_movs(_e: ft.Event | None = None) -> None:
        lista_movs.controls.clear()
        filas = stock_manager.product_store.list_recent_movements(
            product_code=filtro_prod.value or "",
            movement_type=filtro_tipo.value or "",
            limit=200,
        )
        resumen_txt.value = f"Mostrando {len(filas)} movimiento(s) recientes en SQLite"
        if not filas:
            lista_movs.controls.append(
                ft.Text("No se encontraron movimientos para el filtro seleccionado.", color=interfaz.secundario, size=12)
            )
        else:
            for r in filas:
                qty = int(r["quantity"])
                signo = f"+{qty}" if qty > 0 else str(qty)
                col_qty = ft.Colors.GREEN_400 if qty > 0 else ft.Colors.RED_400
                usr = str(r["usuario"] or "sistema")
                det = str(r["detalle"] or r["movement_type"])
                fecha_m = str(r["registered_at"]).replace("T", " ")[:19]
                lista_movs.controls.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                        border=ft.Border.all(1, interfaz.borde),
                        border_radius=8,
                        content=ft.Row(
                            [
                                ft.Text(str(r["product_code"]), width=90, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                                ft.Text(str(r["product_name"] or "-"), expand=True, color=interfaz.texto),
                                ft.Text(signo, width=65, color=col_qty, weight=ft.FontWeight.BOLD),
                                ft.Text(det, width=190, size=11, color=interfaz.secundario),
                                ft.Text(f"👤 {usr}", width=110, size=11, color=interfaz.secundario),
                                ft.Text(fecha_m, width=130, size=11, color=interfaz.secundario),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    )
                )
        interfaz.page.update()

    filtro_prod.on_change = recargar_movs
    filtro_tipo.on_select = recargar_movs
    recargar_movs()

    dlg = ft.AlertDialog(
        title=ft.Row(
            [
                ft.Icon(ft.Icons.HISTORY, color=ft.Colors.BLUE_GREY_700),
                ft.Text("Historial de Movimientos de Stock (SQLite)", weight=ft.FontWeight.BOLD, size=15),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=880,
            content=ft.Column(
                [ft.Row([filtro_prod, filtro_tipo], spacing=8), resumen_txt, ft.Divider(height=6), lista_movs],
                tight=True,
                spacing=8,
            ),
        ),
        actions=[interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog())],
    )
    interfaz.page.show_dialog(dlg)


def mostrar_dialogo_formulario_producto(
    interfaz: Any,
    al_guardar: Callable[[], None] | None = None,
) -> None:
    """Abre el formulario para agregar un producto nuevo en posición."""
    if not interfaz.exigir_roles("administrador"):
        return
    campos = {
        "codigo": ft.TextField(label="Código del nuevo producto"),
        "nombre": ft.TextField(label="Nombre del producto"),
        "cod_barras": ft.TextField(label="Código de barras (opcional)"),
        "referencia": ft.TextField(label="Código del producto anterior"),
        "stock": ft.TextField(label="Stock inicial (opcional)", keyboard_type=ft.KeyboardType.NUMBER),
    }

    async def guardar(_evento: ft.Event) -> None:
        if not interfaz.exigir_roles("administrador"):
            return
        codigo = (campos["codigo"].value or "").strip()
        nombre = (campos["nombre"].value or "").strip()
        referencia = (campos["referencia"].value or "").strip()
        stock_texto = (campos["stock"].value or "").strip()
        campos["codigo"].error_text = "El código es obligatorio" if not codigo else None
        campos["nombre"].error_text = "El nombre es obligatorio" if not nombre else None
        campos["referencia"].error_text = "Selecciona el producto de referencia" if not referencia else None
        if not codigo or not nombre or not referencia:
            interfaz.page.update()
            return

        try:
            stock = int(stock_texto) if stock_texto else None
            campos["stock"].error_text = None
        except ValueError:
            campos["stock"].error_text = "El stock inicial debe ser un número entero"
            interfaz.page.update()
            return

        interfaz.page.pop_dialog()

        def insertar() -> None:
            stock_manager = _resolver_stock_manager_cls()(interfaz.menu.ruta_excel_base)
            exito, mensaje, _ = stock_manager.agregar_producto_en_posicion(
                codigo_nuevo=codigo,
                nombre_nuevo=nombre,
                codigo_arriba=referencia,
                stock_inicial=stock,
                cod_barras=(campos["cod_barras"].value or "").strip(),
            )
            if not exito:
                raise ValueError(mensaje)
            print(f"[OK] {mensaje}")

        creado = await interfaz.ejecutar_tarea("Alta de producto", insertar)
        if creado and al_guardar is not None:
            al_guardar()

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text("Datos del nuevo producto"),
        content=ft.Column(list(campos.values()), tight=True, width=380),
        actions=[
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
            interfaz.boton_dialogo("Guardar", guardar),
        ],
    )
    interfaz.page.show_dialog(dialogo)
