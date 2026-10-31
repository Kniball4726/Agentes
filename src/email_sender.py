"""Módulo de envío y gestión de correos electrónicos con soporte para adjuntos.
Permite el envío directo mediante SMTP (Gmail, Outlook, servidores corporativos)
y la integración nativa con clientes de correo de Windows (MAPI / Outlook / Thunderbird)
con archivos adjuntos físicos.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json
import mimetypes
import os
from pathlib import Path
import smtplib
import subprocess
import sys
import urllib.parse

from . import secretos
from .paths import application_root

RUTA_CONFIG_EMAIL = application_root() / "data" / "email_config.json"


def _ruta_config_email() -> Path:
    return application_root() / "data" / "email_config.json"


CONFIG_EMAIL_DEFECTO: dict = {
    "metodo": "auto",  # "auto", "smtp", "cliente"
    "smtp_servidor": "",
    "smtp_puerto": 587,
    "smtp_usar_tls": True,
    "smtp_usar_ssl": False,
    "smtp_usuario": "",
    "smtp_password": "",
    "remitente": "",
    "destinatarios_guardados": "",
    # Alertas automáticas (resumen diario de stock crítico y despachos)
    "alertas": {
        "activo": False,
        "hora": "08:00",
        "destinatarios": "",
        "ultimo_envio": "",
    },
}


def obtener_config_email() -> dict:
    """Obtiene la configuración de correo (la contraseña SMTP se devuelve descifrada).

    Prioridad de la contraseña: variable de entorno ``STOCKAGENT_SMTP_PASSWORD`` y luego
    el valor cifrado en ``data/email_config.json``.
    """
    ruta_cfg = _ruta_config_email()
    config = json.loads(json.dumps(CONFIG_EMAIL_DEFECTO))
    if ruta_cfg.exists():
        try:
            guardada = json.loads(ruta_cfg.read_text(encoding="utf-8"))
        except Exception:
            guardada = {}
        alertas = {**config["alertas"], **(guardada.get("alertas") or {})}
        config.update(guardada)
        config["alertas"] = alertas
    valor_guardado = config.get("smtp_password", "") or ""
    try:
        config["smtp_password"] = secretos.descifrar(valor_guardado)
    except secretos.SecretoError:
        config["smtp_password"] = ""
    clave_entorno = os.environ.get("STOCKAGENT_SMTP_PASSWORD", "")
    if clave_entorno:
        config["smtp_password"] = clave_entorno
    if os.environ.get("STOCKAGENT_SMTP_SERVER"):
        config["smtp_servidor"] = os.environ["STOCKAGENT_SMTP_SERVER"].strip()
    if os.environ.get("STOCKAGENT_SMTP_PORT"):
        try:
            config["smtp_puerto"] = int(os.environ["STOCKAGENT_SMTP_PORT"])
        except ValueError:
            pass
    if os.environ.get("STOCKAGENT_SMTP_USER"):
        config["smtp_usuario"] = os.environ["STOCKAGENT_SMTP_USER"].strip()
    if os.environ.get("STOCKAGENT_SMTP_SENDER"):
        config["remitente"] = os.environ["STOCKAGENT_SMTP_SENDER"].strip()
    # Migración automática: si estaba en texto plano, volver a guardarla cifrada.
    if valor_guardado and not secretos.esta_cifrado(valor_guardado):
        try:
            guardar_config_email(config)
        except Exception:
            pass
    return config


def guardar_config_email(config: dict) -> None:
    """Guarda la configuración de correo cifrando la contraseña SMTP."""
    ruta_cfg = _ruta_config_email()
    a_guardar = dict(config)
    a_guardar["smtp_password"] = secretos.cifrar(str(config.get("smtp_password") or ""))
    ruta_cfg.parent.mkdir(parents=True, exist_ok=True)
    ruta_cfg.write_text(
        json.dumps(a_guardar, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def probar_conexion_smtp(config: dict) -> tuple[bool, str]:
    """Prueba la conexión y autenticación con el servidor SMTP configurado."""
    servidor = (config.get("smtp_servidor") or "").strip()
    puerto = int(config.get("smtp_puerto") or 587)
    usuario = (config.get("smtp_usuario") or "").strip()
    password = (config.get("smtp_password") or "").strip()
    usar_tls = bool(config.get("smtp_usar_tls", True))
    usar_ssl = bool(config.get("smtp_usar_ssl", False))

    if not servidor:
        return False, "Falta especificar el servidor SMTP (ej: smtp.gmail.com)."

    try:
        if usar_ssl:
            server = smtplib.SMTP_SSL(servidor, puerto, timeout=12)
        else:
            server = smtplib.SMTP(servidor, puerto, timeout=12)
            if usar_tls:
                server.starttls()

        if usuario and password:
            server.login(usuario, password)

        server.quit()
        return True, "Conexión SMTP establecida con éxito."
    except Exception as err:
        return False, f"Error al conectar con el servidor SMTP:\n{err}"


def enviar_via_smtp(
    destinatarios: list[str],
    asunto: str,
    cuerpo: str,
    adjuntos: list[Path],
    config: dict | None = None,
) -> tuple[bool, str]:
    """Envía un correo con archivos adjuntos directamente a través de SMTP."""
    cfg = config or obtener_config_email()
    servidor = (cfg.get("smtp_servidor") or "").strip()
    puerto = int(cfg.get("smtp_puerto") or 587)
    usuario = (cfg.get("smtp_usuario") or "").strip()
    password = (cfg.get("smtp_password") or "").strip()
    remitente = (cfg.get("remitente") or "").strip() or usuario
    usar_tls = bool(cfg.get("smtp_usar_tls", True))
    usar_ssl = bool(cfg.get("smtp_usar_ssl", False))

    if not servidor or not usuario:
        return False, "No se han configurado los datos del servidor SMTP."

    dest_limpios = [d.strip() for d in destinatarios if d.strip()]
    if not dest_limpios:
        return False, "No se indicaron destinatarios válidos."

    msg = MIMEMultipart()
    msg["From"] = remitente
    msg["To"] = ", ".join(dest_limpios)
    msg["Subject"] = asunto

    msg.attach(MIMEText(cuerpo, "plain", "utf-8"))

    for ruta in adjuntos:
        if not ruta.exists():
            continue
        tipo_mime, _ = mimetypes.guess_type(str(ruta))
        if tipo_mime is None:
            tipo_mime = "application/octet-stream"
        categoria, subcategoria = tipo_mime.split("/", 1)

        parte = MIMEBase(categoria, subcategoria)
        parte.set_payload(ruta.read_bytes())
        encoders.encode_base64(parte)
        parte.add_header("Content-Disposition", f'attachment; filename="{ruta.name}"')
        msg.attach(parte)

    try:
        if usar_ssl:
            server = smtplib.SMTP_SSL(servidor, puerto, timeout=20)
        else:
            server = smtplib.SMTP(servidor, puerto, timeout=20)
            if usar_tls:
                server.starttls()

        if usuario and password:
            server.login(usuario, password)

        server.sendmail(remitente, dest_limpios, msg.as_string())
        server.quit()
        return True, "Correo enviado correctamente con todos sus archivos adjuntos vía SMTP."
    except Exception as err:
        return False, f"Fallo al enviar correo por SMTP:\n{err}"


# --- Integración Simple MAPI para Windows (Outlook, Thunderbird, etc.) ---

class _MapiFileDesc(ctypes.Structure):
    _fields_ = [
        ("ulReserved", wintypes.ULONG),
        ("flFlags", wintypes.ULONG),
        ("nPosition", wintypes.ULONG),
        ("lpszPathName", ctypes.c_char_p),
        ("lpszFileName", ctypes.c_char_p),
        ("lpFileType", ctypes.c_void_p),
    ]


class _MapiRecipDesc(ctypes.Structure):
    _fields_ = [
        ("ulReserved", wintypes.ULONG),
        ("ulRecipClass", wintypes.ULONG),
        ("lpszName", ctypes.c_char_p),
        ("lpszAddress", ctypes.c_char_p),
        ("ulEIDSize", wintypes.ULONG),
        ("lpEntryID", ctypes.c_void_p),
    ]


class _MapiMessage(ctypes.Structure):
    _fields_ = [
        ("ulReserved", wintypes.ULONG),
        ("lpszSubject", ctypes.c_char_p),
        ("lpszNoteText", ctypes.c_char_p),
        ("lpszMessageType", ctypes.c_char_p),
        ("lpszDateReceived", ctypes.c_char_p),
        ("lpszConversationID", ctypes.c_char_p),
        ("flFlags", wintypes.ULONG),
        ("lpOriginator", ctypes.c_void_p),
        ("nRecipCount", wintypes.ULONG),
        ("lpRecips", ctypes.POINTER(_MapiRecipDesc)),
        ("nFileCount", wintypes.ULONG),
        ("lpFiles", ctypes.POINTER(_MapiFileDesc)),
    ]


def abrir_en_cliente_mapi(
    destinatarios: list[str],
    asunto: str,
    cuerpo: str,
    adjuntos: list[Path],
) -> tuple[bool, str]:
    """Abre la ventana de redacción del cliente de correo por defecto de Windows con los adjuntos cargados."""
    if sys.platform != "win32":
        return False, "Simple MAPI solo está disponible en Windows."

    try:
        mapi32 = ctypes.windll.mapi32
        if not hasattr(mapi32, "MAPISendMail"):
            return False, "La librería MAPI de Windows no tiene MAPISendMail."

        mapisendmail = mapi32.MAPISendMail
        mapisendmail.restype = wintypes.ULONG
        mapisendmail.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.POINTER(_MapiMessage),
            wintypes.ULONG,
            wintypes.ULONG,
        ]

        # Preparar destinatarios
        dest_limpios = [d.strip() for d in destinatarios if d.strip()]
        recips_arr = None
        if dest_limpios:
            recips_arr = (_MapiRecipDesc * len(dest_limpios))()
            for idx, d in enumerate(dest_limpios):
                recips_arr[idx].ulReserved = 0
                recips_arr[idx].ulRecipClass = 1  # MAPI_TO
                recips_arr[idx].lpszName = d.encode("mbcs", errors="replace")
                recips_arr[idx].lpszAddress = f"SMTP:{d}".encode("mbcs", errors="replace")
                recips_arr[idx].ulEIDSize = 0
                recips_arr[idx].lpEntryID = None

        # Preparar adjuntos
        adjuntos_existentes = [p.resolve() for p in adjuntos if p.exists()]
        files_arr = None
        # Mantener referencias vivas para evitar garbage collection de ctypes
        byte_refs: list[bytes] = []

        if adjuntos_existentes:
            files_arr = (_MapiFileDesc * len(adjuntos_existentes))()
            for idx, p in enumerate(adjuntos_existentes):
                path_bytes = str(p).encode("mbcs", errors="replace")
                name_bytes = p.name.encode("mbcs", errors="replace")
                byte_refs.extend([path_bytes, name_bytes])

                files_arr[idx].ulReserved = 0
                files_arr[idx].flFlags = 0
                files_arr[idx].nPosition = 0xFFFFFFFF
                files_arr[idx].lpszPathName = path_bytes
                files_arr[idx].lpszFileName = name_bytes
                files_arr[idx].lpFileType = None

        asunto_bytes = asunto.encode("mbcs", errors="replace")
        cuerpo_bytes = cuerpo.encode("mbcs", errors="replace")

        msg = _MapiMessage()
        msg.ulReserved = 0
        msg.lpszSubject = asunto_bytes
        msg.lpszNoteText = cuerpo_bytes
        msg.lpszMessageType = None
        msg.lpszDateReceived = None
        msg.lpszConversationID = None
        msg.flFlags = 0
        msg.lpOriginator = None
        msg.nRecipCount = len(dest_limpios) if dest_limpios else 0
        msg.lpRecips = recips_arr if dest_limpios else None
        msg.nFileCount = len(adjuntos_existentes)
        msg.lpFiles = files_arr if adjuntos_existentes else None

        MAPI_LOGON_UI = 0x00000001
        MAPI_DIALOG = 0x00000008

        codigo = mapisendmail(None, 0, ctypes.byref(msg), MAPI_LOGON_UI | MAPI_DIALOG, 0)

        # 0: Éxito (enviado o ventana de redacción abierta)
        # 1: Usuario canceló o cerró la ventana de redacción
        if codigo in (0, 1):
            return True, "Cliente de correo abierto con los archivos adjuntos preparados."
        return False, f"El cliente de correo devolvió código MAPI: {codigo}"
    except Exception as err:
        return False, f"Error al invocar MAPI de Windows: {err}"


def abrir_fallback_correo(
    destinatarios: list[str],
    asunto: str,
    cuerpo: str,
    adjuntos: list[Path],
) -> None:
    """Abre el explorador de Windows con el archivo seleccionado y la URL mailto:."""
    dest_str = urllib.parse.quote(",".join([d.strip() for d in destinatarios if d.strip()]))
    asunto_enc = urllib.parse.quote(asunto)
    cuerpo_enc = urllib.parse.quote(cuerpo)

    # Abrir explorer seleccionando el primer archivo adjunto
    for p in adjuntos:
        if p.exists():
            try:
                subprocess.Popen(["explorer.exe", f"/select,{p.resolve()}"])
            except Exception:
                pass
            break

    try:
        os.startfile(f"mailto:{dest_str}?subject={asunto_enc}&body={cuerpo_enc}")  # type: ignore[attr-defined]
    except Exception:
        pass


def despachar_correo(
    destinatarios: list[str],
    asunto: str,
    cuerpo: str,
    adjuntos: list[Path],
    metodo_preferido: str = "auto",
) -> tuple[bool, str]:
    """Envía o prepara el correo utilizando el mejor método disponible (SMTP, MAPI o Fallback)."""
    cfg = obtener_config_email()
    metodo = metodo_preferido if metodo_preferido != "auto" else cfg.get("metodo", "auto")

    # Si se configuró SMTP explícito o auto con credenciales cargadas
    tiene_smtp = bool(cfg.get("smtp_servidor") and cfg.get("smtp_usuario"))

    if metodo == "smtp" or (metodo == "auto" and tiene_smtp):
        ok, msg = enviar_via_smtp(destinatarios, asunto, cuerpo, adjuntos, cfg)
        if ok:
            return True, msg
        # Si falló SMTP en modo auto, intentar MAPI
        if metodo != "auto":
            return False, msg

    # Intentar MAPI (Outlook, Thunderbird, Mail de Windows)
    ok_mapi, msg_mapi = abrir_en_cliente_mapi(destinatarios, asunto, cuerpo, adjuntos)
    if ok_mapi:
        return True, msg_mapi

    # Fallback si no hay MAPI ni SMTP
    abrir_fallback_correo(destinatarios, asunto, cuerpo, adjuntos)
    return True, (
        "Se abrió la aplicación de correo y la carpeta con los archivos seleccionados. "
        "Si tu cliente web no los adjuntó automáticamente, arrástralos directamente a la ventana de redacción."
    )
