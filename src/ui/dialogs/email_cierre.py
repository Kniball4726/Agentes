"""Plantillas y despacho automático/interactivo de correos para Cierres de Jornada."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ...integrations.email_sender import despachar_correo
from ..app_config import guardar_correo_cierre


def _construir_resumen_cierre_email(
    cierre_id: int,
    resumen_pedidos: str,
    usuario: str,
    fecha_str: str | None = None,
) -> tuple[str, list[str]]:
    """Genera asunto y cabecera compartida del correo de Cierre de Jornada."""
    marca_fecha = fecha_str or datetime.now().strftime("%d/%m/%Y %H:%M")
    asunto = f"Cierre de Jornada #{cierre_id} - {marca_fecha} ({resumen_pedidos})"
    lineas = [
        "Estimados,",
        "",
        f"Se ha completado el Cierre de Jornada #{cierre_id} en el sistema de depósito.",
        f"• Fecha y Hora: {marca_fecha}",
        f"• Responsable: {usuario}",
        f"• Resumen consolidado: {resumen_pedidos}",
        "",
    ]
    return asunto, lineas


def enviar_correo_cierre(
    interfaz: Any,
    destinatarios: str,
    cierre_id: int,
    archivo_pdf: Path | None,
    archivo_excel: Path | None,
    resumen_pedidos: str,
    usuario: str,
    archivo_hoja_ruta: Path | None = None,
    alerta_stock: str = "",
) -> None:
    """Envía automáticamente el informe y hoja de ruta tras registrar un cierre de jornada."""
    dest_limpio = destinatarios.strip()
    if not dest_limpio:
        return
    guardar_correo_cierre(dest_limpio)
    asunto_txt, lineas_cuerpo = _construir_resumen_cierre_email(cierre_id, resumen_pedidos, usuario)
    lineas_cuerpo.append("Archivos oficiales adjuntos generados:")

    adjuntos_validos: list[Path] = []
    for arch, desc in (
        (archivo_pdf, "PDF Cierre de Descuentos"),
        (archivo_excel, "Excel Descuentos"),
        (archivo_hoja_ruta, "Manifiesto / Hoja de Ruta de Despacho"),
    ):
        if arch and arch.exists():
            lineas_cuerpo.append(f"• {desc}: {arch.name}")
            adjuntos_validos.append(arch)

    if alerta_stock:
        lineas_cuerpo.append("\n⚠️ ALERTAS DE INVENTARIO POST-CIERRE:")
        lineas_cuerpo.append(alerta_stock)
    lineas_cuerpo.append("\nLos archivos se encuentran guardados y respaldados en el servidor.")

    dest_lista = [d.strip() for d in dest_limpio.replace(";", ",").split(",") if d.strip()]
    ok, msg = despachar_correo(
        destinatarios=dest_lista,
        asunto=asunto_txt,
        cuerpo="\n".join(lineas_cuerpo),
        adjuntos=adjuntos_validos,
    )
    interfaz.notificar(f"✅ {msg}" if ok else f"⚠️ {msg}")


def mostrar_dialogo_compartir_cierre(
    interfaz: Any,
    cierre_id: int,
    archivo_pdf: Path | None,
    archivo_excel: Path | None,
    resumen_pedidos: str,
    usuario: str,
    archivo_hoja_ruta: Path | None = None,
    *,
    abrir_composer_fn: Callable[..., None] | None = None,
) -> None:
    """Prepara el diálogo de correo con los archivos del cierre de jornada precargados."""
    asunto, lineas_cuerpo = _construir_resumen_cierre_email(cierre_id, resumen_pedidos, usuario)
    lineas_cuerpo.append("Archivos adjuntos para control y archivo contable.")
    archivos = [p for p in (archivo_pdf, archivo_excel, archivo_hoja_ruta) if p and p.exists()]

    composer = abrir_composer_fn
    if composer is None:
        from .dlg_email import mostrar_dialogo_enviar_correo

        composer = mostrar_dialogo_enviar_correo

    composer(
        interfaz,
        archivos_iniciales=archivos,
        asunto_inicial=asunto,
        cuerpo_inicial="\n".join(lineas_cuerpo),
        titulo_dialogo=f"Enviar Cierre #{cierre_id} por Correo",
    )
