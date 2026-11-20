"""Generación y gestión modular de PKI local (CA restringida + certificado hoja ≤ 365 días)."""

from __future__ import annotations

import datetime
import ipaddress
import os
import re
import socket
import subprocess
import sys
from pathlib import Path

from .paths import application_root

_LEAF_VALIDITY_DAYS = 365
_LEAF_RENEWAL_MARGIN_DAYS = 30
_CA_VALIDITY_DAYS = 3650
_REDES_PERMITIDAS_CA = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),
)
_DNS_LABEL_RE = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$")


def _es_dns_rfc_valido(nombre: str) -> bool:
    """Verifica que un nombre DNS cumpla estrictamente RFC 1035 / RFC 5280 (sin guiones al inicio o final)."""
    limpio = (nombre or "").strip().lstrip(".")
    if not limpio or len(limpio) > 253:
        return False
    etiquetas = limpio.split(".")
    return all(bool(_DNS_LABEL_RE.match(et)) for et in etiquetas)


def _normalizar_hostname_dns(raw_hostname: str) -> str:
    """Sanitiza el hostname del equipo para evitar certificados X.509 inválidos (ej. 'PC-' en Windows)."""
    candidato = (raw_hostname or "").strip().lower()
    etiquetas_limpias: list[str] = []
    for parte in candidato.split("."):
        limpia = re.sub(r"[^a-z0-9-]", "", parte).strip("-")
        if limpia:
            etiquetas_limpias.append(limpia[:63])
    resultado = ".".join(etiquetas_limpias)
    if not resultado or not _es_dns_rfc_valido(resultado):
        return "stockagent.local"
    return resultado


def _obtener_ips_locales() -> list[str]:
    ips = {"127.0.0.1"}
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ips.add(s.getsockname()[0])
    except Exception:
        pass
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip:
                ips.add(ip)
    except Exception:
        pass
    filtradas: list[str] = []
    for ip_str in sorted(ips):
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if any(ip_obj in red for red in _REDES_PERMITIDAS_CA):
            filtradas.append(ip_str)
    return filtradas or ["127.0.0.1"]


def _proteger_clave_privada(ruta_key: Path) -> None:
    """Aplica permisos restrictivos sobre una clave privada (.key) en POSIX y NTFS Windows."""
    try:
        os.chmod(ruta_key, 0o600)
    except OSError:
        pass
    if sys.platform == "win32":
        usuario = os.environ.get("USERNAME", "").strip()
        if usuario and all(c.isalnum() or c in "._- $" for c in usuario):
            try:
                subprocess.run(
                    [
                        "icacls",
                        str(ruta_key),
                        "/inheritance:r",
                        "/grant:r",
                        f"{usuario}:(R,W)",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    check=False,
                )
            except Exception:
                pass


def _ca_instalada_en_root_windows() -> bool:
    """Comprueba si 'StockAgent Local CA' ya figura en el almacén ROOT de Windows."""
    if sys.platform != "win32":
        return True
    for args in (
        ["certutil", "-store", "ROOT", "StockAgent Local CA"],
        ["certutil", "-user", "-store", "ROOT", "StockAgent Local CA"],
    ):
        try:
            res = subprocess.run(
                args,
                capture_output=True,
                text=True,
                errors="ignore",
                timeout=3,
                check=False,
            )
            if res.returncode == 0 and "StockAgent Local CA" in (res.stdout or ""):
                return True
        except Exception:
            pass
    return False


def asegurar_ca_confiable_windows(ca_cert_path: Path | None = None) -> bool:
    """Verifica si la CA local está instalada en Windows ROOT y solicita elevación UAC si falta."""
    if sys.platform != "win32" or "PYTEST_CURRENT_TEST" in os.environ:
        return True
    ruta_ca = ca_cert_path or (application_root() / "data" / "certs" / "stockagent_ca.crt")
    if not ruta_ca.exists():
        return False
    if _ca_instalada_en_root_windows():
        return True
    try:
        import ctypes

        params = f'-addstore -f "ROOT" "{ruta_ca.resolve()}"'
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "certutil.exe", params, None, 0
        )
        if int(ret) > 32:
            for _ in range(16):
                import time

                time.sleep(0.5)
                if _ca_instalada_en_root_windows():
                    return True
    except Exception:
        pass
    return _ca_instalada_en_root_windows()


def _certificado_tiene_dns_invalido(cert) -> bool:
    """Detecta si un certificado contiene algún DNSName con etiquetas no válidas (ej. 'PC-')."""
    from cryptography import x509

    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        for gn in san:
            if isinstance(gn, x509.DNSName) and not _es_dns_rfc_valido(gn.value):
                return True
    except x509.ExtensionNotFound:
        pass
    try:
        nc = cert.extensions.get_extension_for_class(x509.NameConstraints).value
        for gn in nc.permitted_subtrees or []:
            if isinstance(gn, x509.DNSName) and not _es_dns_rfc_valido(gn.value):
                return True
    except x509.ExtensionNotFound:
        pass
    return False


