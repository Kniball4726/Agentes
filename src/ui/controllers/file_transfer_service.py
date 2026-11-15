"""Servicio independiente para transferencia de archivos (subida/descarga vía FilePicker)."""

from __future__ import annotations

import logging
import shutil
import weakref
from pathlib import Path
from typing import Any, Callable

import flet as ft

logger = logging.getLogger(__name__)


class FileTransferService:
    """Gestiona el servicio FilePicker de Flet 1.0 y las operaciones de carga y descarga."""

    def __init__(
        self,
        host: Any,
        notify_fn: Callable[[str], None] | None = None,
        on_files_saved: Callable[[], None] | None = None,
    ) -> None:
        self._host = host
        self._notify_fn = notify_fn
        self._on_files_saved = on_files_saved

    def _notificar(self, mensaje: str) -> None:
        fn = self._notify_fn or getattr(self._host, "notificar", None)
        if callable(fn):
            fn(mensaje)

    def _notificar_guardado(self) -> None:
        if callable(self._on_files_saved):
            self._on_files_saved()
            return
        act = getattr(self._host, "actualizar_estado", None)
        if callable(act):
            act()
        sync = getattr(self._host, "sincronizar_sesiones", None)
        if callable(sync):
            sync()

    def asegurar_file_picker(self, forzar_recrear: bool = False) -> None:
        """Asegura que FilePicker esté registrado exclusivamente como servicio sin contaminar el overlay."""
        page = self._host.page
        reg = getattr(page, "_services", None)
        fp_actual = getattr(self._host, "file_picker", None)

        if forzar_recrear or fp_actual is None:
            if fp_actual is not None:
                if hasattr(page, "overlay") and page.overlay is not None:
                    try:
                        page.overlay = [c for c in page.overlay if c is not fp_actual]
                    except Exception:
                        pass
                if hasattr(page, "services") and page.services is not None:
                    try:
                        page.services = [s for s in page.services if s is not fp_actual]
                    except Exception:
                        pass
                if reg is not None and hasattr(reg, "_services"):
                    try:
                        reg._services = [s for s in reg._services if s is not fp_actual]
                    except Exception:
                        pass
            self._host.file_picker = ft.FilePicker()

        fp = self._host.file_picker
        # En Flet 1.0 FilePicker es un Servicio no visual: mantenerlo fuera de overlay.
        if hasattr(page, "overlay") and page.overlay is not None:
            while fp in page.overlay:
                page.overlay.remove(fp)

        if hasattr(page, "services") and page.services is not None:
            if not any(s is fp for s in page.services):
                page.services.append(fp)

        if type(reg).__name__ == "ServiceRegistry":
            if getattr(reg, "parent", None) is None:
                try:
                    reg._parent = weakref.ref(page)
                except Exception:
                    pass
            if hasattr(reg, "_services") and not any(s is fp for s in reg._services):
                try:
                    reg.register_service(fp)
                except Exception:
                    pass

        try:
            fp._parent = weakref.ref(page)
        except Exception:
            pass

    async def descargar_archivo_navegador(self, ruta: Path) -> None:
        """Envía el contenido de un archivo local al navegador mediante FilePicker.save_file."""
        try:
            self.asegurar_file_picker()
            contenido_bytes = ruta.read_bytes()
            await self._host.file_picker.save_file(
                dialog_title=f"Guardar {ruta.name}",
                file_name=ruta.name,
                src_bytes=contenido_bytes,
            )
        except Exception as error:
            logger.warning("Error al descargar archivo en navegador: %s", error)
            self._notificar(f"No se pudo descargar el archivo en el navegador:\n{error}")

    async def subir_archivos_desde_pc(
        self,
        carpeta_destino: Path,
        extensiones: list[str],
        titulo: str = "Seleccionar archivo(s) desde esta PC",
        al_terminar: Callable[[list[Path]], None] | None = None,
    ) -> list[Path]:
        """Abre el selector del sistema/navegador y guarda archivos válidos en destino."""
        try:
            self.asegurar_file_picker()
            ext_limpias: list[str] = []
            for ext in extensiones:
                e = ext.lstrip(".").lower()
                if e not in ext_limpias:
                    ext_limpias.append(e)
            seleccionados = await self._host.file_picker.pick_files(
                dialog_title=titulo,
                file_type=ft.FilePickerFileType.ANY,
                allowed_extensions=None,
                allow_multiple=True,
                with_data=True,
                cancel_upload_on_window_blur=False,
            )
        except Exception as error:
            logger.warning("Error al abrir selector de archivos: %s", error)
            self._notificar(f"Error al abrir el selector de archivos:\n{error}")
            return []

        if not seleccionados:
            return []

        carpeta_destino.mkdir(parents=True, exist_ok=True)
        guardados: list[Path] = []
        rechazados: list[str] = []
        max_subida_bytes = 25 * 1024 * 1024  # 25 MB
        try:
            for item in seleccionados:
                nombre_limpio = Path(item.name).name
                if ext_limpias:
                    ext_item = Path(nombre_limpio).suffix.lstrip(".").lower()
                    if ext_item not in ext_limpias:
                        rechazados.append(nombre_limpio)
                        continue
                peso_bytes = (
                    len(item.bytes)
                    if (item.bytes and len(item.bytes) > 0)
                    else (Path(item.path).stat().st_size if (item.path and Path(item.path).exists()) else 0)
                )
                if peso_bytes > max_subida_bytes:
                    self._notificar(
                        f"El archivo '{nombre_limpio}' ({peso_bytes // (1024 * 1024)} MB) supera el límite máximo de 25 MB."
                    )
                    continue

                destino = carpeta_destino / nombre_limpio
                _cnt = 1
                while destino.exists():
                    try:
                        with open(destino, "ab"):
                            pass
                        break
                    except OSError:
                        destino = carpeta_destino / f"{Path(nombre_limpio).stem}_{_cnt}{Path(nombre_limpio).suffix}"
                        _cnt += 1
                if item.bytes and len(item.bytes) > 0:
                    destino.write_bytes(item.bytes)
                    guardados.append(destino)
                elif item.path:
                    origen = Path(item.path)
                    if origen.exists():
                        if origen.resolve() != destino.resolve():
                            shutil.copy2(origen, destino)
                        guardados.append(destino)
                elif item.bytes is not None:
                    destino.write_bytes(item.bytes)
                    guardados.append(destino)
        except Exception as error:
            self._notificar(f"Error al guardar el archivo subido:\n{error}")
            return []

        if rechazados and not guardados:
            formatos_str = ", ".join(f".{x}" for x in ext_limpias)
            self._notificar(
                f"El archivo seleccionado ({', '.join(rechazados)}) no tiene un formato permitido ({formatos_str})."
            )
            return []

        if guardados:
            if al_terminar is not None:
                al_terminar(guardados)
            self._notificar_guardado()
        return guardados
