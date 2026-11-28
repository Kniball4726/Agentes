"""Utilidades modulares de seguridad de red: anti-SSRF, TLS estricto, HMAC y cabeceras MIME."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

_RE_CONTROL_MIME = re.compile(r"[\r\n\x00-\x1f\x7f]+")
_HOSTS_LOCALES_PROHIBIDOS = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "ip6-localhost",
        "ip6-loopback",
        "metadata.google.internal",
        "metadata",
    }
)


class SSRFBlockedError(ValueError):
    """Se lanza cuando una URL o destino de red apunta a un origen prohibido."""


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Impide redirecciones HTTP 3xx automáticas para prevenir evasión SSRF."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(
            req.full_url,
            code,
            f"Redirección HTTP {code} bloqueada por política anti-SSRF.",
            headers,
            fp,
        )


def crear_contexto_tls_estricto() -> ssl.SSLContext:
    """Devuelve un contexto TLS con verificación de certificados y hostname activada."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    if hasattr(ssl, "TLSVersion"):
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def sanitizar_cabecera_mime(valor: str) -> str:
    """Elimina CR/LF y caracteres de control para prevenir SMTP/MIME Header Injection."""
    return _RE_CONTROL_MIME.sub(" ", str(valor or "")).strip()


def es_ip_prohibida(ip_str: str, *, permitir_lan_privada: bool = False) -> bool:
    """Evalúa si una dirección IP corresponde a loopback, link-local/metadata o rangos prohibidos."""
    try:
        ip_obj = ipaddress.ip_address(str(ip_str).strip("[]"))
    except ValueError:
        return False

    if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped is not None:
        ip_obj = ip_obj.ipv4_mapped

    if (
        ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_unspecified
        or ip_obj.is_reserved
    ):
        return True

    return bool(not permitir_lan_privada and ip_obj.is_private)


def validar_url_externa_segura(
    url: str,
    *,
    resolver_dns: bool = False,
    permitir_lan_privada: bool = False,
) -> str:
    """Valida esquema http/https y bloquea destinos internos/metadata (anti-SSRF)."""
    limpia = str(url or "").strip()
    if not limpia or any(ord(c) < 32 for c in limpia):
        raise ValueError("URL vacía o con caracteres de control.")

    parsed = urllib.parse.urlparse(limpia)
    esquema = parsed.scheme.lower()
    if esquema not in ("http", "https") or not parsed.netloc:
        raise ValueError("La URL del webhook debe comenzar con http:// o https:// y contener un host válido.")
    if parsed.username or parsed.password:
        raise SSRFBlockedError("No se permiten credenciales embebidas en la URL.")

    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        raise ValueError("La URL no contiene un host válido.")

    if host in _HOSTS_LOCALES_PROHIBIDOS or host.endswith(".localhost") or host.endswith(".internal"):
        raise SSRFBlockedError(f"Host interno/local bloqueado por seguridad: '{host}'.")

    if es_ip_prohibida(host, permitir_lan_privada=permitir_lan_privada):
        raise SSRFBlockedError(f"Dirección IP restringida bloqueada por política anti-SSRF: '{host}'.")

    if resolver_dns:
        puerto = parsed.port or (443 if esquema == "https" else 80)
        try:
            infos = socket.getaddrinfo(host, puerto, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise SSRFBlockedError(f"No se pudo resolver el host '{host}': {exc}") from exc
        if not infos:
            raise SSRFBlockedError(f"El host '{host}' no devolvió direcciones IP válidas.")
        for info in infos:
            ip_resuelta = str(info[4][0])
            if es_ip_prohibida(ip_resuelta, permitir_lan_privada=permitir_lan_privada):
                raise SSRFBlockedError(
                    f"El host '{host}' resuelve a una IP bloqueada por política anti-SSRF ({ip_resuelta})."
                )

    return limpia


def firmar_payload_hmac(
    data_bytes: bytes,
    secreto: str,
    *,
    timestamp: str | None = None,
) -> dict[str, str]:
    """Genera cabeceras de firma HMAC-SHA256 sobre timestamp + payload JSON."""
    ts = str(timestamp if timestamp is not None else int(time.time()))
    secreto_limpio = str(secreto or "").strip()
    if not secreto_limpio:
        return {"X-StockAgent-Timestamp": ts}
    mensaje = ts.encode("utf-8") + b"." + data_bytes
    firma = hmac.new(secreto_limpio.encode("utf-8"), mensaje, hashlib.sha256).hexdigest()
    return {
        "X-StockAgent-Timestamp": ts,
        "X-StockAgent-Signature": f"sha256={firma}",
    }
