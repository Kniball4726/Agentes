"""Mixin para transferencia de archivos (subida/descarga vía FilePicker Flet)."""

from __future__ import annotations

import logging
import shutil
import weakref
from pathlib import Path
from typing import Any, Callable

import flet as ft

logger = logging.getLogger(__name__)


class FileTransferMixin:
    """Gestiona el servicio FilePicker y las operaciones de carga y descarga web/desktop."""

    page: ft.Page
    file_picker: ft.FilePicker

    def _asegurar_file_picker(self, forzar_recrear: bool = False) -> None:
        """Asegura que FilePicker esté registrado exclusivamente como servicio (Flet 1.0) sin contaminar el overlay visual."""
        reg = getattr(self.page, "_services", None)

        if forzar_recrear or not hasattr(self, "file_picker") or self.file_picker is None:
            viejo_fp = getattr(self, "file_picker", None)
            if viejo_fp is not None:
                if hasattr(self.page, "overlay") and self.page.overlay is not None:
                    try:
                        self.page.overlay = [c for c in self.page.overlay if c is not viejo_fp]
                    except Exception:
                        pass
                if hasattr(self.page, "services") and self.page.services is not None:
                    try:
                        self.page.services = [s for s in self.page.services if s is not viejo_fp]
                    except Exception:
                        pass
                if reg is not None and hasattr(reg, "_services"):
                    try:
                        reg._services = [s for s in reg._services if s is not viejo_fp]
                    except Exception:
                        pass
            self.file_picker = ft.FilePicker()

        # En Flet 1.0 FilePicker es un Servicio no visual. Si está en overlay, Flutter intenta
        # renderizarlo como Widget y genera el panel rojo de error 'Unknown control: FilePicker'.
        if hasattr(self.page, "overlay") and self.page.overlay is not None:
            while self.file_picker in self.page.overlay:
                self.page.overlay.remove(self.file_picker)

        if hasattr(self.page, "services") and self.page.services is not None:
            if not any(s is self.file_picker for s in self.page.services):
                self.page.services.append(self.file_picker)

        if type(reg).__name__ == "ServiceRegistry":
            if getattr(reg, "parent", None) is None:
                try:
                    reg._parent = weakref.ref(self.page)
                except Exception:
                    pass
            if hasattr(reg, "_services") and not any(s is self.file_picker for s in reg._services):
                try:
                    reg.register_service(self.file_picker)
                except Exception:
                    pass

        try:
            self.file_picker._parent = weakref.ref(self.page)
        except Exception:
            pass

    async def _descargar_archivo_navegador(self, ruta: Path) -> None:
        """Envía el contenido de un archivo local al navegador mediante FilePicker.save_file."""
        try:
            self._asegurar_file_picker()
            contenido_bytes = ruta.read_bytes()
            await self.file_picker.save_file(
                dialog_title=f"Guardar {ruta.name}",
                file_name=ruta.name,
                src_bytes=contenido_bytes,
            )
        except Exception as error:
            logger.warning("Error al descargar archivo en navegador: %s", error)
            self.notificar(f"No se pudo descargar el archivo en el navegador:\n{error}")

    async def subir_archivos_desde_pc(
        self,
        carpeta_destino: Path,
        extensiones: list[str],
        titulo: str = "Seleccionar archivo(s) desde esta PC",
        al_terminar: Callable[[list[Path]], None] | None = None,
    ) -> list[Path]:
        """Abre el selector del sistema/navegador y guarda archivos válidos en destino."""
        try:
            self._asegurar_file_picker()
            ext_limpias: list[str] = []
            for ext in extensiones:
                e = ext.lstrip(".").lower()
                if e not in ext_limpias:
                    ext_limpias.append(e)
            # Usar FilePickerFileType.ANY y validar extensiones en Python para evitar
            # filtros inconsistentes entre navegador y sistema operativo.
            seleccionados = await self.file_picker.pick_files(
                dialog_title=titulo,
                file_type=ft.FilePickerFileType.ANY,
                allowed_extensions=None,
                allow_multiple=True,
                with_data=True,
                cancel_upload_on_window_blur=False,
            )
        except Exception as error:
            logger.warning("Error al abrir selector de archivos: %s", error)
            self.notificar(f"Error al abrir el selector de archivos:\n{error}")
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
                    self.notificar(
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
            self.notificar(f"Error al guardar el archivo subido:\n{error}")
            return []

        if rechazados and not guardados:
            formatos_str = ", ".join(f".{x}" for x in ext_limpias)
            self.notificar(
                f"El archivo seleccionado ({', '.join(rechazados)}) no tiene un formato permitido ({formatos_str})."
            )
            return []

        if guardados:
            if al_terminar is not None:
                al_terminar(guardados)
            self.actualizar_estado()
            self.sincronizar_sesiones()
        return guardados
