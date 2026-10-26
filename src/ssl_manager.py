"""Generación y gestión de certificados SSL/TLS autofirmados para modo HTTPS."""

from __future__ import annotations

import datetime
import ipaddress
import socket
from pathlib import Path

from .paths import application_root


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
    return sorted(ips)


def asegurar_certificado_ssl(
    cert_path: Path | None = None,
    key_path: Path | None = None,
) -> tuple[Path, Path]:
    """Garantiza que existan un certificado X.509 y su clave privada para HTTPS.

    Si no se especifican rutas o los archivos no existen, genera automáticamente
    un certificado autofirmado válido por 10 años en `data/certs/` incluyendo
    Subject Alternative Names (SAN) para `localhost` y las IPs de la red local.
    """
    certs_dir = application_root() / "data" / "certs"
    certs_dir.mkdir(parents=True, exist_ok=True)

    ruta_cert = Path(cert_path) if cert_path else (certs_dir / "stockagent.crt")
    ruta_key = Path(key_path) if key_path else (certs_dir / "stockagent.key")
    ruta_cert.parent.mkdir(parents=True, exist_ok=True)
    ruta_key.parent.mkdir(parents=True, exist_ok=True)

    if ruta_cert.exists() and ruta_key.exists():
        return ruta_cert, ruta_key

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    hostname = socket.gethostname() or "stockagent.local"
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "AR"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Elola Depósito - StockAgent"),
            x509.NameAttribute(NameOID.COMMON_NAME, hostname[:64]),
        ]
    )

    san_entries: list[x509.GeneralName] = [
        x509.DNSName("localhost"),
        x509.DNSName(hostname),
    ]
    for ip_str in _obtener_ips_locales():
        try:
            san_entries.append(x509.IPAddress(ipaddress.ip_address(ip_str)))
        except ValueError:
            pass

    ahora = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(ahora - datetime.timedelta(days=1))
        .not_valid_after(ahora + datetime.timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName(san_entries),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=0),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
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
            x509.ExtendedKeyUsage(
                [
                    ExtendedKeyUsageOID.SERVER_AUTH,
                    ExtendedKeyUsageOID.CLIENT_AUTH,
                ]
            ),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    ruta_key.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    ruta_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return ruta_cert, ruta_key
