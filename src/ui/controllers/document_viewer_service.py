"""Servicio independiente para apertura, visualización y compartición de documentos."""

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
from typing import Any, Callable

import flet as ft

from ...paths import application_root
from ..dialogs import (
    compartir_correo,
    compartir_whatsapp,
    enviar_correo_cierre,
    mostrar_dialogo_informes,
    mostrar_dialogo_opciones_documento,
)

logger = logging.getLogger(__name__)


class DocumentViewerService:
    """Provee operaciones desacopladas para abrir informes, manuales de rol y compartir archivos."""

    def __init__(
        self,
        host: Any,
        check_roles_fn: Callable[..., bool] | None = None,
        notify_fn: Callable[[str], None] | None = None,
        app_root_fn: Callable[[], Path] | None = None,
    ) -> None:
        self._host = host
        self._check_roles_fn = check_roles_fn
        self._notify_fn = notify_fn
        self._app_root_fn = app_root_fn or application_root
        self._opening_url = False

    def _exigir_roles(self, *roles: Any) -> bool:
        fn = self._check_roles_fn or getattr(self._host, "exigir_roles", None)
        return bool(fn(*roles)) if callable(fn) else True

    def _notificar(self, mensaje: str) -> None:
        fn = self._notify_fn or getattr(self._host, "notificar", None)
        if callable(fn):
            fn(mensaje)

    def _open_url_via_host_or_self(self, url: str) -> None:
        custom_opener = getattr(self._host, "abrir_url_en_navegador", None)
        if callable(custom_opener) and not self._opening_url:
            self._opening_url = True
            try:
                custom_opener(url)
                return
            finally:
                self._opening_url = False
        self.abrir_url_en_navegador(url)

    def abrir_url_en_navegador(self, url: str) -> None:
        """Abre una URL en nueva pestaña/ventana compatible con Flet clásico, 1.0 y navegador."""
        page = getattr(self._host, "page", None)
        if not page:
            return

        if hasattr(page, "launch_url") and callable(getattr(page, "launch_url")):
            try:
                try:
                    page.launch_url(url, web_window_name="_blank")
                except TypeError:
                    page.launch_url(url)
                return
            except Exception:
                pass

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

        try:
            webbrowser.open(url)
        except Exception:
            pass

    def ruta_informe(self) -> Path | None:
        if not self._exigir_roles("operador", "picker", "administrador", "master", "consulta"):
            return None
        seleccionado = getattr(self._host, "informe_seleccionado", None)
        if seleccionado and seleccionado.exists():
            return seleccionado
        informes = getattr(self._host, "informes", None) or []
        menu = getattr(self._host, "menu", None)
        if not informes and menu and hasattr(menu, "_obtener_generados"):
            try:
                informes = menu._obtener_generados()
                self._host.informes = informes
            except Exception:
                informes = []
                self._host.informes = []
        if informes:
            self._host.informe_seleccionado = informes[-1]
            return self._host.informe_seleccionado
        self._notificar("Todavía no hay informes generados.")
        return None

    def mostrar_manual_usuario(self, _evento: ft.Event | None = None) -> None:
        """Abre directamente la documentación oficial en PDF correspondiente al rol activo."""
        usuario = getattr(self._host, "usuario_actual", None)
        if usuario is None:
            return

        role = (usuario.role or "operador").strip().lower()
        mapa_archivos = {
            "operador": "Manual_Operador.pdf",
            "picker": "Manual_Picker.pdf",
            "administrador": "Manual_Administrador.pdf",
            "master": "Manual_Master.pdf",
            "consulta": "Manual_Consulta.pdf",
        }
        nombre_archivo = mapa_archivos.get(role, "Manual_Operador.pdf")
        doc_dir = Path(self._app_root_fn()) / "Documentacion"
        doc_dir.mkdir(parents=True, exist_ok=True)
        ruta_pdf = doc_dir / nombre_archivo

        if not ruta_pdf.exists():
            try:
                from Documentacion.generar_manual_pdf import generar_todos_los_manuales
                generar_todos_los_manuales(doc_dir)
            except Exception as exc_gen:
                logger.warning("No se pudo autogenerar la documentación: %s", exc_gen)

        if not ruta_pdf.exists():
            self._notificar(f"No se encontró el manual oficial: {nombre_archivo}")
            return

        if getattr(self._host.page, "web", False):
            ts = int(ruta_pdf.stat().st_mtime)
            from ...api.deps import crear_token_documento
            dt = crear_token_documento(usuario, recurso=nombre_archivo)
            url_doc = f"/documentacion/{nombre_archivo}?v={ts}&dt={urllib.parse.quote(dt)}"
            try:
                self._open_url_via_host_or_self(url_doc)
            except Exception:
                self.abrir_informe(ruta_especifica=ruta_pdf)
            return

        try:
            os.startfile(ruta_pdf)  # type: ignore[attr-defined]
        except OSError as error:
            self._notificar(f"No se pudo abrir el manual:\n{error}")

    def abrir_informe(
        self,
        _evento: ft.Event | None = None,
        ruta_especifica: Path | None = None,
        directo: bool = False,
        **kwargs: Any,
    ) -> None:
        if hasattr(self._host, "exigir_roles") and not self._exigir_roles(
            "operador", "picker", "administrador", "master", "consulta"
        ):
            return
        if ruta_especifica is None:
            menu = getattr(self._host, "menu", None)
            if menu and hasattr(menu, "_obtener_generados"):
                try:
                    self._host.informes = menu._obtener_generados()
                except Exception:
                    pass
            if not getattr(self._host, "informes", None):
                self._notificar("Todavía no hay informes generados.")
                return
            mostrar_dialogo_informes(self._host)
            return

        ruta_path = Path(ruta_especifica)

        if getattr(self._host.page, "web", False):
            try:
                root = Path(self._app_root_fn()).resolve()
                ruta_res = ruta_path.resolve()
                if ruta_res.is_relative_to(root):
                    rel_p = str(ruta_res.relative_to(root)).replace("\\", "/")
                else:
                    rel_p = ruta_res.name
            except Exception:
                rel_p = ruta_path.name

            url_doc = f"/documentos/ver?p={urllib.parse.quote(rel_p)}"
            usr_actual = getattr(self._host, "usuario_actual", None)
            if usr_actual is not None:
                from ...api.deps import crear_token_documento
                dt = crear_token_documento(usr_actual, recurso=rel_p)
                url_doc = f"{url_doc}&dt={urllib.parse.quote(dt)}"
            self._open_url_via_host_or_self(url_doc)
            return

        if not ruta_path.exists():
            self._notificar(f"No se encontró el archivo de informe:\n{ruta_path.name}")
            return

        try:
            if sys.platform == "win32":
                os.startfile(str(ruta_path.resolve()))  # type: ignore[attr-defined]
            else:
                webbrowser.open(ruta_path.resolve().as_uri())
        except OSError as error:
            try:
                webbrowser.open(ruta_path.resolve().as_uri())
            except Exception:
                self._notificar(f"No se pudo abrir el archivo:\n{error}")

    def mostrar_opciones_documento(
        self,
        ruta_archivo: str | Path | None = None,
        _evento: ft.Event | None = None,
    ) -> None:
        """Muestra el diálogo modal con opciones de descarga e impresión Windows."""
        target = ruta_archivo or self.ruta_informe()
        if target is None:
            return
        mostrar_dialogo_opciones_documento(self._host, target)

    def abrir_carpeta_informe(self, ruta: Path | None = None, ruta_especifica: Path | None = None) -> None:
        target = ruta or ruta_especifica or self.ruta_informe()
        if target is None:
            return
        target = Path(target)
        if getattr(self._host.page, "web", False):
            self._notificar(f"Ubicación en servidor: {target.parent if target.is_file() else target}")
            return
        try:
            if sys.platform == "win32":
                if target.is_file():
                    subprocess.Popen(["explorer.exe", f"/select,{target.resolve()}"])
                else:
                    subprocess.Popen(["explorer.exe", str(target.resolve())])
            else:
                webbrowser.open(target.parent.resolve().as_uri() if target.is_file() else target.resolve().as_uri())
        except Exception as exc:
            self._notificar(f"No se pudo abrir la carpeta:\n{exc}")

    def compartir_correo(
        self,
        _evento: ft.Event | None = None,
        ruta_especifica: Path | None = None,
    ) -> None:
        compartir_correo(self._host, _evento, ruta_especifica)

    def compartir_whatsapp(
        self,
        _evento: ft.Event | None = None,
        ruta_especifica: Path | None = None,
    ) -> None:
        compartir_whatsapp(self._host, _evento, ruta_especifica)

    def enviar_correo_cierre(self, *args: Any, **kwargs: Any) -> Any:
        return enviar_correo_cierre(self._host, *args, **kwargs)
