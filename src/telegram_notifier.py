"""Módulo de Alertas Proactivas por Telegram Bot para StockAgent.

Permite enviar notificaciones inmediatas a un canal o chat privado de Telegram ante:
- Quiebres críticos de inventario (stock <= stock mínimo).
- Bloqueos de seguridad por fuerza bruta (5 intentos fallidos).
- Resumen formal de Cierre de Jornada y despacho.
"""

from datetime import datetime
import json
from pathlib import Path
import threading
from typing import Any
import urllib.parse
import urllib.request

from .paths import application_root

CONFIG_PATH_DEFAULT = "data/config_telegram.json"


def _obtener_ruta_config(root_path: Path | None = None) -> Path:
    root = root_path or application_root()
    return root / CONFIG_PATH_DEFAULT


def cargar_config_telegram(root_path: Path | None = None) -> dict[str, Any]:
    """Carga la configuración del bot de Telegram desde disco."""
    ruta = _obtener_ruta_config(root_path)
    if ruta.exists():
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "bot_token": str(data.get("bot_token", "")).strip(),
                    "chat_id": str(data.get("chat_id", "")).strip(),
                    "activo": bool(data.get("activo", False)),
                    "notificar_quiebres": bool(data.get("notificar_quiebres", True)),
                    "notificar_seguridad": bool(data.get("notificar_seguridad", True)),
                    "notificar_cierre": bool(data.get("notificar_cierre", True)),
                }
        except Exception:
            pass

    return {
        "bot_token": "",
        "chat_id": "",
        "activo": False,
        "notificar_quiebres": True,
        "notificar_seguridad": True,
        "notificar_cierre": True,
    }


def guardar_config_telegram(config: dict[str, Any], root_path: Path | None = None) -> None:
    """Guarda la configuración del bot de Telegram en disco."""
    ruta = _obtener_ruta_config(root_path)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def enviar_mensaje_telegram(
    mensaje: str,
    config: dict[str, Any] | None = None,
    sync: bool = False,
    root_path: Path | None = None,
) -> tuple[bool, str]:
    """Envía un mensaje de texto formateado en HTML al chat o canal de Telegram configurado."""
    cfg = config or cargar_config_telegram(root_path)
    token = cfg.get("bot_token", "").strip()
    chat_id = cfg.get("chat_id", "").strip()

    if not token or not chat_id:
        return False, "Faltan credenciales: se requiere Bot Token y Chat ID de Telegram."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": mensaje,
        "parse_mode": "HTML",
    }).encode("utf-8")

    def _ejecutar_envio() -> tuple[bool, str]:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=6.0) as resp:
                if resp.status == 200:
                    return True, "Mensaje enviado exitosamente a Telegram."
                return False, f"Respuesta inesperada de Telegram (Código: {resp.status})."
        except urllib.error.HTTPError as http_err:
            try:
                err_body = http_err.read().decode("utf-8", errors="ignore")
            except Exception:
                err_body = str(http_err)
            return False, f"Error HTTP Telegram ({http_err.code}): {err_body}"
        except Exception as exc:
            return False, f"Error de conexión con Telegram: {exc}"

    if sync:
        return _ejecutar_envio()

    # Envío asíncrono en segundo plano para no congelar la interfaz
    threading.Thread(target=_ejecutar_envio, daemon=True).start()
    return True, "Envío programado en segundo plano."


def notificar_quiebre_stock_telegram(
    codigo: str,
    nombre: str,
    stock_actual: int,
    stock_minimo: int,
    root_path: Path | None = None,
) -> bool:
    """Envía una alerta proactiva cuando un producto entra en quiebre o stock crítico."""
    cfg = cargar_config_telegram(root_path)
    if not cfg.get("activo") or not cfg.get("notificar_quiebres"):
        return False

    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    estado = "🔴 AGOTADO (0 unidades)" if stock_actual <= 0 else f"🟡 CRÍTICO ({stock_actual} unidades)"
    msg = (
        f"🚨 <b>ALERTA DE QUIEBRE DE STOCK - STOCKAGENT</b>\n\n"
        f"• <b>Producto:</b> {nombre}\n"
        f"• <b>Código/SKU:</b> <code>{codigo}</code>\n"
        f"• <b>Estado:</b> {estado}\n"
        f"• <b>Stock Mínimo Definido:</b> {stock_minimo} un.\n"
        f"• <b>Fecha y Hora:</b> {ahora}\n\n"
        f"<i>💡 Sugerencia: Generar pedido de reposición para fábrica.</i>"
    )
    enviar_mensaje_telegram(msg, config=cfg, sync=False, root_path=root_path)
    return True


