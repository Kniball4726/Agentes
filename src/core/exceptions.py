"""Jerarquía unificada de excepciones de StockAgent.

Define errores de dominio e infraestructura con contexto estructurado para
facilitar el logging, la depuración y la notificación amigable al usuario.
"""

from typing import Any


class StockAgentError(Exception):
    """Excepción base para todos los errores internos de StockAgent."""

    def __init__(self, mensaje: str, codigo: str = "ERROR_GENERAL", detalles: dict[str, Any] | None = None) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo
        self.detalles = detalles or {}

    def __str__(self) -> str:
        if self.detalles:
            return f"[{self.codigo}] {self.mensaje} - Detalles: {self.detalles}"
        return f"[{self.codigo}] {self.mensaje}"


# =============================================================================
# ERRORES DE DOMINIO (Reglas de negocio y entidades)
# =============================================================================

class DomainError(StockAgentError):
    """Errores originados por infracción de reglas de negocio."""


# Subdominio: Pedidos y Clientes
class OrderStoreError(DomainError):
    """Error en almacenamiento o procesamiento de pedidos."""


class OrderNotFoundError(OrderStoreError):
    """El pedido solicitado no existe o fue anulado."""

    def __init__(self, identificador: str | int) -> None:
        super().__init__(
            f"No se encontró el pedido '{identificador}'.",
            codigo="PEDIDO_NO_ENCONTRADO",
            detalles={"identificador": identificador},
        )


class OrderValidationError(OrderStoreError):
    """Datos de pedido inválidos o incompletos."""

    def __init__(self, mensaje: str, campo: str | None = None) -> None:
        super().__init__(
            mensaje,
            codigo="VALIDACION_PEDIDO_FALLIDA",
            detalles={"campo": campo} if campo else {},
        )


class OrderConcurrencyError(OrderStoreError):
    """Conflicto de concurrencia o bloqueo de pedido activo por otro usuario."""

    def __init__(self, pedido_id: int, usuario_bloqueador: str) -> None:
        super().__init__(
            f"El pedido #{pedido_id} está siendo editado por '{usuario_bloqueador}'.",
            codigo="PEDIDO_BLOQUEADO",
            detalles={"pedido_id": pedido_id, "usuario_bloqueador": usuario_bloqueador},
        )


# Subdominio: Usuarios y Autenticación
class UserStoreError(DomainError):
    """Error general de gestión de usuarios o credenciales."""


class AuthenticationError(UserStoreError):
    """Fallo de autenticación o contraseña incorrecta."""


class UserNotFoundError(UserStoreError):
    """El usuario indicado no existe en la base de datos."""

    def __init__(self, username: str) -> None:
        super().__init__(
            f"Usuario '{username}' no encontrado.",
            codigo="USUARIO_NO_ENCONTRADO",
            detalles={"username": username},
        )


class UserLockedError(UserStoreError):
    """La cuenta de usuario está temporalmente bloqueada por intentos fallidos."""

    def __init__(self, username: str, segundos_restantes: int) -> None:
        super().__init__(
            f"Cuenta '{username}' bloqueada temporalmente ({segundos_restantes}s restantes).",
            codigo="CUENTA_BLOQUEADA",
            detalles={"username": username, "segundos_restantes": segundos_restantes},
        )


class InvalidRoleError(UserStoreError):
    """El rol asignado o verificado no pertenece a USER_ROLES."""


# Subdominio: Stock y Catálogo
class StockError(DomainError):
    """Error general en operaciones de stock físico o catálogo."""


class InsufficientStockError(StockError):
    """Stock insuficiente para descontar o preparar un producto."""

    def __init__(self, codigo: str, solicitado: int, disponible: int) -> None:
        super().__init__(
            f"Stock insuficiente para '{codigo}': disponible={disponible}, requerido={solicitado}.",
            codigo="STOCK_INSUFICIENTE",
            detalles={"codigo": codigo, "solicitado": solicitado, "disponible": disponible},
        )


class ProductNotFoundError(StockError):
    """El producto buscado por código o código de barras no existe en el catálogo."""

    def __init__(self, clave: str) -> None:
        super().__init__(
            f"Producto '{clave}' no registrado en catálogo maestro.",
            codigo="PRODUCTO_NO_ENCONTRADO",
            detalles={"clave": clave},
        )


class CatalogSyncError(StockError):
    """Error al sincronizar el catálogo entre SQLite y hojas Excel."""


# =============================================================================
# ERRORES DE INFRAESTRUCTURA (I/O, BD, Red, Servicios Externos)
# =============================================================================

class InfrastructureError(StockAgentError):
    """Errores relacionados con recursos externos, sistema de archivos o base de datos."""


class DatabaseError(InfrastructureError):
    """Error durante la ejecución de consultas SQLite o transacciones de base de datos."""


class ReportGenerationError(InfrastructureError):
    """Fallo al renderizar o escribir informes en PDF, XLSX o CSV."""


class IntegrationError(InfrastructureError):
    """Fallo de comunicación con servicios externos (Mercado Libre, Telegram, SMTP)."""
