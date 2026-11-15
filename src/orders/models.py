"""Modelos de datos y constantes para pedidos, clientes, cierres y auditoría."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
import sqlite3

from ..core.exceptions import OrderStoreError

LOGISTICA_OPCIONES: tuple[str, ...] = (
    "Domicilio",
    "Centro de distribución",
    "Transporte",
    "Comisionista",
    "Mabel",
    "Canje",
)

ESTADOS_DESPACHO: tuple[str, ...] = ("armado", "despachado", "entregado")
CANAL_PEDIDO_OPCIONES: tuple[str, ...] = ("mayorista", "mercado_libre", "full", "canje", "otro")
_COLUMNAS_DESPACHO = "numero_guia, estado_despacho, despachado_at, despachado_por, entregado_at, entregado_por"


def clasificar_canal_pedido(
    tipo_archivo: str = "",
    cliente: str = "",
    nombre_archivo: str = "",
    nota_pedido: str = "",
    logistica: str = "",
    canal_explicito: str = "",
) -> str:
    """Clasifica de forma determinista el canal de venta de un pedido.

    Retorna `'mayorista'`, `'mercado_libre'`, `'full'`, `'canje'` u `'otro'`.
    """
    canal_clean = (canal_explicito or "").strip().lower()
    if canal_clean in CANAL_PEDIDO_OPCIONES:
        return canal_clean

    tipo = (tipo_archivo or "").strip().lower()
    cli = (cliente or "").strip().lower()
    arch = (nombre_archivo or "").strip().lower()
    nota = (nota_pedido or "").strip().lower()
    log = (logistica or "").strip().lower()
    texto = f"{cli} {arch} {nota}"

    if "full" in texto:
        return "full"
    if tipo == "docx" or "mercado libre" in cli or nota.startswith("ml") or arch.startswith("ml_"):
        return "mercado_libre"
    if log == "canje" or tipo == "excel":
        return "canje"
    if tipo == "pdf" or cli or nota:
        return "mayorista"
    return "otro"


def calcular_hash_archivo(ruta_o_bytes: Path | bytes | str) -> str:
    """Calcula el hash SHA-256 de un archivo o flujo de bytes para detección de duplicados."""
    hasher = hashlib.sha256()
    if isinstance(ruta_o_bytes, (str, Path)):
        p = Path(ruta_o_bytes)
        if not p.exists() or not p.is_file():
            return ""
        try:
            with open(p, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
        except Exception:
            return ""
    elif isinstance(ruta_o_bytes, (bytes, bytearray)):
        hasher.update(ruta_o_bytes)
    else:
        return ""
    return hasher.hexdigest()


@dataclass(frozen=True)
class Cliente:
    """Entidad inmutable que representa un cliente comercial."""

    id: int
    nombre: str
    activo: bool
    created_at: str
    codigo: str = ""
    direccion: str = ""


@dataclass(frozen=True)
class CierreJornada:
    """Resumen consolidado del cierre diario de pedidos."""

    id: int
    usuario: str
    cantidad_pedidos: int
    articulos_totales: int
    resumen_pedidos: str
    archivo_pdf: str
    archivo_excel: str
    created_at: str
    archivo_hoja_ruta: str = ""


@dataclass(frozen=True)
class CierreMercado:
    """Resumen consolidado de una tanda de cierre de Mercado Libre / Full por un picker."""

    id: int
    usuario: str
    tipo_mercado: str
    cantidad_pedidos: int
    articulos_totales: int
    resumen_pedidos: str
    archivo_pdf: str
    archivo_excel: str
    created_at: str


@dataclass(frozen=True)
class RegistroAuditoria:
    """Entrada inmutable del registro de eventos de auditoría forense."""

    id: int
    usuario: str
    accion: str
    detalle: str
    created_at: str


@dataclass(frozen=True)
class Pedido:
    """Entidad inmutable representativa de una orden o pedido despachado."""

    id: int
    nota_pedido: str
    numero_pedido: str
    cliente: str
    bultos: int
    logistica: str
    armador: str
    tipo_archivo: str
    nombre_archivo: str
    agregado: bool
    articulos_descontados: int
    resumen_items: str
    created_at: str
    estado: str
    fecha_retiro: str = ""
    archivo_descuento: str = ""
    cierre_id: int | None = None
    cierre_mercado_id: int | None = None
    archivo_hash: str = ""
    numero_guia: str = ""
    estado_despacho: str = "armado"
    despachado_at: str = ""
    despachado_por: str = ""
    entregado_at: str = ""
    entregado_por: str = ""
    canal: str = ""

    @property
    def canal_efectivo(self) -> str:
        """Devuelve el canal normalizado del pedido (explícito o inferido)."""
        return clasificar_canal_pedido(
            tipo_archivo=self.tipo_archivo,
            cliente=self.cliente,
            nombre_archivo=self.nombre_archivo,
            nota_pedido=self.nota_pedido,
            logistica=self.logistica,
            canal_explicito=self.canal,
        )


@dataclass(frozen=True)
class MensajeChat:
    """Mensaje individual del chat interno de equipo entre terminales."""

    id: int
    emisor: str
    destinatario: str
    mensaje: str
    leido: bool
    created_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> MensajeChat:
        return cls(
            id=int(row["id"]),
            emisor=str(row["emisor"]),
            destinatario=str(row["destinatario"]),
            mensaje=str(row["mensaje"]),
            leido=bool(row["leido"]),
            created_at=str(row["created_at"]),
        )
