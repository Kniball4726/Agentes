"""Diálogo modal para la gestión y CRUD de clientes."""
from typing import Any
import flet as ft
from ..theme import ROJO


def mostrar_dialogo_gestion_clientes(interfaz: Any) -> None:
    """Abre la ventana modal con el CRUD interactivo de clientes."""
    if not interfaz.exigir_roles("operador", "administrador"):
        return

    usr_nom = interfaz.usuario_actual.username if interfaz.usuario_actual else "Operador"

    filtro_txt = ft.TextField(
        hint_text="Buscar cliente por nombre, código o dirección...",
        prefix_icon=ft.Icons.SEARCH,
        dense=True,
        expand=True,
    )
    nuevo_cliente_txt = ft.TextField(
        hint_text="Nombre del nuevo cliente *",
        dense=True,
        expand=True,
    )
    nuevo_codigo_txt = ft.TextField(
        hint_text="Código (opc)",
        dense=True,
        width=110,
    )
    nueva_direccion_txt = ft.TextField(
        hint_text="Dirección para mapas / logística (opcional)...",
        dense=True,
        expand=True,
    )
    msg_feedback = ft.Text(size=12, color=ft.Colors.RED_400)
    total_txt = ft.Text("", size=11, color=interfaz.secundario)
    lista_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=300)

    def recargar_clientes() -> None:
        lista_col.controls.clear()
        msg_feedback.value = ""
        busqueda = (filtro_txt.value or "").strip().lower()
        try:
            clientes = interfaz.order_store.listar_clientes()
        except Exception as err:
            msg_feedback.value = f"Error al cargar clientes: {err}"
            msg_feedback.color = ft.Colors.RED_400
            interfaz.page.update()
            return

        if busqueda:
            clientes = [
                c for c in clientes
                if busqueda in c.nombre.lower() or busqueda in c.codigo.lower() or busqueda in c.direccion.lower()
            ]

        total_txt.value = f"Total: {len(clientes)} cliente(s) activo(s)"

        if not clientes:
            lista_col.controls.append(
                ft.Container(
                    padding=12,
                    content=ft.Text(
                        "No se encontraron clientes que coincidan con la búsqueda."
                        if busqueda
                        else "No hay clientes registrados aún.",
                        italic=True,
                        color=interfaz.secundario,
                        size=12,
                    ),
                )
            )
        else:
            for cli in clientes:
                c_id = cli.id
                c_nom = cli.nombre
                c_cod = cli.codigo
                c_dir = cli.direccion

                def editar_cli(_e: ft.Event, cid=c_id, cnom=c_nom, ccod=c_cod, cdir=c_dir):
                    campo_edit = ft.TextField(
                        value=cnom,
                        label="Nombre del cliente *",
                        expand=True,
                        autofocus=True,
                    )
                    campo_cod = ft.TextField(
                        value=ccod,
                        label="Código de cliente (opcional)",
                        dense=True,
                    )
                    campo_dir = ft.TextField(
                        value=cdir,
                        label="Dirección (para mapas Google / logística)",
                        dense=True,
                    )
                    err_edit = ft.Text(size=11, color=ft.Colors.RED_400)

                    def guardar_edit(_ev: ft.Event):
                        val_nom = (campo_edit.value or "").strip()
                        val_cod = (campo_cod.value or "").strip()
                        val_dir = (campo_dir.value or "").strip()
                        try:
                            interfaz.order_store.actualizar_cliente(
                                cid,
                                val_nom,
                                usuario=usr_nom,
                                codigo=val_cod,
                                direccion=val_dir,
                            )
                            interfaz.page.pop_dialog()
                            interfaz.notificar(f"Cliente '{val_nom}' actualizado.")
                            recargar_clientes()
                        except Exception as err:
                            err_edit.value = str(err)
                            interfaz.page.update()

                    campo_edit.on_submit = guardar_edit

                    dlg_edit = ft.AlertDialog(
                        modal=True,
                        title=ft.Row([ft.Icon(ft.Icons.EDIT, color=ROJO), ft.Text("Editar Cliente")]),
                        content=ft.Container(
                            width=440,
                            content=ft.Column(
                                [campo_edit, campo_cod, campo_dir, err_edit],
                                tight=True,
                                spacing=10,
                            ),
                        ),
                        actions=[
                            ft.Button("Guardar", bgcolor=ROJO, color=ft.Colors.WHITE, on_click=guardar_edit),
                            interfaz.boton_dialogo("Cancelar", lambda _ev: interfaz.page.pop_dialog()),
                        ],
                    )
                    interfaz.page.show_dialog(dlg_edit)

                def borrar_cli(_e: ft.Event, cid=c_id, cnom=c_nom):
                    def confirmar_borrado(_ev: ft.Event):
                        try:
                            interfaz.order_store.eliminar_cliente(cid, usuario=usr_nom)
                            interfaz.page.pop_dialog()
                            interfaz.notificar(f"Cliente '{cnom}' dado de baja.")
                            recargar_clientes()
                        except Exception as err:
                            interfaz.page.pop_dialog()
                            interfaz.notificar(f"Error al eliminar cliente: {err}")

                    dlg_del = ft.AlertDialog(
                        modal=True,
                        title=ft.Row([ft.Icon(ft.Icons.WARNING_AMBER, color=ROJO), ft.Text("Confirmar Baja de Cliente")]),
                        content=ft.Text(f"¿Deseas dar de baja al cliente '{cnom}'?\n\nNo se borrará el historial de pedidos anteriores."),
                        actions=[
                            ft.Button("Dar de baja", bgcolor=ROJO, color=ft.Colors.WHITE, on_click=confirmar_borrado),
                            interfaz.boton_dialogo("Cancelar", lambda _ev: interfaz.page.pop_dialog()),
                        ],
                    )
                    interfaz.page.show_dialog(dlg_del)

                fecha_creado = cli.created_at[:10] if cli.created_at else ""
                sub_partes = []
                if cli.codigo:
                    sub_partes.append(f"Cód: {cli.codigo}")
                if cli.direccion:
                    sub_partes.append(f"📍 {cli.direccion}")
                if fecha_creado:
                    sub_partes.append(f"Alta: {fecha_creado}")
                subtitulo = " | ".join(sub_partes)

                fila = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    border=ft.Border.all(1, interfaz.borde),
                    border_radius=8,
                    bgcolor=interfaz.fondo,
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.BUSINESS, color=interfaz.secundario, size=18),
                            ft.Column(
                                [
                                    ft.Text(cli.nombre, weight=ft.FontWeight.W_500, size=13),
                                    ft.Text(subtitulo, size=10, color=interfaz.secundario) if subtitulo else ft.Container(),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.IconButton(
                                ft.Icons.EDIT_OUTLINED,
                                tooltip="Editar cliente",
                                icon_size=18,
                                on_click=editar_cli,
                            ),
                            ft.IconButton(
                                ft.Icons.DELETE_OUTLINE,
                                tooltip="Dar de baja",
                                icon_size=18,
                                icon_color=ft.Colors.RED_400,
                                on_click=borrar_cli,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
                lista_col.controls.append(fila)

        interfaz.page.update()

    def agregar_cliente(_e: ft.Event) -> None:
        nom = (nuevo_cliente_txt.value or "").strip()
        cod = (nuevo_codigo_txt.value or "").strip()
        dir_c = (nueva_direccion_txt.value or "").strip()
        if not nom:
            msg_feedback.value = "Por favor ingresa un nombre para el cliente."
            msg_feedback.color = ft.Colors.RED_400
            interfaz.page.update()
            return
        try:
            interfaz.order_store.crear_cliente(nom, usuario=usr_nom, codigo=cod, direccion=dir_c)
            nuevo_cliente_txt.value = ""
            nuevo_codigo_txt.value = ""
            nueva_direccion_txt.value = ""
            msg_feedback.value = f"✓ Cliente '{nom}' agregado correctamente."
            msg_feedback.color = ft.Colors.GREEN_400
            recargar_clientes()
        except Exception as err:
            msg_feedback.value = str(err)
            msg_feedback.color = ft.Colors.RED_400
            interfaz.page.update()

    filtro_txt.on_change = lambda _e: recargar_clientes()
    nuevo_cliente_txt.on_submit = agregar_cliente

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row([ft.Icon(ft.Icons.PEOPLE_ALT, color=ROJO), ft.Text("Gestión de Clientes", weight=ft.FontWeight.BOLD)]),
        content=ft.Container(
            width=560,
            content=ft.Column(
                [
                    ft.Text("Registrar nuevo cliente:", size=12, weight=ft.FontWeight.BOLD),
                    ft.Row(
                        [
                            nuevo_cliente_txt,
                            nuevo_codigo_txt,
                        ],
                        spacing=8,
                    ),
                    ft.Row(
                        [
                            nueva_direccion_txt,
                            ft.Button(
                                "Agregar",
                                icon=ft.Icons.PERSON_ADD,
                                bgcolor=ROJO,
                                color=ft.Colors.WHITE,
                                on_click=agregar_cliente,
                            ),
                        ],
                        spacing=8,
                    ),
                    msg_feedback,
                    ft.Divider(height=16, color=interfaz.borde),
                    ft.Row(
                        [
                            ft.Text("Clientes registrados:", size=12, weight=ft.FontWeight.BOLD),
                            total_txt,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    filtro_txt,
                    lista_col,
                ],
                tight=True,
                spacing=8,
            ),
        ),
        actions=[interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog())],
    )

    interfaz.page.show_dialog(dialogo)
    recargar_clientes()
