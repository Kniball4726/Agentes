"""Diálogo modal para la gestión y CRUD de clientes."""

from __future__ import annotations

import sys
from typing import Any

import flet as ft

from ..components.debounce import Debouncer
from ..design import colores_de, marcar_error
from ..theme import ROJO


def _formatear_subtitulo_cliente(cli: Any) -> str:
    fecha_creado = cli.created_at[:10] if cli.created_at else ""
    sub_partes: list[str] = []
    if cli.codigo:
        sub_partes.append(f"Cód: {cli.codigo}")
    if cli.direccion:
        sub_partes.append(f"📍 {cli.direccion}")
    if fecha_creado:
        sub_partes.append(f"Alta: {fecha_creado}")
    return " | ".join(sub_partes)


def _construir_placeholder_clientes(interfaz: Any, busqueda: str) -> ft.Container:
    return ft.Container(
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


class _GestionClientesController:
    """Controlador de estado y eventos para el CRUD modal de clientes."""

    def __init__(self, interfaz: Any) -> None:
        self.interfaz = interfaz
        self.colores = colores_de(interfaz)
        self.usr_nom = interfaz.usuario_actual.username if interfaz.usuario_actual else "Operador"

        self.filtro_txt = ft.TextField(
            hint_text="Buscar cliente por nombre, código o dirección...",
            prefix_icon=ft.Icons.SEARCH,
            dense=True,
            expand=True,
        )
        self.nuevo_cliente_txt = ft.TextField(
            hint_text="Nombre del nuevo cliente *",
            dense=True,
            expand=True,
        )
        self.nuevo_codigo_txt = ft.TextField(
            hint_text="Código (opc)",
            dense=True,
            width=110,
        )
        self.nueva_direccion_txt = ft.TextField(
            hint_text="Dirección para mapas / logística (opcional)...",
            dense=True,
            expand=True,
        )
        self.msg_feedback = ft.Text(size=12, color=ft.Colors.RED_400)
        self.total_txt = ft.Text("", size=11, color=interfaz.secundario)
        self.lista_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=300)
        self.cache_clientes: list[Any] = []
        self.limite_clientes = 80

        es_test = getattr(interfaz, "_is_mock", False) or "pytest" in sys.modules
        self.debouncer = Debouncer(0.0 if es_test else 0.25)
        self.filtro_txt.on_change = lambda _e: self.debouncer.debounce(
            lambda: self.recargar_clientes(recargar_db=False)
        )
        self.filtro_txt.on_submit = self._al_enviar_filtro
        self.nuevo_cliente_txt.on_submit = self.agregar_cliente

    def _al_enviar_filtro(self, _e: ft.Event) -> None:
        self.debouncer.cancel()
        self.recargar_clientes(recargar_db=False)

    def _mostrar_mas_clientes(self, _e: ft.Event | None = None) -> None:
        self.limite_clientes += 100
        self.recargar_clientes(recargar_db=False, mantener_limite=True)

    def _cargar_clientes_filtrados(self, recargar_db: bool, busqueda: str) -> list[Any] | None:
        if recargar_db or not self.cache_clientes:
            try:
                self.cache_clientes = list(self.interfaz.order_store.listar_clientes())
            except Exception as err:
                self.msg_feedback.value = f"Error al cargar clientes: {err}"
                self.msg_feedback.color = ft.Colors.RED_400
                self.interfaz.page.update()
                return None

        clientes = list(self.cache_clientes)
        if busqueda:
            clientes = [
                c
                for c in clientes
                if busqueda in c.nombre.lower()
                or busqueda in c.codigo.lower()
                or busqueda in c.direccion.lower()
            ]
        return clientes

    def _abrir_dialogo_editar(self, cli: Any) -> None:
        campo_edit = ft.TextField(
            value=cli.nombre,
            label="Nombre del cliente *",
            expand=True,
            autofocus=True,
        )
        campo_cod = ft.TextField(
            value=cli.codigo,
            label="Código de cliente (opcional)",
            dense=True,
        )
        campo_dir = ft.TextField(
            value=cli.direccion,
            label="Dirección (para mapas Google / logística)",
            dense=True,
        )
        err_edit = ft.Text(size=11, color=ft.Colors.RED_400)

        def guardar_edit(_ev: ft.Event) -> None:
            val_nom = (campo_edit.value or "").strip()
            val_cod = (campo_cod.value or "").strip()
            val_dir = (campo_dir.value or "").strip()
            marcar_error(campo_edit, None)
            try:
                self.interfaz.order_store.actualizar_cliente(
                    cli.id,
                    val_nom,
                    usuario=self.usr_nom,
                    codigo=val_cod,
                    direccion=val_dir,
                )
                self.interfaz.page.pop_dialog()
                self.interfaz.notificar(f"Cliente '{val_nom}' actualizado.")
                self.recargar_clientes()
            except Exception as err:
                err_msg = str(err)
                if "ya existe" in err_msg.lower():
                    marcar_error(campo_edit, "El cliente ya existe en el sistema")
                err_edit.value = err_msg
                self.interfaz.page.update()

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
                self.interfaz.boton_dialogo("Cancelar", lambda _ev: self.interfaz.page.pop_dialog()),
            ],
        )
        self.interfaz.page.show_dialog(dlg_edit)

    def _abrir_dialogo_eliminar(self, cli: Any) -> None:
        def confirmar_borrado(_ev: ft.Event) -> None:
            try:
                self.interfaz.order_store.eliminar_cliente(cli.id, usuario=self.usr_nom)
                self.interfaz.page.pop_dialog()
                self.interfaz.notificar(f"Cliente '{cli.nombre}' dado de baja.")
                self.recargar_clientes()
            except Exception as err:
                self.interfaz.page.pop_dialog()
                self.interfaz.notificar(f"Error al eliminar cliente: {err}")

        dlg_del = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [ft.Icon(ft.Icons.WARNING_AMBER, color=ROJO), ft.Text("Confirmar Baja de Cliente")]
            ),
            content=ft.Text(
                f"¿Deseas dar de baja al cliente '{cli.nombre}'?\n\n"
                "No se borrará el historial de pedidos anteriores."
            ),
            actions=[
                ft.Button(
                    "Dar de baja",
                    bgcolor=ROJO,
                    color=ft.Colors.WHITE,
                    on_click=confirmar_borrado,
                ),
                self.interfaz.boton_dialogo("Cancelar", lambda _ev: self.interfaz.page.pop_dialog()),
            ],
        )
        self.interfaz.page.show_dialog(dlg_del)

    def _construir_fila_cliente(self, cli: Any) -> ft.Container:
        subtitulo = _formatear_subtitulo_cliente(cli)
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            border=ft.Border.all(1, self.interfaz.borde),
            border_radius=8,
            bgcolor=self.interfaz.fondo,
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.BUSINESS, color=self.interfaz.secundario, size=18),
                    ft.Column(
                        [
                            ft.Text(
                                cli.nombre,
                                weight=ft.FontWeight.W_500,
                                size=13,
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            (
                                ft.Text(
                                    subtitulo,
                                    size=10,
                                    color=self.interfaz.secundario,
                                    max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                )
                                if subtitulo
                                else ft.Container()
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.IconButton(
                        ft.Icons.EDIT_OUTLINED,
                        tooltip="Editar cliente",
                        icon_size=18,
                        on_click=lambda _e, c=cli: self._abrir_dialogo_editar(c),
                    ),
                    ft.IconButton(
                        ft.Icons.DELETE_OUTLINE,
                        tooltip="Dar de baja",
                        icon_size=18,
                        icon_color=ft.Colors.RED_400,
                        on_click=lambda _e, c=cli: self._abrir_dialogo_eliminar(c),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def recargar_clientes(self, recargar_db: bool = True, mantener_limite: bool = False) -> None:
        if not mantener_limite:
            self.limite_clientes = 80
        self.lista_col.controls.clear()
        self.msg_feedback.value = ""
        busqueda = (self.filtro_txt.value or "").strip().lower()

        clientes = self._cargar_clientes_filtrados(recargar_db, busqueda)
        if clientes is None:
            return

        self.total_txt.value = f"Total: {len(clientes)} cliente(s) activo(s)"
        if not clientes:
            self.lista_col.controls.append(_construir_placeholder_clientes(self.interfaz, busqueda))
        else:
            for cli in clientes[: self.limite_clientes]:
                self.lista_col.controls.append(self._construir_fila_cliente(cli))
            restantes_cli = len(clientes) - self.limite_clientes
            if restantes_cli > 0:
                self.lista_col.controls.append(
                    ft.Container(
                        alignment=ft.Alignment.CENTER,
                        padding=4,
                        content=ft.TextButton(
                            f"Mostrar más clientes ({restantes_cli} restantes)...",
                            icon=ft.Icons.EXPAND_MORE,
                            on_click=self._mostrar_mas_clientes,
                        ),
                    )
                )

        self.interfaz.page.update()

    def agregar_cliente(self, _e: ft.Event) -> None:
        nom = (self.nuevo_cliente_txt.value or "").strip()
        cod = (self.nuevo_codigo_txt.value or "").strip()
        dir_c = (self.nueva_direccion_txt.value or "").strip()
        if not nom:
            marcar_error(self.nuevo_cliente_txt, "El nombre del cliente es obligatorio")
            self.msg_feedback.value = "Por favor ingresa un nombre para el cliente."
            self.msg_feedback.color = self.colores.error
            self.interfaz.page.update()
            return
        marcar_error(self.nuevo_cliente_txt, None)
        try:
            self.interfaz.order_store.crear_cliente(
                nom,
                usuario=self.usr_nom,
                codigo=cod,
                direccion=dir_c,
            )
            self.nuevo_cliente_txt.value = ""
            self.nuevo_codigo_txt.value = ""
            self.nueva_direccion_txt.value = ""
            self.msg_feedback.value = f"✓ Cliente '{nom}' agregado correctamente."
            self.msg_feedback.color = self.colores.exito
            self.recargar_clientes()
        except Exception as err:
            err_msg = str(err)
            if "ya existe" in err_msg.lower():
                marcar_error(self.nuevo_cliente_txt, "El cliente ya existe en el sistema")
            self.msg_feedback.value = err_msg
            self.msg_feedback.color = self.colores.error
            self.interfaz.page.update()

    def construir_dialogo(self) -> ft.AlertDialog:
        ancho_dlg = (
            self.interfaz.ancho_adaptable(560)
            if hasattr(self.interfaz, "ancho_adaptable")
            else 560
        )
        return ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.PEOPLE_ALT, color=ROJO),
                    ft.Text("Gestión de Clientes", weight=ft.FontWeight.BOLD),
                ]
            ),
            content=ft.Container(
                width=ancho_dlg,
                content=ft.Column(
                    [
                        ft.Text("Registrar nuevo cliente:", size=12, weight=ft.FontWeight.BOLD),
                        ft.Row([self.nuevo_cliente_txt, self.nuevo_codigo_txt], spacing=8),
                        ft.Row(
                            [
                                self.nueva_direccion_txt,
                                ft.Button(
                                    "Agregar",
                                    icon=ft.Icons.PERSON_ADD,
                                    bgcolor=ROJO,
                                    color=ft.Colors.WHITE,
                                    on_click=self.agregar_cliente,
                                ),
                            ],
                            spacing=8,
                        ),
                        self.msg_feedback,
                        ft.Divider(height=16, color=self.interfaz.borde),
                        ft.Row(
                            [
                                ft.Text("Clientes registrados:", size=12, weight=ft.FontWeight.BOLD),
                                self.total_txt,
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        self.filtro_txt,
                        self.lista_col,
                    ],
                    tight=True,
                    spacing=8,
                ),
            ),
            actions=[
                self.interfaz.boton_dialogo("Cerrar", lambda _e: self.interfaz.page.pop_dialog())
            ],
        )

    def mostrar(self) -> None:
        self.interfaz.page.show_dialog(self.construir_dialogo())
        self.recargar_clientes()


def mostrar_dialogo_gestion_clientes(interfaz: Any) -> None:
    """Abre la ventana modal con el CRUD interactivo de clientes."""
    if not interfaz.exigir_roles("operador", "administrador"):
        return

    _GestionClientesController(interfaz).mostrar()
