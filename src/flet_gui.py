"""Prototipo de escritorio en Flet para el agente de control de stock."""

import asyncio
import contextlib
import io
import os
import subprocess
import traceback
import urllib.parse
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Callable

import flet as ft

from .internal_chat import detectar_intencion
from .menu import MenuAgente
from .paths import application_root
from .stock_manager import StockManager
from .user_store import USER_ROLES, User, UserRole, UserStore, UserStoreError


ROJO = ft.Colors.RED_700
FONDO = ft.Colors.GREY_100
SUPERFICIE = ft.Colors.WHITE
TEXTO = ft.Colors.BLUE_GREY_900
SECUNDARIO = ft.Colors.BLUE_GREY_600


class InterfazFlet:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.user_store = UserStore(
            application_root() / "data" / "usuarios.sqlite3"
        )
        self.usuario_actual: User | None = None
        self.modo_oscuro = True
        self.fondo = ft.Colors.BLACK
        self.superficie = ft.Colors.BLUE_GREY_900
        self.texto = ft.Colors.WHITE
        self.secundario = ft.Colors.BLUE_GREY_300
        self.borde = ft.Colors.BLUE_GREY_700
        self.fondo_acento = ft.Colors.RED_700
        self.menu = MenuAgente()
        self.ocupado = False
        self.informes: list[Path] = []
        self.informe_seleccionado: Path | None = None
        self.seleccion_fecha_restauracion: ft.Dropdown | None = None
        self.controles_tarea: list[ft.Button] = []
        self.mayoristas = ft.Checkbox(label="Mayoristas · PDF", value=True)
        self.canjes = ft.Checkbox(label="Canjes · Excel", value=True)
        self.mercado_libre = ft.Checkbox(label="Mercado Libre · DOCX", value=True)
        self.estado_tarea = ft.Text("Listo", color=self.secundario, size=12)
        self.lista_informes = ft.ListView(expand=True, spacing=4)
        self.actividad = ft.ListView(expand=True, spacing=6, auto_scroll=True)
        self.conversacion = ft.ListView(expand=True, spacing=8, auto_scroll=True)
        self.entrada_chat = ft.TextField(
            hint_text="Escribe una consulta o /ayuda",
            expand=True,
            min_lines=1,
            max_lines=3,
            on_submit=self.enviar_chat,
        )
        self.contadores: dict[str, ft.Text] = {}
        self.pendientes_texto = ft.Text("", color=self.secundario, size=12)
        self._configurar_ventana()
        if self.user_store.has_users:
            self.mostrar_inicio_sesion()
        else:
            self.mostrar_configuracion_inicial()

    def alternar_tema(self, _evento: ft.Event | None = None) -> None:
        self.modo_oscuro = not self.modo_oscuro
        if self.modo_oscuro:
            self.fondo = ft.Colors.BLACK
            self.superficie = ft.Colors.BLUE_GREY_900
            self.texto = ft.Colors.WHITE
            self.secundario = ft.Colors.BLUE_GREY_300
            self.borde = ft.Colors.BLUE_GREY_700
            self.fondo_acento = ft.Colors.RED_700
        else:
            self.fondo = ft.Colors.GREY_100
            self.superficie = ft.Colors.WHITE
            self.texto = ft.Colors.BLUE_GREY_900
            self.secundario = ft.Colors.BLUE_GREY_600
            self.borde = ft.Colors.GREY_300
            self.fondo_acento = ft.Colors.RED_50
        self.construir()

    def _configurar_ventana(self) -> None:
        self.page.title = "Agente de control de stock"
        self.page.window.icon = str(
            Path(__file__).resolve().parent / "img" / "ultratech.ico"
        )
        self.page.padding = 0
        self.page.bgcolor = self.fondo
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.theme = ft.Theme(color_scheme_seed=ROJO)
        self.page.window.maximized = True
        self.page.window.min_width = 1050
        self.page.window.min_height = 720

    def mostrar_inicio_sesion(self, error: str = "") -> None:
        usuario = ft.TextField(label="Usuario", autofocus=True)
        clave = ft.TextField(label="Contraseña", password=True, can_reveal_password=True)
        mensaje = ft.Text(error, color=ft.Colors.RED_400)

        def iniciar(_evento: ft.Event) -> None:
            autenticado = self.user_store.authenticate(
                usuario.value or "", clave.value or ""
            )
            if autenticado is None:
                mensaje.value = "Usuario o contraseña incorrectos, o cuenta inactiva."
                self.page.update()
                return
            self.usuario_actual = autenticado
            self.construir()

        self.page.controls.clear()
        self.page.add(
            ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                bgcolor=self.fondo,
                content=ft.Container(
                    width=420,
                    padding=28,
                    bgcolor=self.superficie,
                    border=ft.Border.all(1, self.borde),
                    border_radius=16,
                    content=ft.Column(
                        [
                            ft.Text(
                                "Iniciar sesión",
                                size=24,
                                weight=ft.FontWeight.BOLD,
                                color=self.texto,
                            ),
                            ft.Text(
                                "Agente de control de stock",
                                color=self.secundario,
                            ),
                            usuario,
                            clave,
                            mensaje,
                            ft.Button(
                                "Ingresar",
                                icon=ft.Icons.LOGIN,
                                on_click=iniciar,
                                bgcolor=ROJO,
                                color=ft.Colors.WHITE,
                                width=360,
                            ),
                        ],
                        tight=True,
                        spacing=14,
                    ),
                ),
            )
        )
        self.page.update()

    def mostrar_configuracion_inicial(self, error: str = "") -> None:
        usuario = ft.TextField(label="Usuario administrador", autofocus=True)
        clave = ft.TextField(
            label="Contraseña (mínimo 10 caracteres)",
            password=True,
            can_reveal_password=True,
        )
        confirmar = ft.TextField(
            label="Confirmar contraseña",
            password=True,
            can_reveal_password=True,
        )
        mensaje = ft.Text(error, color=ft.Colors.RED_400)

        def crear_administrador(_evento: ft.Event) -> None:
            if clave.value != confirmar.value:
                mensaje.value = "Las contraseñas no coinciden."
                self.page.update()
                return
            try:
                self.usuario_actual = self.user_store.create_initial_admin(
                    usuario.value or "", clave.value or ""
                )
            except (ValueError, UserStoreError) as error:
                mensaje.value = str(error)
                self.page.update()
                return
            self.construir()

        self.page.controls.clear()
        self.page.add(
            ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                bgcolor=self.fondo,
                content=ft.Container(
                    width=460,
                    padding=28,
                    bgcolor=self.superficie,
                    border=ft.Border.all(1, self.borde),
                    border_radius=16,
                    content=ft.Column(
                        [
                            ft.Text(
                                "Configurar administrador",
                                size=24,
                                weight=ft.FontWeight.BOLD,
                                color=self.texto,
                            ),
                            ft.Text(
                                "Crea la primera cuenta para proteger el acceso al sistema.",
                                color=self.secundario,
                            ),
                            usuario,
                            clave,
                            confirmar,
                            mensaje,
                            ft.Button(
                                "Crear cuenta y continuar",
                                icon=ft.Icons.PERSON_ADD,
                                on_click=crear_administrador,
                                bgcolor=ROJO,
                                color=ft.Colors.WHITE,
                                width=400,
                            ),
                        ],
                        tight=True,
                        spacing=14,
                    ),
                ),
            )
        )
        self.page.update()

    def cerrar_sesion(self, _evento: ft.Event) -> None:
        self.usuario_actual = None
        self.controles_tarea.clear()
        self.mostrar_inicio_sesion()

    def exigir_roles(self, *roles: UserRole) -> bool:
        if self.usuario_actual is None:
            self.mostrar_inicio_sesion()
            return False
        usuario = self.user_store.get_user(self.usuario_actual.id)
        if usuario is None or not usuario.active:
            self.usuario_actual = None
            self.mostrar_inicio_sesion("La cuenta ya no está activa. Inicia sesión nuevamente.")
            return False
        self.usuario_actual = usuario
        if usuario.role not in roles:
            self.notificar("Tu rol no tiene permiso para realizar esta acción.")
            return False
        return True

    def _sidebar_controls(self) -> list[ft.Control]:
        assert self.usuario_actual is not None
        controls: list[ft.Control] = [
            ft.Row(
                [
                    ft.Container(
                        width=42,
                        height=42,
                        border_radius=12,
                        bgcolor=ft.Colors.RED_50 if self.modo_oscuro else ft.Colors.RED_50,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Image(
                            src=(
                                Path(__file__).resolve().parent
                                / "img"
                                / "ultratech.png"
                            ).read_bytes(),
                            width=42,
                            height=42,
                            fit=ft.BoxFit.CONTAIN,
                        ),
                    ),
                    ft.Column(
                        [
                            ft.Text("StockAgent", size=18, weight=ft.FontWeight.BOLD, color=self.texto),
                            ft.Text("Panel de control", size=11, color=self.secundario),
                        ],
                        spacing=2,
                    ),
                ],
                spacing=10,
            ),
            ft.Text(
                f"{self.usuario_actual.username} · {self.usuario_actual.role}",
                size=11,
                color=self.secundario,
            ),
            ft.Divider(height=22, color=self.borde),
        ]
        if self.usuario_actual.role in ("administrador", "operador"):
            controls.extend(
                [
                    ft.Text("FUENTES", size=11, weight=ft.FontWeight.BOLD, color=self.secundario),
                    self.mayoristas,
                    self.canjes,
                    self.mercado_libre,
                    ft.Divider(height=18, color=self.borde),
                    ft.Text("PROCESAMIENTO", size=11, weight=ft.FontWeight.BOLD, color=self.secundario),
                    self.boton("Procesar y actualizar stock", ft.Icons.PLAY_ARROW, self.procesar_real),
                    self.boton("Simular sin guardar", ft.Icons.SCIENCE, self.simular),
                ]
            )
        controls.extend(
            [
                ft.Divider(height=18, color=self.borde),
                ft.Text("INFORMES", size=11, weight=ft.FontWeight.BOLD, color=self.secundario),
                self.boton("Abrir informe", ft.Icons.OPEN_IN_NEW, self.abrir_informe),
                self.boton("Compartir por correo", ft.Icons.EMAIL, self.compartir_correo),
                self.boton("WhatsApp Web", ft.Icons.CHAT, self.compartir_whatsapp),
            ]
        )
        if self.usuario_actual.role == "administrador":
            controls.extend(
                [
                    ft.Divider(height=18, color=self.borde),
                    ft.Text("ADMINISTRACIÓN", size=11, weight=ft.FontWeight.BOLD, color=self.secundario),
                    self.boton("Gestionar usuarios", ft.Icons.GROUP, self.mostrar_gestion_usuarios),
                    self.boton("Restaurar documentos", ft.Icons.RESTORE, self.confirmar_restaurar),
                    self.boton(
                        "Gestionar productos",
                        ft.Icons.ADD_BOX,
                        self.mostrar_gestion_productos,
                    ),
                ]
            )
        controls.extend(
            [
                ft.Container(height=8),
                ft.Row(
                    [
                        ft.Icon(ft.Icons.CIRCLE, color=ft.Colors.GREEN_600, size=10),
                        ft.Text("Agente local activo", size=12, color=self.secundario),
                    ],
                    spacing=8,
                ),
            ]
        )
        return controls

    def construir(self) -> None:
        if self.usuario_actual is None:
            self.mostrar_inicio_sesion()
            return
        self.page.bgcolor = self.fondo
        self.page.theme_mode = ft.ThemeMode.DARK if self.modo_oscuro else ft.ThemeMode.LIGHT
        self.controles_tarea.clear()
        self.page.controls.clear()

        sidebar = ft.Container(
            width=258,
            bgcolor=self.superficie,
            padding=20,
            content=ft.Column(
                self._sidebar_controls(),
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
            ),
        )

        dashboard_controls: list[ft.Control] = [
            self.encabezado(),
            self.panel_metricas(),
            ft.Row(
                [
                    self.panel_informes_actividad(),
                    self.panel_chat(),
                ],
                expand=True,
                spacing=18,
                vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            self.estado_tarea,
        ]
        dashboard = ft.Column(
            dashboard_controls,
            expand=True,
            spacing=16,
        )
        self.page.add(
            ft.Row(
                [
                    sidebar,
                    ft.Container(
                        expand=True,
                        padding=22,
                        content=dashboard,
                    ),
                ],
                expand=True,
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            )
        )
        if not self.conversacion.controls:
            self.escribir_chat(
                "Agente",
                "Hola. Puedo consultar el estado, mostrar informes y ejecutar "
                "simulaciones de solo lectura. Escribe /ayuda para ver los comandos.",
            )
        self.actualizar_estado()

    def boton(
        self,
        texto: str,
        icono: ft.IconData,
        accion: Callable,
        ancho: int = 218,
    ) -> ft.Button:
        control = ft.Button(
            content=texto,
            icon=icono,
            bgcolor=ROJO,
            color=ft.Colors.WHITE,
            on_click=accion,
            width=ancho,
        )
        self.controles_tarea.append(control)
        return control

    @staticmethod
    def boton_dialogo(texto: str, accion: Callable) -> ft.Button:
        return ft.Button(
            content=texto,
            bgcolor=ROJO,
            color=ft.Colors.WHITE,
            on_click=accion,
        )

    def encabezado(self) -> ft.Control:
        assert self.usuario_actual is not None
        boton_tema = ft.Button(
            content="Modo claro" if self.modo_oscuro else "Modo oscuro",
            icon=ft.Icons.WB_SUNNY if self.modo_oscuro else ft.Icons.DARK_MODE,
            on_click=self.alternar_tema,
            bgcolor=ROJO,
            color=ft.Colors.WHITE,
        )
        return ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(
                            "Panel de control",
                            size=28,
                            weight=ft.FontWeight.BOLD,
                            color=self.texto,
                        ),
                        ft.Text(
                            "Gestiona tus documentos, inventario y actividad.",
                            size=14,
                            color=self.secundario,
                        ),
                        self.pendientes_texto,
                    ],
                    spacing=4,
                ),
                ft.Row(
                    [
                        boton_tema,
                        ft.TextButton(
                            f"{self.usuario_actual.username} · Cerrar sesión",
                            icon=ft.Icons.LOGOUT,
                            on_click=self.cerrar_sesion,
                        ),
                        self.boton(
                            "Actualizar", ft.Icons.REFRESH, self.actualizar_estado, 150
                        ),
                    ],
                    spacing=10,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def panel_metricas(self) -> ft.Control:
        metricas = [
            ("PDF pendientes", "pdf", ft.Icons.DESCRIPTION),
            ("Canjes pendientes", "canjes", ft.Icons.SHOPPING_BAG),
            ("Pedidos ML", "ml", ft.Icons.LOCAL_SHIPPING),
            ("Informes", "informes", ft.Icons.INSERT_CHART),
        ]
        tarjetas = []
        for titulo, clave, icono in metricas:
            valor = ft.Text("0", size=25, weight=ft.FontWeight.BOLD, color=self.texto)
            self.contadores[clave] = valor
            tarjetas.append(
                ft.Container(
                    expand=True,
                    bgcolor=self.superficie,
                    border=ft.Border.all(1, self.borde),
                    border_radius=12,
                    padding=16,
                    content=ft.Row(
                        [
                            ft.Container(
                                width=40,
                                height=40,
                                border_radius=10,
                                bgcolor=ft.Colors.RED_50,
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(icono, color=ROJO, size=20),
                            ),
                            ft.Column(
                                [
                                    ft.Text(titulo, size=11, color=self.secundario),
                                    valor,
                                ],
                                spacing=3,
                            ),
                        ],
                        spacing=12,
                    ),
                )
            )
        return ft.Row(tarjetas, spacing=12)

    def panel_informes_actividad(self) -> ft.Control:
        contenido_informes = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Informes generados", size=16, weight=ft.FontWeight.BOLD, color=self.texto),
                        ft.Icon(ft.Icons.DESCRIPTION, color=ROJO, size=18),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                self.lista_informes,
            ],
            expand=True,
            spacing=10,
        )
        contenido_actividad = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Actividad", size=16, weight=ft.FontWeight.BOLD, color=self.texto),
                        ft.Icon(ft.Icons.BOLT, color=ROJO, size=18),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                self.actividad,
            ],
            expand=True,
            spacing=10,
        )
        return ft.Column(
            [
                self.tarjeta(contenido_informes, expand=True),
                self.tarjeta(contenido_actividad, expand=True),
            ],
            expand=3,
            spacing=16,
        )

    def panel_chat(self) -> ft.Control:
        return ft.Container(
            width=340,
            bgcolor=self.superficie,
            border=ft.Border.all(1, self.borde),
            border_radius=14,
            padding=16,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=36,
                                height=36,
                                border_radius=10,
                                bgcolor=ft.Colors.RED_50,
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.SMART_TOY, color=ROJO, size=19),
                            ),
                            ft.Column(
                                [
                                    ft.Text("Chat con agente", size=15, weight=ft.FontWeight.BOLD, color=self.texto),
                                    ft.Text("Local · Sin conexión externa", size=11, color=self.secundario),
                                ],
                                spacing=2,
                            ),
                        ],
                        spacing=9,
                    ),
                    ft.Divider(height=14, color=self.borde),
                    self.conversacion,
                    ft.Row(
                        [
                            self.entrada_chat,
                            ft.IconButton(
                                icon=ft.Icons.SEND,
                                icon_color=ft.Colors.WHITE,
                                bgcolor=ROJO,
                                tooltip="Enviar mensaje",
                                on_click=self.enviar_chat,
                            ),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                    ),
                    ft.Text(
                        "Prueba /estado, /informes, /ayuda o /simular",
                        size=10,
                        color=self.secundario,
                    ),
                ],
                expand=True,
                spacing=8,
            ),
        )

    def tarjeta(self, contenido: ft.Control, expand: bool = False) -> ft.Container:
        return ft.Container(
            expand=expand,
            bgcolor=self.superficie,
            border=ft.Border.all(1, self.borde),
            border_radius=14,
            padding=16,
            content=contenido,
        )

    def actualizar_estado(self, _evento: ft.Event | None = None) -> None:
        if not self.exigir_roles(*USER_ROLES):
            return
        mayoristas, canjes, mercado_libre = self.menu._obtener_pendientes()
        archivados = self.menu._obtener_archivados()
        informes = sorted(
            self.menu._obtener_generados(),
            key=lambda ruta: (ruta.stat().st_mtime_ns, ruta.name.casefold()),
            reverse=True,
        )
        self.informes = informes
        self.contadores["pdf"].value = str(len(mayoristas))
        self.contadores["canjes"].value = str(len(canjes))
        self.contadores["ml"].value = str(len(mercado_libre))
        self.contadores["informes"].value = str(len(informes))
        total_archivados = sum(map(len, archivados))
        self.pendientes_texto.value = (
            f"Archivados: {total_archivados} · Informes: {len(informes)}"
        )
        self.lista_informes.controls.clear()
        if not informes:
            self.lista_informes.controls.append(
                ft.Text("Todavía no hay informes.", size=12, color=self.secundario)
            )
        else:
            for ruta in informes:
                self.lista_informes.controls.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.DESCRIPTION, color=ROJO, size=19),
                        title=ft.Text(ruta.name, size=12, color=self.texto),
                        on_click=lambda _e, archivo=ruta: self.seleccionar_informe(archivo),
                    )
                )
        if self.page.controls:
            self.page.update()

    def seleccionar_informe(self, ruta: Path) -> None:
        self.informe_seleccionado = ruta
        self.estado_tarea.value = f"Informe seleccionado: {ruta.name}"
        self.page.update()

    def escribir_chat(self, emisor: str, mensaje: str) -> None:
        color = ROJO if emisor == "Tú" else ft.Colors.RED_300
        if emisor == "Tú":
            bgcolor = ft.Colors.RED_900 if self.modo_oscuro else ft.Colors.RED_50
        else:
            bgcolor = ft.Colors.BLUE_GREY_800 if self.modo_oscuro else ft.Colors.GREY_100
        self.conversacion.controls.append(
            ft.Container(
                bgcolor=bgcolor,
                border_radius=10,
                padding=10,
                content=ft.Column(
                    [
                        ft.Text(emisor, size=10, weight=ft.FontWeight.BOLD, color=color),
                        ft.Text(mensaje, size=12, color=self.texto),
                    ],
                    spacing=3,
                ),
            )
        )

    async def enviar_chat(self, _evento: ft.Event | None = None) -> None:
        if not self.exigir_roles(*USER_ROLES):
            return
        mensaje = (self.entrada_chat.value or "").strip()
        if not mensaje:
            return
        self.entrada_chat.value = ""
        self.escribir_chat("Tú", mensaje)
        intencion = detectar_intencion(mensaje)
        if intencion == "estado":
            respuesta = self.resumen_estado()
        elif intencion == "informes":
            respuesta = self.resumen_informes()
        elif intencion == "saludo":
            respuesta = (
                "¡Hola! Puedo consultar el estado y los informes, explicar el "
                "uso del sistema o iniciar una simulación de solo lectura. "
                "Escribe /ayuda para ver las opciones."
            )
        elif intencion == "ayuda":
            respuesta = (
                "Consulta archivos pendientes con /estado, lista informes con "
                "/informes o ejecuta una simulación de solo lectura con /simular. "
                "No puedo iniciar un procesamiento real desde el chat."
            )
        elif intencion == "simular":
            if self.ocupado:
                respuesta = "Ya hay una operación en curso. Inténtalo de nuevo al finalizar."
            elif not any(self.fuentes_seleccionadas()):
                respuesta = "Selecciona al menos una fuente antes de iniciar la simulación."
            elif self.usuario_actual is None or self.usuario_actual.role == "consulta":
                respuesta = "Tu rol no tiene permiso para iniciar simulaciones."
            else:
                respuesta = "Simulación de solo lectura iniciada."
                await self.simular(None)
        else:
            respuesta = (
                "Puedo ayudar con el estado de archivos, los informes y las "
                "simulaciones. Prueba /ayuda."
            )
        self.escribir_chat("Agente", respuesta)
        self.page.update()

    def resumen_estado(self) -> str:
        mayoristas, canjes, mercado_libre = self.menu._obtener_pendientes()
        archivados = self.menu._obtener_archivados()
        return (
            f"Pendientes: {len(mayoristas)} PDF mayoristas, {len(canjes)} Excel "
            f"de canjes y {len(mercado_libre)} DOCX de Mercado Libre. "
            f"Archivados: {sum(map(len, archivados))}. "
            f"Informes disponibles: {len(self.menu._obtener_generados())}."
        )

    def resumen_informes(self) -> str:
        informes = self.menu._obtener_generados()
        if not informes:
            return "Todavía no hay informes generados."
        nombres = [ruta.name for ruta in informes[-10:]]
        return "Informes recientes:\n" + "\n".join(nombres)

    def fuentes_seleccionadas(self) -> tuple[bool, bool, bool]:
        return (
            bool(self.mayoristas.value),
            bool(self.canjes.value),
            bool(self.mercado_libre.value),
        )

    async def simular(self, _evento: ft.Event | None) -> None:
        if not self.exigir_roles("administrador", "operador"):
            return
        await self.procesar(simulacion=True)

    def procesar_real(self, _evento: ft.Event) -> None:
        if not self.exigir_roles("administrador", "operador"):
            return
        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmar procesamiento real"),
            content=ft.Text(
                "Esta operación generará el informe y moverá los documentos "
                "procesados a 'descontados'. No modificará Productos.xlsx. ¿Quieres continuar?"
            ),
            actions=[
                self.boton_dialogo("Cancelar", lambda _e: self.page.pop_dialog()),
                self.boton_dialogo("Confirmar", self.confirmar_procesar_real),
            ],
        )
        self.page.show_dialog(dialogo)

    async def confirmar_procesar_real(self, _evento: ft.Event) -> None:
        if not self.exigir_roles("administrador", "operador"):
            return
        self.page.pop_dialog()
        await self.procesar(simulacion=False)

    async def procesar(self, simulacion: bool) -> None:
        if not self.exigir_roles("administrador", "operador"):
            return
        if self.ocupado:
            self.notificar("Ya hay una operación en curso.")
            return
        fuentes = self.fuentes_seleccionadas()
        if not any(fuentes):
            self.notificar("Selecciona al menos una fuente.")
            return

        await self.ejecutar_tarea(
            "Simulación" if simulacion else "Procesamiento real",
            lambda: self.menu.procesar(
                incluir_mayoristas=fuentes[0],
                incluir_canjes=fuentes[1],
                incluir_mercado_libre=fuentes[2],
                simulacion=simulacion,
            ),
        )

    async def ejecutar_tarea(
        self, nombre: str, accion: Callable[[], object]
    ) -> bool:
        self.ocupado = True
        self.estado_tarea.value = f"En curso: {nombre}"
        self.actualizar_estado_botones()
        self.page.update()

        salida = io.StringIO()
        exito = False

        def ejecutar() -> None:
            with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(salida):
                accion()

        try:
            await asyncio.to_thread(ejecutar)
        except Exception:
            detalle = traceback.format_exc()
            self.actividad.controls.append(
                ft.Text(
                    f"[ERROR]\n{detalle}",
                    color=ft.Colors.RED_400 if self.modo_oscuro else ft.Colors.RED_700,
                    size=14,
                )
            )
            self.estado_tarea.value = f"{nombre} terminó con un error."
            self.notificar("La operación falló. Revisa el panel Actividad.")
        else:
            texto = salida.getvalue().strip()
            if texto:
                self.actividad.controls.append(
                    ft.Text(texto, color=self.texto, size=14)
                )
            self.estado_tarea.value = f"{nombre} finalizada."
            exito = True
        finally:
            self.ocupado = False
            self.actualizar_estado_botones()
            self.actualizar_estado()
        return exito

    def actualizar_estado_botones(self) -> None:
        for control in self.controles_tarea:
            control.disabled = self.ocupado
        self.page.update()

    def notificar(self, mensaje: str) -> None:
        dialogo = ft.AlertDialog(
            title=ft.Text("Aviso"),
            content=ft.Text(mensaje),
            actions=[
                self.boton_dialogo("Aceptar", lambda _e: self.page.pop_dialog())
            ],
        )
        self.page.show_dialog(dialogo)

    def ruta_informe(self) -> Path | None:
        if not self.exigir_roles(*USER_ROLES):
            return None
        if self.informe_seleccionado and self.informe_seleccionado.exists():
            return self.informe_seleccionado
        if self.informes:
            self.informe_seleccionado = self.informes[0]
            return self.informe_seleccionado
        self.notificar("Todavía no hay informes generados.")
        return None

    def abrir_informe(self, _evento: ft.Event) -> None:
        ruta = self.ruta_informe()
        if ruta is None:
            return
        try:
            os.startfile(ruta)  # type: ignore[attr-defined]
        except OSError as error:
            self.notificar(f"No se pudo abrir el informe:\n{error}")

    def abrir_carpeta_informe(self, ruta: Path) -> None:
        subprocess.Popen(["explorer.exe", f"/select,{ruta}"])

    def compartir_correo(self, _evento: ft.Event) -> None:
        if not self.exigir_roles(*USER_ROLES):
            return
        ruta = self.ruta_informe()
        if ruta is None:
            return
        asunto = urllib.parse.quote(f"Informe de descuentos: {ruta.name}")
        cuerpo = urllib.parse.quote(f"Adjunto el informe de descuentos {ruta.name}.")
        try:
            self.abrir_carpeta_informe(ruta)
            os.startfile(f"mailto:?subject={asunto}&body={cuerpo}")  # type: ignore[attr-defined]
        except OSError as error:
            self.notificar(f"No se pudo abrir el correo o el informe:\n{error}")

    def compartir_whatsapp(self, _evento: ft.Event) -> None:
        if not self.exigir_roles(*USER_ROLES):
            return
        ruta = self.ruta_informe()
        if ruta is None:
            return
        try:
            self.abrir_carpeta_informe(ruta)
            if not webbrowser.open("https://web.whatsapp.com/"):
                raise RuntimeError("No se pudo abrir WhatsApp Web.")
        except (OSError, RuntimeError) as error:
            self.notificar(f"No se pudo abrir WhatsApp o el informe:\n{error}")

    def confirmar_restaurar(self, _evento: ft.Event) -> None:
        if not self.exigir_roles("administrador"):
            return
        fechas = self.menu.fechas_descuento_disponibles()
        if not fechas:
            self.notificar(
                "No hay documentos archivados asociados a informes de descuento."
            )
            return
        seleccion_fecha = ft.Dropdown(
            label="Fecha de descuento",
            value=fechas[0],
            options=[
                ft.DropdownOption(
                    key=fecha,
                    text=datetime.strptime(fecha, "%Y-%m-%d").strftime("%d/%m/%Y"),
                )
                for fecha in fechas
            ],
            width=250,
        )
        self.seleccion_fecha_restauracion = seleccion_fecha
        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Restaurar documentos"),
            content=ft.Column(
                [
                    ft.Text(
                        "Selecciona la fecha de descuento de los documentos "
                        "que quieres restaurar. Si ya existe un archivo con el "
                        "mismo nombre en pendientes, será reemplazado."
                    ),
                    seleccion_fecha,
                ],
                tight=True,
                spacing=12,
            ),
            actions=[
                self.boton_dialogo("Cancelar", lambda _e: self.page.pop_dialog()),
                self.boton_dialogo("Restaurar", self.restaurar),
            ],
        )
        self.page.show_dialog(dialogo)

    async def restaurar(self, _evento: ft.Event) -> None:
        if not self.exigir_roles("administrador"):
            return
        if self.seleccion_fecha_restauracion is None:
            self.notificar("No se cargó la selección de fecha.")
            return
        fecha = self.seleccion_fecha_restauracion.value
        if not fecha:
            self.notificar("Selecciona una fecha de descuento.")
            return
        self.page.pop_dialog()
        await self.ejecutar_tarea(
            "Restauración de documentos",
            lambda: self.menu.restaurar_para_pruebas(fecha),
        )

    def mostrar_gestion_usuarios(self, _evento: ft.Event | None = None) -> None:
        if not self.exigir_roles("administrador"):
            return
        nuevo_usuario = ft.TextField(label="Nombre de usuario")
        nueva_clave = ft.TextField(
            label="Contraseña (mínimo 10 caracteres)",
            password=True,
            can_reveal_password=True,
        )
        nuevo_rol = ft.Dropdown(
            label="Rol",
            value="consulta",
            options=[
                ft.DropdownOption(key=role, text=role.capitalize())
                for role in USER_ROLES
            ],
            width=220,
        )
        mensaje = ft.Text(color=ft.Colors.RED_400, size=12)
        usuarios = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=240)
        crear_boton = ft.Button(
            "Crear usuario",
            icon=ft.Icons.PERSON_ADD,
            bgcolor=ROJO,
            color=ft.Colors.WHITE,
        )
        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Gestión de usuarios"),
            content=ft.Column(
                [
                    nuevo_usuario,
                    nueva_clave,
                    nuevo_rol,
                    mensaje,
                    crear_boton,
                    ft.Divider(),
                    usuarios,
                ],
                tight=True,
                width=520,
            ),
            actions=[
                self.boton_dialogo("Cerrar", lambda _e: self.page.pop_dialog())
            ],
        )

        def actualizar_lista() -> None:
            usuarios.controls.clear()
            actual = self.usuario_actual
            for usuario in self.user_store.list_users():
                selector_rol = ft.Dropdown(
                    value=usuario.role,
                    options=[
                        ft.DropdownOption(key=role, text=role.capitalize())
                        for role in USER_ROLES
                    ],
                    width=160,
                    disabled=actual is not None and usuario.id == actual.id,
                )
                boton_estado = ft.TextButton(
                    "Desactivar" if usuario.active else "Activar",
                    on_click=lambda _e, user_id=usuario.id, active=not usuario.active: cambiar_estado(
                        user_id, active
                    ),
                    disabled=actual is not None and usuario.id == actual.id,
                )
                selector_rol.on_select = lambda _e, user_id=usuario.id, dropdown=selector_rol: cambiar_rol(
                    user_id, dropdown.value or ""
                )
                usuarios.controls.append(
                    ft.Row(
                        [
                            ft.Text(
                                f"{usuario.username}{' (inactivo)' if not usuario.active else ''}",
                                expand=True,
                            ),
                            selector_rol,
                            boton_estado,
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                )

        def cambiar_rol(user_id: int, role: str) -> None:
            if not self.exigir_roles("administrador"):
                return
            try:
                self.user_store.update_role(user_id, role)
                mensaje.value = ""
            except (ValueError, UserStoreError) as error:
                mensaje.value = str(error)
            actualizar_lista()
            self.page.update()

        def cambiar_estado(user_id: int, active: bool) -> None:
            if not self.exigir_roles("administrador"):
                return
            try:
                self.user_store.set_active(user_id, active)
                mensaje.value = ""
            except UserStoreError as error:
                mensaje.value = str(error)
            actualizar_lista()
            self.page.update()

        def crear_usuario(_evento: ft.Event) -> None:
            if not self.exigir_roles("administrador"):
                return
            try:
                self.user_store.create_user(
                    nuevo_usuario.value or "",
                    nueva_clave.value or "",
                    nuevo_rol.value or "",
                )
            except (ValueError, UserStoreError) as error:
                mensaje.value = str(error)
            else:
                nuevo_usuario.value = ""
                nueva_clave.value = ""
                mensaje.value = "Usuario creado."
            actualizar_lista()
            self.page.update()

        crear_boton.on_click = crear_usuario
        actualizar_lista()
        self.page.show_dialog(dialogo)

    def mostrar_acceso_admin(self, _evento: ft.Event) -> None:
        if not self.exigir_roles("administrador"):
            return
        self.mostrar_formulario_producto()

    def mostrar_gestion_productos(self, _evento: ft.Event | None = None) -> None:
        if not self.exigir_roles("administrador"):
            return
        stock_manager = StockManager(self.menu.ruta_excel_base)
        busqueda = ft.TextField(
            label="Buscar por código o nombre",
            expand=True,
        )
        productos = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO)

        def actualizar_lista(_evento: ft.Event | None = None) -> None:
            productos.controls.clear()
            consulta = (busqueda.value or "").strip().casefold()
            for producto in stock_manager.listar_productos():
                codigo = str(producto["code"])
                nombre = str(producto["name"])
                activo = bool(producto["active"])
                if consulta and consulta not in f"{codigo} {nombre}".casefold():
                    continue
                productos.controls.append(
                    ft.Container(
                        padding=8,
                        border=ft.Border.all(1, self.borde),
                        border_radius=8,
                        content=ft.Row(
                            [
                                ft.Text(codigo, width=100, color=self.texto),
                                ft.Text(nombre, expand=True, color=self.texto),
                                ft.Text(
                                    str(producto["stock"]),
                                    width=70,
                                    color=self.texto,
                                ),
                                ft.Text(
                                    "Activo" if activo else "Inactivo",
                                    width=80,
                                    color=(
                                        ft.Colors.GREEN_400
                                        if activo
                                        else self.secundario
                                    ),
                                ),
                                ft.TextButton(
                                    "Editar",
                                    on_click=lambda _e, item=producto: editar(item),
                                ),
                                ft.TextButton(
                                    "Desactivar" if activo else "Reactivar",
                                    on_click=lambda _e, code=codigo, status=activo: confirmar_estado(
                                        code, not status
                                    ),
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    )
                )
            if not productos.controls:
                productos.controls.append(
                    ft.Text("No se encontraron productos.", color=self.secundario)
                )
            self.page.update()

        def editar(producto) -> None:
            if not self.exigir_roles("administrador"):
                return
            codigo_original = str(producto["code"])
            campo_codigo = ft.TextField(label="Código", value=codigo_original)
            campo_nombre = ft.TextField(
                label="Nombre", value=str(producto["name"])
            )
            campo_stock = ft.TextField(
                label="Stock",
                value=str(producto["stock"]),
                keyboard_type=ft.KeyboardType.NUMBER,
            )
            campos: list[ft.Control] = [
                campo_codigo,
                campo_nombre,
                campo_stock,
            ]

            async def guardar_edicion(_evento: ft.Event) -> None:
                if not self.exigir_roles("administrador"):
                    return
                codigo = (campo_codigo.value or "").strip()
                nombre = (campo_nombre.value or "").strip()
                stock_texto = (campo_stock.value or "").strip()
                if not codigo or not nombre or not stock_texto:
                    self.notificar("Completa el código, el nombre y el stock.")
                    return
                try:
                    stock = int(stock_texto)
                except ValueError:
                    self.notificar("El stock debe ser un número entero.")
                    return
                self.page.pop_dialog()
                actualizado = await self.ejecutar_tarea(
                    "Edición de producto",
                    lambda: stock_manager.actualizar_producto(
                        codigo_original, codigo, nombre, stock
                    ),
                )
                if actualizado:
                    actualizar_lista()

            dialogo_edicion = ft.AlertDialog(
                modal=True,
                title=ft.Text(f"Editar producto {codigo_original}"),
                content=ft.Column(campos, tight=True, width=380),
                actions=[
                    self.boton_dialogo(
                        "Cancelar", lambda _e: self.page.pop_dialog()
                    ),
                    self.boton_dialogo("Guardar", guardar_edicion),
                ],
            )
            self.page.show_dialog(dialogo_edicion)

        def confirmar_estado(codigo: str, activo: bool) -> None:
            if not self.exigir_roles("administrador"):
                return
            accion = "reactivar" if activo else "desactivar"

            async def aceptar_estado(_evento: ft.Event) -> None:
                await cambiar_estado(codigo, activo)

            dialogo_estado = ft.AlertDialog(
                modal=True,
                title=ft.Text(f"Confirmar {accion}"),
                content=ft.Text(
                    (
                        f"El producto {codigo} volverá a incluirse en futuros informes."
                        if activo
                        else f"El producto {codigo} se conservará en el catálogo, "
                        "pero no se incluirá en futuros informes."
                    )
                ),
                actions=[
                    self.boton_dialogo(
                        "Cancelar", lambda _e: self.page.pop_dialog()
                    ),
                    self.boton_dialogo(
                        accion.capitalize(),
                        aceptar_estado,
                    ),
                ],
            )
            self.page.show_dialog(dialogo_estado)

        async def cambiar_estado(codigo: str, activo: bool) -> None:
            if not self.exigir_roles("administrador"):
                return
            self.page.pop_dialog()
            actualizado = await self.ejecutar_tarea(
                "Actualización del estado del producto",
                lambda: stock_manager.cambiar_estado_producto(codigo, activo),
            )
            if actualizado:
                actualizar_lista()

        def agregar(_evento: ft.Event) -> None:
            if not self.exigir_roles("administrador"):
                return
            self.mostrar_formulario_producto(actualizar_lista)

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Gestión de productos"),
            content=ft.Column(
                [
                    ft.Text(
                        "Las bajas son lógicas: el producto se conserva, "
                        "pero no aparece en futuros informes."
                    ),
                    ft.Row(
                        [
                            busqueda,
                            ft.Button(
                                "Agregar producto",
                                icon=ft.Icons.ADD,
                                on_click=agregar,
                                bgcolor=ROJO,
                                color=ft.Colors.WHITE,
                            ),
                        ]
                    ),
                    ft.Row(
                        [
                            ft.Text(
                                "Código", width=100, weight=ft.FontWeight.BOLD
                            ),
                            ft.Text(
                                "Nombre", expand=True, weight=ft.FontWeight.BOLD
                            ),
                            ft.Text("Stock", width=70, weight=ft.FontWeight.BOLD),
                            ft.Text("Estado", width=80, weight=ft.FontWeight.BOLD),
                            ft.Container(width=145),
                        ]
                    ),
                    ft.Container(
                        height=420,
                        content=productos,
                    ),
                ],
                tight=True,
                width=900,
            ),
            actions=[
                self.boton_dialogo("Cerrar", lambda _e: self.page.pop_dialog())
            ],
        )
        busqueda.on_change = actualizar_lista
        actualizar_lista()
        self.page.show_dialog(dialogo)

    def mostrar_formulario_producto(
        self, al_guardar: Callable[[], None] | None = None
    ) -> None:
        if not self.exigir_roles("administrador"):
            return
        campos = {
            "codigo": ft.TextField(label="Código del nuevo producto"),
            "nombre": ft.TextField(label="Nombre del producto"),
            "referencia": ft.TextField(label="Código del producto anterior"),
            "stock": ft.TextField(label="Stock inicial (opcional)", keyboard_type=ft.KeyboardType.NUMBER),
        }

        async def guardar(_evento: ft.Event) -> None:
            if not self.exigir_roles("administrador"):
                return
            codigo = (campos["codigo"].value or "").strip()
            nombre = (campos["nombre"].value or "").strip()
            referencia = (campos["referencia"].value or "").strip()
            stock_texto = (campos["stock"].value or "").strip()
            if not codigo or not nombre or not referencia:
                self.notificar("Completa el código, el nombre y el código de referencia.")
                return
            try:
                stock = int(stock_texto) if stock_texto else None
            except ValueError:
                self.notificar("El stock inicial debe ser un número entero.")
                return

            self.page.pop_dialog()

            def insertar() -> None:
                stock_manager = StockManager(self.menu.ruta_excel_base)
                exito, mensaje, _ = stock_manager.agregar_producto_en_posicion(
                    codigo_nuevo=codigo,
                    nombre_nuevo=nombre,
                    codigo_arriba=referencia,
                    stock_inicial=stock,
                )
                if not exito:
                    raise ValueError(mensaje)
                print(f"[OK] {mensaje}")

            creado = await self.ejecutar_tarea("Alta de producto", insertar)
            if creado and al_guardar is not None:
                al_guardar()

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Datos del nuevo producto"),
            content=ft.Column(list(campos.values()), tight=True, width=380),
            actions=[
                self.boton_dialogo("Cancelar", lambda _e: self.page.pop_dialog()),
                self.boton_dialogo("Guardar", guardar),
            ],
        )
        self.page.show_dialog(dialogo)

async def main(page: ft.Page) -> None:
    InterfazFlet(page)


def iniciar() -> None:
    ft.run(
        main,
        view=ft.AppView.FLET_APP,
        name="Agente de control de stock",
    )
