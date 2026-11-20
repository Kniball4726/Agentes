"""Servicio independiente para transferencia de archivos (subida/descarga vía FilePicker)."""

from __future__ import annotations

import logging
import shutil
import weakref
from pathlib import Path
from typing import Any, Callable

import flet as ft

from ...core.security_utils import resolver_ruta_confinada, sanitizar_componente_archivo

logger = logging.getLogger(__name__)

_MAGIC_BYTES_EXT: dict[str, tuple[bytes, ...]] = {
    "pdf": (b"%PDF-",),
    "xlsx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    "docx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    "zip": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    "xls": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", b"PK\x03\x04"),
}


def _validar_magic_bytes(ext: str, cabecera: bytes) -> bool:
    """Verifica firmas binarias (magic bytes) para los formatos documentales soportados."""
    firmas = _MAGIC_BYTES_EXT.get(ext.lstrip(".").lower())
    if not firmas:
        return True
    if not cabecera:
        return False
    return any(cabecera.startswith(f) for f in firmas)


def _reservar_destino_exclusivo(carpeta_destino: Path, stem: str, suffix: str) -> Path:
    """Reserva atómicamente una ruta sin sobrescribir archivos previos usando modo exclusivo 'xb'."""
    candidato = resolver_ruta_confinada(carpeta_destino, f"{stem}{suffix}")
    contador = 1
    while True:
        try:
            with open(candidato, "xb"):
                pass
            return candidato
        except FileExistsError:
            candidato = resolver_ruta_confinada(carpeta_destino, f"{stem}_{contador}{suffix}")
            contador += 1


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
                nombre_orig = Path(str(item.name or "")).name
                suffix_orig = Path(nombre_orig).suffix
                ext_item = suffix_orig.lstrip(".").lower()
                stem_limpio = sanitizar_componente_archivo(Path(nombre_orig).stem, fallback="archivo")
                suffix_limpio = (
                    f".{sanitizar_componente_archivo(suffix_orig.lstrip('.'), fallback=ext_item)}"
                    if ext_item
                    else ""
                )
                nombre_limpio = f"{stem_limpio}{suffix_limpio}"
                if ext_limpias and ext_item not in ext_limpias:
                    rechazados.append(nombre_orig or nombre_limpio)
                    continue

                tiene_bytes = item.bytes is not None and len(item.bytes) > 0
                origen_path = Path(item.path) if item.path else None
                if tiene_bytes:
                    peso_bytes = len(item.bytes)
                    cabecera = bytes(item.bytes[:16])
                elif origen_path and origen_path.exists():
                    peso_bytes = origen_path.stat().st_size
                    with open(origen_path, "rb") as fh_head:
                        cabecera = fh_head.read(16)
                else:
                    peso_bytes = 0
                    cabecera = b""

                if peso_bytes > max_subida_bytes:
                    self._notificar(
                        f"El archivo '{nombre_limpio}' ({peso_bytes // (1024 * 1024)} MB) supera el límite máximo de 25 MB."
                    )
                    continue

                if ext_item in _MAGIC_BYTES_EXT and not _validar_magic_bytes(ext_item, cabecera):
                    rechazados.append(nombre_orig or nombre_limpio)
                    continue

                if tiene_bytes:
                    destino = _reservar_destino_exclusivo(carpeta_destino, stem_limpio, suffix_limpio)
                    destino.write_bytes(item.bytes)
                    guardados.append(destino)
                elif origen_path and origen_path.exists():
                    destino_directo = resolver_ruta_confinada(carpeta_destino, nombre_limpio)
                    if origen_path.resolve() == destino_directo.resolve():
                        guardados.append(destino_directo)
                    else:
                        destino = _reservar_destino_exclusivo(carpeta_destino, stem_limpio, suffix_limpio)
                        shutil.copy2(origen_path, destino)
                        guardados.append(destino)
                elif item.bytes is not None:
                    destino = _reservar_destino_exclusivo(carpeta_destino, stem_limpio, suffix_limpio)
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