def _certificado_requiere_renovacion(ruta_cert: Path) -> bool:
    """Devuelve True si el certificado hoja no existe, expiró, está próximo a vencer, es CA legado o tiene DNS inválido."""
    if not ruta_cert.exists():
        return True
    try:
        from cryptography import x509

        cert = x509.load_pem_x509_certificate(ruta_cert.read_bytes())
        ahora = datetime.datetime.now(datetime.timezone.utc)
        exp = getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after.replace(
            tzinfo=datetime.timezone.utc
        )
        if exp <= ahora + datetime.timedelta(days=_LEAF_RENEWAL_MARGIN_DAYS):
            return True
        try:
            bc = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
            if bc.ca:
                return True
        except x509.ExtensionNotFound:
            pass
        if _certificado_tiene_dns_invalido(cert):
            return True
        return False
    except Exception:
        return True


def _cargar_o_crear_ca_local(certs_dir: Path, hostname_limpio: str):
    """Carga o genera la CA local restringida mediante NameConstraints a entornos privados/LAN."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    ca_cert_path = certs_dir / "stockagent_ca.crt"
    ca_key_path = certs_dir / "stockagent_ca.key"

    if ca_cert_path.exists() and ca_key_path.exists():
        try:
            ca_cert = x509.load_pem_x509_certificate(ca_cert_path.read_bytes())
            if not _certificado_tiene_dns_invalido(ca_cert):
                ca_key = serialization.load_pem_private_key(ca_key_path.read_bytes(), password=None)
                return ca_cert, ca_key, ca_cert_path
        except Exception:
            pass

    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "AR"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Elola Depósito - StockAgent"),
            x509.NameAttribute(NameOID.COMMON_NAME, "StockAgent Local CA"),
        ]
    )

    permitted: list[x509.GeneralName] = [
        x509.DNSName("localhost"),
        x509.DNSName(".local"),
        x509.DNSName(".lan"),
        x509.DNSName(".ts.net"),
    ]
    if (
        hostname_limpio
        and hostname_limpio != "localhost"
        and _es_dns_rfc_valido(hostname_limpio)
        and not hostname_limpio.endswith((".local", ".lan", ".ts.net"))
    ):
        permitted.append(x509.DNSName(hostname_limpio))
    for red in _REDES_PERMITIDAS_CA:
        permitted.append(x509.IPAddress(red))

    ahora = datetime.datetime.now(datetime.timezone.utc)
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(ahora - datetime.timedelta(days=1))
        .not_valid_after(ahora + datetime.timedelta(days=_CA_VALIDITY_DAYS))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.NameConstraints(permitted_subtrees=permitted, excluded_subtrees=None),
            critical=True,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    ca_key_path.write_bytes(
        ca_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    _proteger_clave_privada(ca_key_path)
    ca_cert_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    return ca_cert, ca_key, ca_cert_path


def asegurar_certificado_ssl(
    cert_path: Path | None = None,
    key_path: Path | None = None,
) -> tuple[Path, Path]:
    """Garantiza un certificado hoja X.509 (`ca=False`, ≤ 365 días) firmado por una CA local restringida.

    Genera automáticamente `stockagent_ca.crt` (CA local con `NameConstraints` acotada a LAN/localhost/Tailscale)
    y el certificado hoja de servidor en `ruta_cert` + `ruta_key` con permisos NTFS/POSIX restringidos.
    """
    certs_dir = application_root() / "data" / "certs"
    certs_dir.mkdir(parents=True, exist_ok=True)

    ruta_cert = Path(cert_path) if cert_path else (certs_dir / "stockagent.crt")
    ruta_key = Path(key_path) if key_path else (certs_dir / "stockagent.key")
    ruta_cert.parent.mkdir(parents=True, exist_ok=True)
    ruta_key.parent.mkdir(parents=True, exist_ok=True)

    ca_cert_check = ruta_cert.parent / "stockagent_ca.crt"
    ca_invalida = False
    if ca_cert_check.exists():
        try:
            from cryptography import x509

            ca_invalida = _certificado_tiene_dns_invalido(
                x509.load_pem_x509_certificate(ca_cert_check.read_bytes())
            )
        except Exception:
            ca_invalida = True

    if (
        not ca_invalida
        and ruta_cert.exists()
        and ruta_key.exists()
        and not _certificado_requiere_renovacion(ruta_cert)
    ):
        return ruta_cert, ruta_key

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    hostname_limpio = _normalizar_hostname_dns(socket.gethostname() or "stockagent.local")
    ca_cert, ca_key, _ = _cargar_o_crear_ca_local(ruta_cert.parent, hostname_limpio)

    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "AR"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Elola Depósito - StockAgent"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ]
    )

    san_entries: list[x509.GeneralName] = [x509.DNSName("localhost")]
    if hostname_limpio != "localhost" and _es_dns_rfc_valido(hostname_limpio):
        san_entries.append(x509.DNSName(hostname_limpio))
    for ip_str in _obtener_ips_locales():
        try:
            san_entries.append(x509.IPAddress(ipaddress.ip_address(ip_str)))
        except ValueError:
            pass

    ahora = datetime.datetime.now(datetime.timezone.utc)
    leaf_cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(ahora - datetime.timedelta(days=1))
        .not_valid_after(ahora + datetime.timedelta(days=_LEAF_VALIDITY_DAYS))
        .add_extension(x509.SubjectAlternativeName(san_entries), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )

    ruta_key.write_bytes(
        leaf_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    _proteger_clave_privada(ruta_key)

    cadena_pem = (
        leaf_cert.public_bytes(serialization.Encoding.PEM)
        + ca_cert.public_bytes(serialization.Encoding.PEM)
    )
    ruta_cert.write_bytes(cadena_pem)
    return ruta_cert, ruta_key
