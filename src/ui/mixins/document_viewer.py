"""Mixin para apertura, visualización y compartición de documentos e informes."""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
import subprocess
import sys
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Any

import flet as ft

from ..dialogs import (
    compartir_correo,
    compartir_whatsapp,
    enviar_correo_cierre,
    mostrar_dialogo_informes,
)
from ...paths import application_root

logger = logging.getLogger(__name__)


class DocumentViewerMixin:
    """Provee métodos para abrir informes, manuales de usuario y compartir documentos."""

    page: ft.Page
    usuario_actual: Any
    informes: list[Path]
    informe_seleccionado: Path | None

    def abrir_url_en_navegador(self, url: str) -> None:
        """Abre una URL en nueva pestaña/ventana compatible con Flet clásico, 1.0 y navegador."""
        page = self.page
        if not page:
            return

        # 1. Page.launch_url clásico si está disponible
        if hasattr(page, "launch_url") and callable(getattr(page, "launch_url")):
            try:
                try:
                    page.launch_url(url, web_window_name="_blank")
                except TypeError:
                    page.launch_url(url)
                return
            except Exception:
                pass

        # 2. UrlLauncher como servicio registrado (Flet 1.0+)
        try:
            launcher = None
            if hasattr(page, "services") and isinstance(page.services, list):
                for s in page.services:
                    if isinstance(s, ft.UrlLauncher):
                        launcher = s
                        break
                if not launcher:
                    launcher = ft.UrlLauncher()
                    page.services.append(launcher)
                    try:
                        page.update()
                    except Exception:
                        pass

            if launcher:
                if hasattr(page, "run_task") and callable(page.run_task):
                    page.run_task(launcher.launch_url, url, web_only_window_name="_blank")
                else:
                    coro = launcher.launch_url(url, web_only_window_name="_blank")
                    if inspect.iscoroutine(coro):
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                asyncio.create_task(coro)
                            else:
                                loop.run_until_complete(coro)
                        except Exception:
                            coro.close()
                return
        except Exception:
            pass

        # 3. Fallback de navegador del sistema
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def ruta_informe(self) -> Path | None:
        if not self.exigir_roles("operador", "picker", "administrador", "master", "consulta"):
            return None
        if self.informe_seleccionado and self.informe_seleccionado.exists():
            return self.informe_seleccionado
        if not self.informes and getattr(self, "menu", None) and hasattr(self.menu, "_obtener_generados"):
            try:
                self.informes = self.menu._obtener_generados()
            except Exception:
                self.informes = []
        if self.informes:
            self.informe_seleccionado = self.informes[-1]
            return self.informe_seleccionado
        self.notificar("Todavía no hay informes generados.")
        return None

    def mostrar_manual_usuario(self, _evento: ft.Event | None = None) -> None:
        """Abre directamente la documentación oficial en PDF correspondiente al rol del usuario activo."""
        if self.usuario_actual is None:
            return

        role = (self.usuario_actual.role or "operador").strip().lower()
        mapa_archivos = {
            "operador": "Manual_Operador.pdf",
            "picker": "Manual_Picker.pdf",
            "administrador": "Manual_Administrador.pdf",
            "master": "Manual_Master.pdf",
            "consulta": "Manual_Consulta.pdf",
        }
        nombre_archivo = mapa_archivos.get(role, "Manual_Operador.pdf")
        doc_dir = Path(application_root()) / "Documentacion"
        doc_dir.mkdir(parents=True, exist_ok=True)
        ruta_pdf = doc_dir / nombre_archivo

        if not ruta_pdf.exists():
            try:
                from Documentacion.generar_manual_pdf import generar_todos_los_manuales
                generar_todos_los_manuales(doc_dir)
            except Exception as exc_gen:
                logger.warning("No se pudo autogenerar la documentación: %s", exc_gen)

        if not ruta_pdf.exists():
            self.notificar(f"No se encontró el manual oficial: {nombre_archivo}")
            return

        if getattr(self.page, "web", False):
            ts = int(ruta_pdf.stat().st_mtime)
            from ...api.deps import crear_token_documento
            dt = crear_token_documento(self.usuario_actual, recurso=nombre_archivo)
            url_doc = f"/documentacion/{nombre_archivo}?v={ts}&dt={urllib.parse.quote(dt)}"
            try:
                self.abrir_url_en_navegador(url_doc)
            except Exception:
                self.abrir_informe(ruta_especifica=ruta_pdf)
            return

        try:
            os.startfile(ruta_pdf)  # type: ignore[attr-defined]
        except OSError as error:
            self.notificar(f"No se pudo abrir el manual:\n{error}")

    def abrir_informe(self, _evento: ft.Event | None = None, ruta_especifica: Path | None = None) -> None:
        if hasattr(self, "exigir_roles") and not self.exigir_roles(
            "operador", "picker", "administrador", "master", "consulta"
        ):
            return
        if ruta_especifica is None:
            if getattr(self, "menu", None) and hasattr(self.menu, "_obtener_generados"):
                try:
                    self.informes = self.menu._obtener_generados()
                except Exception:
                    pass
            if not self.informes:
                self.notificar("Todavía no hay informes generados.")
                return
            mostrar_dialogo_informes(self)
            return

        ruta_path = Path(ruta_especifica)

        if getattr(self.page, "web", False):
            try:
                root = Path(application_root()).resolve()
                ruta_res = ruta_path.resolve()
                if ruta_res.is_relative_to(root):
                    rel_p = str(ruta_res.relative_to(root)).replace("\\", "/")
                else:
                    rel_p = ruta_res.name
            except Exception:
                rel_p = ruta_path.name

            url_doc = f"/documentos/ver?p={urllib.parse.quote(rel_p)}"
            usr_actual = getattr(self, "usuario_actual", None)
            if usr_actual is not None:
                from ...api.deps import crear_token_documento
                dt = crear_token_documento(usr_actual, recurso=rel_p)
                url_doc = f"{url_doc}&dt={urllib.parse.quote(dt)}"
            self.abrir_url_en_navegador(url_doc)
            return

        if not ruta_path.exists():
            self.notificar(f"No se encontró el archivo de informe:\n{ruta_path.name}")
            return

        try:
            if sys.platform == "win32":
                os.startfile(str(ruta_path.resolve()))  # type: ignore[attr-defined]
            else:
                import webbrowser
                webbrowser.open(ruta_path.resolve().as_uri())
        except OSError as error:
            try:
                import webbrowser
                webbrowser.open(ruta_path.resolve().as_uri())
            except Exception:
                self.notificar(f"No se pudo abrir el archivo:\n{error}")

    def abrir_carpeta_informe(self, ruta: Path | None = None, ruta_especifica: Path | None = None) -> None:
        target = ruta or ruta_especifica
        if target is None:
            target = self.ruta_informe()
        if target is None:
            return
        target = Path(target)
        if getattr(self.page, "web", False):
            self.notificar(f"Ubicación en servidor: {target.parent if target.is_file() else target}")
            return
        try:
            if sys.platform == "win32":
                if target.is_file():
                    subprocess.Popen(["explorer.exe", f"/select,{target.resolve()}"])
                else:
                    subprocess.Popen(["explorer.exe", str(target.resolve())])
            else:
                import webbrowser
                webbrowser.open(target.parent.resolve().as_uri() if target.is_file() else target.resolve().as_uri())
        except Exception as exc:
            self.notificar(f"No se pudo abrir la carpeta:\n{exc}")

    def compartir_correo(
        self,
        _evento: ft.Event | None = None,
        ruta_especifica: Path | None = None,
    ) -> None:
        compartir_correo(self, _evento, ruta_especifica)

    def compartir_whatsapp(
        self,
        _evento: ft.Event | None = None,
        ruta_especifica: Path | None = None,
    ) -> None:
        compartir_whatsapp(self, _evento, ruta_especifica)

    def enviar_correo_cierre(
        self,
        *args,
        **kwargs,
    ) -> None:
        return enviar_correo_cierre(self, *args, **kwargs)
