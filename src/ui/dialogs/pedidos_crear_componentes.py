"""Componentes modulares de interfaz para el diálogo de creación de pedidos."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Callable

import flet as ft

from ...orders import calcular_hash_archivo
from ...paths import application_root
from ..components.debounce import Debouncer
from ..design import colores_de
from .pedidos_crear_modales import parsear_comprobante_pedido


class SelectorClientePedido:
    """Gestiona el campo de texto de cliente con sugerencias reactivas y alta transparente."""

    def __init__(self, interfaz: Any, on_cambio_callback: Callable[[str], None] | None = None) -> None:
        self.interfaz = interfaz
        self._on_cambio_callback = on_cambio_callback
        self.clientes_lista_obj = list(interfaz.order_store.listar_clientes())
        self.clientes_actuales = [c.nombre for c in self.clientes_lista_obj]

        colores = colores_de(interfaz)
        self.input_cliente = ft.TextField(
            label="Cliente (buscar o escribir nuevo) *",
            hint_text="Escribe para buscar o ingresar cliente nuevo",
            expand=True,
        )
        self.estado_cliente_txt = ft.Text("", size=11, color=colores.exito)
        self.sugerencias_lista = ft.ListView(spacing=2, height=110, visible=False)

        es_test = getattr(interfaz, "_is_mock", False) or "pytest" in sys.modules
        self._debouncer = Debouncer(0.0 if es_test else 0.25)
        self.input_cliente.on_change = lambda _e: self._debouncer.debounce(self._on_cliente_cambio)
        self.input_cliente.on_submit = lambda _e: (self._debouncer.cancel(), self._on_cliente_cambio())

    @property
    def value(self) -> str:
        return (self.input_cliente.value or "").strip()

    @value.setter
    def value(self, nuevo_valor: str) -> None:
        self.input_cliente.value = nuevo_valor
        self._on_cliente_cambio(None)

    def seleccionar_cliente_sugerido(self, nombre: str) -> None:
        self.input_cliente.value = nombre
        self.sugerencias_lista.visible = False
        colores = colores_de(self.interfaz)
        self.estado_cliente_txt.value = f"✓ Cliente existente seleccionado: {nombre}"
        self.estado_cliente_txt.color = colores.exito
        if self._on_cambio_callback:
            self._on_cambio_callback(nombre)
        self.interfaz.page.update()

    def recargar_clientes(self) -> None:
        self.clientes_lista_obj.clear()
        self.clientes_lista_obj.extend(self.interfaz.order_store.listar_clientes())
        self.clientes_actuales.clear()
        self.clientes_actuales.extend([c.nombre for c in self.clientes_lista_obj])

    def _on_cliente_cambio(self, _e: ft.Event | None = None) -> None:
        q = (self.input_cliente.value or "").strip().lower()
        if not q:
            self.sugerencias_lista.visible = False
            self.estado_cliente_txt.value = ""
            self.interfaz.page.update()
            return

        coincidencias = [
            c
            for c in self.clientes_lista_obj
            if q in c.nombre.lower() or (c.codigo and q in c.codigo.lower()) or (c.direccion and q in c.direccion.lower())
        ]
        if coincidencias:
            self.sugerencias_lista.controls.clear()
            for c in coincidencias[:6]:
                sub_info = []
                if c.codigo:
                    sub_info.append(f"Cód: {c.codigo}")
                if c.direccion:
                    sub_info.append(f"📍 {c.direccion}")
                det_txt = " | ".join(sub_info)

                self.sugerencias_lista.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.PERSON, size=16, color=ft.Colors.BLUE_400),
                                ft.Column(
                                    [
                                        ft.Text(c.nombre, size=13, weight=ft.FontWeight.W_500),
                                        *([ft.Text(det_txt, size=10, color=self.interfaz.secundario)] if det_txt else []),
                                    ],
                                    spacing=1,
                                    expand=True,
                                ),
                            ],
                            spacing=6,
                        ),
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                        border_radius=4,
                        ink=True,
                        on_click=lambda _ev, nom=c.nombre: self.seleccionar_cliente_sugerido(nom),
                    )
                )
            self.sugerencias_lista.visible = True
            if any(c.nombre.lower() == q for c in coincidencias):
                self.estado_cliente_txt.value = "✓ Cliente registrado"
                self.estado_cliente_txt.color = ft.Colors.GREEN_400
            else:
                self.estado_cliente_txt.value = f"{len(coincidencias)} coincidencia(s). Si es nuevo, se creará al confirmar."
                self.estado_cliente_txt.color = ft.Colors.AMBER_400
        else:
            self.sugerencias_lista.visible = False
            self.estado_cliente_txt.value = "✨ Cliente nuevo: se dará de alta automáticamente al guardar."
            self.estado_cliente_txt.color = ft.Colors.AMBER_400
        self.interfaz.page.update()


class SelectorComprobantePedido:
    """Gestiona la selección, validación contra duplicados y auto-extracción de metadatos de comprobantes."""

    def __init__(
        self,
        interfaz: Any,
        on_datos_extraidos: Callable[[Any, Path, str], None],
        on_error: Callable[[str], None],
    ) -> None:
        self.interfaz = interfaz
        self.on_datos_extraidos = on_datos_extraidos
        self.on_error = on_error

        self.ruta_comprobante: list[Path] = []
        self.datos_doc_ref: list[Any] = []
        self.texto_archivo = ft.Text(
            "Ningún comprobante seleccionado (.pdf, .xlsx/.xls o .docx)",
            size=12,
            color=interfaz.secundario,
        )

        self.boton_archivo = ft.Button(
            "Adjuntar Comprobante",
            icon=ft.Icons.ATTACH_FILE,
            bgcolor=ft.Colors.BLUE_GREY_800 if interfaz.modo_oscuro else ft.Colors.BLUE_GREY_100,
            color=interfaz.texto,
            on_click=self.seleccionar_comprobante,
        )

        self.contenedor = ft.Container(
            bgcolor=ft.Colors.BLUE_GREY_900 if interfaz.modo_oscuro else ft.Colors.GREY_100,
            border=ft.Border.all(1, interfaz.borde),
            border_radius=10,
            padding=12,
            content=ft.Column(
                [
                    ft.Text(
                        "Comprobante adjunto (.pdf, .xlsx/.xls o .docx)",
                        size=12,
                        color=interfaz.secundario,
                        weight=ft.FontWeight.W_500,
                    ),
                    ft.Row(
                        [self.boton_archivo, self.texto_archivo]
                        if getattr(interfaz, "es_pantalla_movil", False)
                        else [self.boton_archivo, ft.Container(content=self.texto_archivo, expand=True)],
                        wrap=bool(getattr(interfaz, "es_pantalla_movil", False)),
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                    ),
                ],
                spacing=8,
            ),
        )

    async def seleccionar_comprobante(self, _e: ft.Event) -> None:
        try:
            archivos = await self.interfaz.subir_archivos_desde_pc(
                carpeta_destino=application_root() / "data" / "pedidos_archivos",
                extensiones=["pdf", "xlsx", "xls", "docx"],
                titulo="Seleccionar Comprobante de Pedido (.pdf, .xlsx, .docx)",
            )
            if not archivos:
                return
            arch_candidato = archivos[0]
            if len(archivos) > 1:
                self.interfaz.notificar(
                    f"Se seleccionaron {len(archivos)} comprobantes. Se preparó '{arch_candidato.name}'; "
                    f"una vez confirmado este pedido podrás cargar los restantes."
                )

            hash_candidato = calcular_hash_archivo(arch_candidato)
            if hash_candidato:
                duplicado = self.interfaz.order_store.buscar_pedido_por_hash(hash_candidato)
                if duplicado:
                    self.ruta_comprobante.clear()
                    self.datos_doc_ref.clear()
                    self.texto_archivo.value = f"⛔ DUPLICADO: {arch_candidato.name}"
                    self.texto_archivo.color = ft.Colors.RED_400
                    self.on_error(
                        f"⛔ ATENCIÓN: El contenido de este archivo ya fue procesado el {duplicado.created_at[:16]} "
                        f"(Comprobante: {duplicado.nota_pedido}, Cliente: {duplicado.cliente})."
                    )
                    self.interfaz.page.update()
                    return

            self.ruta_comprobante.clear()
            self.ruta_comprobante.append(arch_candidato)
            self.texto_archivo.value = f"Comprobante: {arch_candidato.name}"
            self.texto_archivo.color = ft.Colors.GREEN_400
            self.on_error("")

            try:
                datos_doc = parsear_comprobante_pedido(arch_candidato, self.interfaz.menu.ruta_excel_base)
                if datos_doc:
                    self.datos_doc_ref.clear()
                    self.datos_doc_ref.append(datos_doc)
                    self.on_datos_extraidos(datos_doc, arch_candidato, hash_candidato)
            except Exception:
                pass
            self.interfaz.page.update()
        except Exception as err:
            self.on_error(f"Error al seleccionar comprobante: {err}")
            self.interfaz.page.update()


class SelectorFechaRetiroPedido:
    """Gestiona el selector de fecha con diálogo de DatePicker integrado."""

    def __init__(self, interfaz: Any) -> None:
        self.interfaz = interfaz
        self.date_picker = ft.DatePicker(
            on_change=self._fecha_seleccionada,
            help_text="Seleccionar fecha de retiro",
            confirm_text="Aceptar",
            cancel_text="Cancelar",
        )
        self.input_fecha = ft.TextField(
            label="Fecha de retiro (opcional)",
            hint_text="Sin fecha asignada",
            read_only=True,
            expand=True,
            on_click=self.abrir_calendario,
        )
        self.fila_control = ft.Row(
            [
                self.input_fecha,
                ft.IconButton(
                    icon=ft.Icons.CALENDAR_MONTH,
                    tooltip="Seleccionar fecha de retiro en calendario",
                    on_click=self.abrir_calendario,
                ),
                ft.IconButton(
                    icon=ft.Icons.BACKSPACE_OUTLINED,
                    tooltip="Quitar fecha de retiro",
                    on_click=self.limpiar_fecha,
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
        )

    @property
    def value(self) -> str:
        return (self.input_fecha.value or "").strip()

    @value.setter
    def value(self, val: str) -> None:
        self.input_fecha.value = val

    def abrir_calendario(self, _e: ft.Event) -> None:
        self.interfaz.page.show_dialog(self.date_picker)

    def limpiar_fecha(self, _e: ft.Event) -> None:
        self.input_fecha.value = ""
        self.interfaz.page.update()

    def _fecha_seleccionada(self, _e: ft.Event) -> None:
        val = self.date_picker.value
        if val:
            self.input_fecha.value = val.strftime("%d/%m/%Y") if hasattr(val, "strftime") else str(val)[:10]
        self.interfaz.page.update()
