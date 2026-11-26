"""Búsqueda y apertura de comprobantes e informes PDF asociados a pedidos."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ...orders import Pedido
from ._shared import resolve_app_root


def _buscar_archivo_pedido(
    nombre_raw: str,
    rutas_directas: list[Path],
    carpetas_glob: list[Path],
    carpetas_rglob: list[Path],
) -> Path | None:
    """Busca un archivo por candidatos exactos, glob simple y rglob insensible a mayúsculas."""
    nombre = (nombre_raw or "").strip()
    if not nombre or nombre.lower() in ("sin archivo", "ninguno", "-", "none"):
        return None

    for candidato in rutas_directas:
        if candidato.exists() and candidato.is_file():
            return candidato

    nombre_lower = nombre.lower()
    for carpeta in carpetas_glob:
        if carpeta.exists():
            for f in carpeta.glob("*"):
                if f.is_file() and f.name.lower() == nombre_lower:
                    return f

    for carpeta in carpetas_rglob:
        if carpeta.exists():
            for f in carpeta.rglob("*"):
                if f.is_file() and f.name.lower() == nombre_lower:
                    return f

    return None


def buscar_archivo_comprobante(
    pedido: Pedido,
    interfaz: Any = None,
    *,
    app_root_fn: Callable[[], Path] | None = None,
) -> Path | None:
    """Busca en el servidor la ruta física del comprobante original cargado para un pedido."""
    nombre = (pedido.nombre_archivo or "").strip()
    if not nombre:
        return None
    root = resolve_app_root(interfaz, app_root_fn=app_root_fn)
    directas = [
        root / "data" / "pedidos_archivos" / nombre,
        root / "data" / "descontados" / nombre,
        root / "data" / "descontados" / "mayoristas" / nombre,
        root / "data" / "descontados" / "canjes" / nombre,
        root / "data" / "descontados" / "mercado_libre" / nombre,
        root / "data" / "pendientes" / nombre,
        root / "data" / "pendientes" / "mayoristas" / nombre,
        root / "data" / "pendientes" / "canjes" / nombre,
        root / "data" / "pendientes" / "mercado_libre" / nombre,
        root / "Descuentos" / nombre,
        root / "data" / "informes" / nombre,
    ]
    return _buscar_archivo_pedido(
        nombre,
        rutas_directas=directas,
        carpetas_glob=[root / "data" / "pedidos_archivos"],
        carpetas_rglob=[root / "data" / "descontados", root / "data" / "historico"],
    )


def buscar_archivo_descuento(
    pedido: Pedido,
    interfaz: Any = None,
    *,
    app_root_fn: Callable[[], Path] | None = None,
) -> Path | None:
    """Busca la ruta del informe de descuento asociado a un pedido."""
    nombre = (getattr(pedido, "archivo_descuento", "") or "").strip()
    if not nombre:
        return None
    root = resolve_app_root(interfaz, app_root_fn=app_root_fn)
    directas = [
        root / "Descuentos" / nombre,
        root / "data" / "informes" / nombre,
        root / "data" / "pedidos_archivos" / nombre,
    ]
    return _buscar_archivo_pedido(
        nombre,
        rutas_directas=directas,
        carpetas_glob=[root / "Descuentos"],
        carpetas_rglob=[root / "data" / "historico"],
    )


def abrir_comprobante_pedido(
    interfaz: Any,
    ped: Pedido,
    *,
    app_root_fn: Callable[[], Path] | None = None,
) -> None:
    """Abre el archivo original cargado para consulta o reimpresión."""
    ruta = buscar_archivo_comprobante(ped, interfaz=interfaz, app_root_fn=app_root_fn)
    if ruta is None or not ruta.exists():
        interfaz.notificar(
            f"El archivo cargado '{ped.nombre_archivo}' no se encuentra actualmente en el servidor.\n"
            "Es posible que haya sido archivado o movido a una copia de seguridad externa."
        )
        return
    interfaz.abrir_informe(ruta_especifica=ruta)


def abrir_descuento_pedido(
    interfaz: Any,
    ped: Pedido,
    *,
    app_root_fn: Callable[[], Path] | None = None,
) -> None:
    """Abre el informe de descuento asociado al pedido."""
    ruta = buscar_archivo_descuento(ped, interfaz=interfaz, app_root_fn=app_root_fn)
    if ruta is None or not ruta.exists():
        interfaz.notificar(
            f"El informe de descuento '{ped.archivo_descuento}' no se encuentra en el servidor."
        )
        return
    interfaz.abrir_informe(ruta_especifica=ruta)