def notificar_seguridad_bloqueo_telegram(
    username: str,
    ip_origen: str = "Local / LAN",
    retry_after_minutos: int = 15,
    root_path: Path | None = None,
) -> bool:
    """Envía una alerta de seguridad cuando una cuenta es bloqueada por intentos fallidos."""
    cfg = cargar_config_telegram(root_path)
    if not cfg.get("activo") or not cfg.get("notificar_seguridad"):
        return False

    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    msg = (
        f"🛡️ <b>ALERTA DE SEGURIDAD - CUENTA BLOQUEADA</b>\n\n"
        f"• <b>Usuario Afectado:</b> <code>{username}</code>\n"
        f"• <b>Motivo:</b> 5 intentos fallidos consecutivos de contraseña.\n"
        f"• <b>Duración del Bloqueo:</b> {retry_after_minutos} minutos.\n"
        f"• <b>Origen:</b> {ip_origen}\n"
        f"• <b>Fecha y Hora:</b> {ahora}\n\n"
        f"<i>⚠️ Un Administrador o Master puede desbloquear la cuenta de inmediato desde 'Gestión de Usuarios'.</i>"
    )
    enviar_mensaje_telegram(msg, config=cfg, sync=False, root_path=root_path)
    return True


def notificar_cierre_jornada_telegram(
    responsable: str,
    pedidos: int,
    bultos: int,
    articulos: int,
    root_path: Path | None = None,
) -> bool:
    """Envía el resumen consolidado al completarse el Cierre de Jornada."""
    cfg = cargar_config_telegram(root_path)
    if not cfg.get("activo") or not cfg.get("notificar_cierre"):
        return False

    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    msg = (
        f"📦 <b>RESUMEN DE CIERRE DE JORNADA - STOCKAGENT</b>\n\n"
        f"• <b>Responsable:</b> {responsable}\n"
        f"• <b>Pedidos Consolidados:</b> {pedidos}\n"
        f"• <b>Total Bultos Despachados:</b> {bultos}\n"
        f"• <b>Artículos Totales Descontados:</b> {articulos} unidades\n"
        f"• <b>Fecha y Hora:</b> {ahora}\n\n"
        f"<i>📄 Hoja de Ruta de Despacho y reportes archivados correctamente.</i>"
    )
    enviar_mensaje_telegram(msg, config=cfg, sync=False, root_path=root_path)
    return True


def notificar_anomalia_demanda_telegram(
    codigo: str,
    nombre: str,
    tipo_anomalia: str,
    consumo_actual: int,
    promedio_historico: float,
    mensaje: str,
    root_path: Path | None = None,
) -> bool:
    """Envía una alerta proactiva por Telegram ante un pico de consumo o desvío anómalo."""
    cfg = cargar_config_telegram(root_path)
    if not cfg.get("activo") or not cfg.get("notificar_quiebres", True):
        return False

    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    lineas = [
        "🚨 <b>ALERTA ANALÍTICA · DESVÍO DE DEMANDA</b>\n",
        f"• <b>Producto:</b> [{codigo}] {nombre}",
        f"• <b>Tipo de Alerta:</b> {tipo_anomalia}",
        f"• <b>Consumo Registrado:</b> {consumo_actual} un. (Habitual: {promedio_historico:.1f} un.)",
        f"• <b>Diagnóstico:</b> {mensaje}",
        f"• <b>Fecha y Hora:</b> {ahora}\n",
        "<i>💡 Verifica si se trata de un pedido especial o un error de tipeo en las cantidades.</i>",
    ]
    texto = "\n".join(lineas)
    enviar_mensaje_telegram(texto, config=cfg, sync=False, root_path=root_path)
    return True
