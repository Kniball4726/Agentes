"""Diálogo para la gestión y conmutación de ambientes (Producción / QA) exclusivo para el usuario Master."""

from __future__ import annotations

from typing import Any
import flet as ft

from ..design import confirmar_accion_destructiva, tono_legible
from ..theme import ROJO
from ...core.environment import (
    get_environment,
    is_qa_environment,
    set_environment,
)
from ...qa.seeder import inicializar_ambiente_qa


def mostrar_gestion_ambientes(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana modal exclusiva para que el usuario Master cambie entre Producción y QA."""
    if not interfaz.exigir_roles("master"):
        return

    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    env_actual = get_environment()
    seleccion = [env_actual]

    # Indicador de estado actual
    es_qa = is_qa_environment()
    color_banner = tono_legible("AMBER" if es_qa else "GREEN", es_oscuro)
    texto_banner = "AMBIENTE QA / PRUEBAS ACTIVO" if es_qa else "AMBIENTE DE PRODUCCIÓN ACTIVO"
    desc_banner = (
        "Trabajando en modo aislado con base de datos 'data_qa/' y planillas 'Descuentos_QA/'. Las operaciones no afectan stock real."
        if es_qa
        else "Trabajando sobre la base de datos central 'data/' y planillas 'Descuentos/'. Operación comercial real."
    )

    banner_estado = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.BUG_REPORT if es_qa else ft.Icons.VERIFIED, color=color_banner, size=24),
                ft.Column(
                    [
                        ft.Text(texto_banner, size=13, weight=ft.FontWeight.BOLD, color=color_banner),
                        ft.Text(desc_banner, size=11, color=interfaz.texto, expand=True),
                    ],
                    spacing=2,
                    expand=True,
                ),
            ],
            spacing=10,
        ),
        bgcolor=ft.Colors.with_opacity(0.12, color_banner),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.4, color_banner)),
        border_radius=8,
        padding=12,
    )

    # Selector de ambiente
    radio_group = ft.RadioGroup(
        value=env_actual,
        content=ft.Column(
            [
                ft.Container(
                    padding=10,
                    border_radius=8,
                    bgcolor=ft.Colors.WHITE_10 if es_oscuro else ft.Colors.GREY_100,
                    content=ft.Row(
                        [
                            ft.Radio(value="production", label=""),
                            ft.Column(
                                [
                                    ft.Text("🟢 Producción (Datos Reales de Empresa)", size=12, weight=ft.FontWeight.BOLD),
                                    ft.Text("Bases: data/ | Planillas: Descuentos/ | Operación regular", size=10, color=interfaz.secundario, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ],
                        spacing=8,
                    ),
                ),
                ft.Container(
                    padding=10,
                    border_radius=8,
                    bgcolor=ft.Colors.WHITE_10 if es_oscuro else ft.Colors.GREY_100,
                    content=ft.Row(
                        [
                            ft.Radio(value="qa", label=""),
                            ft.Column(
                                [
                                    ft.Text("🟡 Ambiente de Pruebas / QA (Aislado)", size=12, weight=ft.FontWeight.BOLD),
                                    ft.Text("Bases: data_qa/ | Planillas: Descuentos_QA/ | Seguro para capacitación y test", size=10, color=interfaz.secundario, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ],
                        spacing=8,
                    ),
                ),
            ],
            spacing=8,
        ),
    )

    def al_cambiar_radio(e: ft.Event) -> None:
        seleccion[0] = radio_group.value

    radio_group.on_change = al_cambiar_radio

    btn_aplicar = ft.Button(
        "Aplicar y Cambiar Ambiente",
        icon=ft.Icons.CHECK,
        bgcolor=ROJO,
        color=ft.Colors.WHITE,
    )

    btn_reseed = ft.Button(
        "🔄 Reinicializar Datos QA",
        icon=ft.Icons.RESTORE,
        bgcolor=ft.Colors.AMBER_700,
        color=ft.Colors.WHITE,
        tooltip="Restaura los usuarios, productos y planillas de prueba originales en data_qa/",
    )

    async def _ejecutar_cambio_ambiente(nuevo_env: str) -> None:
        interfaz.page.pop_dialog()

        def ejecutar() -> None:
            if nuevo_env == "qa":
                inicializar_ambiente_qa(forzar_reinicio=False)

            set_environment(nuevo_env, persistir=True)

            if hasattr(interfaz, "recargar_ambiente"):
                interfaz.recargar_ambiente()

            try:
                order_store = getattr(interfaz, "order_store", None)
                if order_store and hasattr(order_store, "registrar_auditoria"):
                    usr = getattr(getattr(interfaz, "usuario_actual", None), "username", "Master")
                    order_store.registrar_auditoria(usr, "CAMBIO_AMBIENTE", f"Cambio de ambiente: {env_actual} -> {nuevo_env}")
            except Exception:
                pass

            interfaz.sincronizar_sesiones(
                aviso_colaborativo=f"🔄 El usuario Master cambió el entorno a {nuevo_env.upper()}."
            )

        await interfaz.ejecutar_tarea(f"Cambiando a entorno {nuevo_env.upper()}", ejecutar)
        interfaz.notificar(f"Ambiente cambiado exitosamente a: {nuevo_env.upper()}.")

    def al_aplicar_cambio(_e: ft.Event) -> None:
        nuevo_env = seleccion[0]
        if nuevo_env == env_actual:
            interfaz.page.pop_dialog()
            return

        def _confirmado() -> None:
            run_task_fn = getattr(interfaz.page, "run_task", None)
            if callable(run_task_fn) and not getattr(interfaz.page, "_is_mock", False):
                run_task_fn(_ejecutar_cambio_ambiente, nuevo_env)
            else:
                import asyncio

                asyncio.run(_ejecutar_cambio_ambiente(nuevo_env))

        confirmar_accion_destructiva(
            interfaz,
            f"Confirmar Cambio a {nuevo_env.upper()}",
            f"¿Confirmas cambiar el ambiente de ejecución activo de '{env_actual.upper()}' a '{nuevo_env.upper()}'?\n"
            "Se cerrarán las sesiones API en memoria y se reconectarán los almacenes de datos.",
            _confirmado,
            texto_confirmar=f"Sí, Cambiar a {nuevo_env.upper()}",
            roles_permitidos=("master",),
        )

    btn_aplicar.on_click = al_aplicar_cambio

    async def _ejecutar_reseed_qa() -> None:
        def ejecutar() -> None:
            inicializar_ambiente_qa(forzar_reinicio=True)
            if hasattr(interfaz, "recargar_ambiente"):
                interfaz.recargar_ambiente()
            else:
                from ...api.deps import reset_api_stores

                reset_api_stores(revocar_sesiones_memoria=True)
            try:
                order_store = getattr(interfaz, "order_store", None)
                if order_store and hasattr(order_store, "registrar_auditoria"):
                    usr = getattr(getattr(interfaz, "usuario_actual", None), "username", "Master")
                    order_store.registrar_auditoria(usr, "RESEED_QA", "Reinicialización completa de bases y planillas QA")
            except Exception:
                pass
            interfaz.sincronizar_sesiones(
                aviso_colaborativo="🔄 El usuario Master reinicializó los datos semilla del ambiente QA."
            )

        await interfaz.ejecutar_tarea("Reinicializando datos QA", ejecutar)
        interfaz.notificar("Datos de prueba de QA reinicializados con éxito.")

    def al_reseed_qa(_e: ft.Event) -> None:
        def _confirmado_reseed() -> None:
            run_task_fn = getattr(interfaz.page, "run_task", None)
            if callable(run_task_fn) and not getattr(interfaz.page, "_is_mock", False):
                run_task_fn(_ejecutar_reseed_qa)
            else:
                import asyncio

                asyncio.run(_ejecutar_reseed_qa())

        confirmar_accion_destructiva(
            interfaz,
            "Confirmar Reinicialización de QA",
            "¿Confirmas restaurar las bases de datos y planillas de 'data_qa/' y 'Descuentos_QA/' a sus valores semilla originales?",
            _confirmado_reseed,
            texto_confirmar="Sí, Reinicializar QA",
            roles_permitidos=("master",),
        )

    btn_reseed.on_click = al_reseed_qa

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.TUNE, color=ROJO, size=24),
                ft.Text("Gestión de Ambientes de Ejecución", size=16, weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=interfaz.ancho_adaptable(580) if hasattr(interfaz, "ancho_adaptable") else 580,
            content=ft.Column(
                [
                    banner_estado,
                    ft.Text(
                        "Selecciona el ambiente en el cual operará el sistema. Los cambios aplican de forma inmediata y persisten entre reinicios.",
                        size=11,
                        color=interfaz.secundario,
                    ),
                    radio_group,
                    ft.Divider(height=1),
                    ft.Row(
                        [
                            ft.Text("Mantenimiento de QA:", size=11, weight=ft.FontWeight.BOLD),
                            btn_reseed,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        wrap=True,
                        run_spacing=6,
                    ),
                ],
                spacing=10,
                tight=True,
            ),
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda _: interfaz.page.pop_dialog()),
            btn_aplicar,
        ],
        actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    interfaz.page.show_dialog(dialogo)
    interfaz.page.update()
