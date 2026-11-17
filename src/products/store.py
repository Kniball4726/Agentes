"""Módulo principal que ensambla ProductStore mediante composición de repositorios."""

from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Callable, Iterable

from ..core.sqlite_utils import open_sqlite_connection
from .catalog_read_repo import CatalogReadRepository
from .catalog_write_repo import CatalogWriteRepository
from .movements_repo import MovementsRepository
from .movements_report_repo import MovementsReportRepository
from .notifications_repo import NotificationsRepository
from .physical_repo import PhysicalRepository
from .schema import inicializar_esquema_productos


class ProductStore:
    """Gestor unificado de base de datos SQLite para productos, catálogo, despachos e inventario."""

    _initialized_dbs: set[tuple[str, int, int]] = set()

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_sku: dict[str, sqlite3.Row] = {}
        self._cache_barcode: dict[str, sqlite3.Row] = {}
        self._cache_data_version: int | None = None
        self._cache_ts: float = 0.0
        self._cache_ttl: float = 15.0
        self._cache_lock = threading.Lock()
        self.catalog_read = CatalogReadRepository(self)
        self.catalog_write = CatalogWriteRepository(self)
        self.movements_repo = MovementsRepository(self._connect)
        self.movements_report_repo = MovementsReportRepository(self._connect)
        self.physical_repo = PhysicalRepository(self._connect)
        self.notifications_repo = NotificationsRepository(self._connect)
        self._initialize()

    def invalidar_cache(self) -> None:
        """Invalida inmediatamente el caché en memoria de productos."""
        with self._cache_lock:
            self._cache_sku.clear()
            self._cache_barcode.clear()
            self._cache_data_version = None
            self._cache_ts = 0.0

    def _es_cache_valido(self, connection: sqlite3.Connection | None = None) -> bool:
        """Verifica vigencia del caché en memoria por TTL y SQLite PRAGMA data_version."""
        ahora = time.monotonic()
        if ahora - self._cache_ts > self._cache_ttl:
            return False
        if connection is not None and self._cache_data_version is not None:
            try:
                dv = connection.execute("PRAGMA data_version").fetchone()[0]
                if dv != self._cache_data_version:
                    return False
            except Exception:
                return False
        return True

    def _connect(self) -> sqlite3.Connection:
        return open_sqlite_connection(
            self.database_path,
            synchronous_normal=True,
            temp_store_memory=True,
        )

    def _db_signature(self) -> tuple[str, int, int] | None:
        try:
            if not self.database_path.exists():
                return None
            st = self.database_path.stat()
            if st.st_size <= 0:
                return None
            return (str(self.database_path.resolve()), st.st_ctime_ns, st.st_ino)
        except OSError:
            return None

    def _initialize(self) -> None:
        sig_before = self._db_signature()
        if sig_before is not None and sig_before in self._initialized_dbs:
            return
        with closing(self._connect()) as connection, connection:
            inicializar_esquema_productos(connection)
        sig_after = self._db_signature()
        if sig_after is not None:
            self._initialized_dbs.add(sig_after)

    # Delegación explícita hacia repositorios compuestos

    def load_catalog_fast(self) -> tuple[bool, dict[str, str], list[sqlite3.Row]]:
        return self.catalog_read.load_catalog_fast()

    def is_template_imported(self) -> bool:
        return self.catalog_read.is_template_imported()

    def get_all_metadata(self) -> dict[str, str]:
        return self.catalog_read.get_all_metadata()

    def get_metadata(self, key: str, default: str = "") -> str:
        return self.catalog_read.get_metadata(key, default=default)

    def list_catalog_rows(self, include_inactive: bool = False) -> list[sqlite3.Row]:
        return self.catalog_read.list_catalog_rows(include_inactive=include_inactive)

    def list_products(self, solo_activos: bool = False) -> list[sqlite3.Row]:
        return self.catalog_read.list_products(solo_activos=solo_activos)

    def buscar_productos(self, termino: str, limite: int = 50) -> list[sqlite3.Row]:
        return self.catalog_read.buscar_productos(termino, limite=limite)

    def get_product(self, code: object) -> sqlite3.Row | None:
        return self.catalog_read.get_product(code)

    def _query_producto_raw(self, code: str) -> sqlite3.Row | None:
        return self.catalog_read._query_producto_raw(code)

    def get_product_by_barcode(self, cod_barras: object) -> sqlite3.Row | None:
        return self.catalog_read.get_product_by_barcode(cod_barras)

    def _query_barcode_raw(self, cod_barras: str) -> sqlite3.Row | None:
        return self.catalog_read._query_barcode_raw(cod_barras)

    def find_product_by_code_or_barcode(self, query: object) -> sqlite3.Row | None:
        return self.catalog_read.find_product_by_code_or_barcode(query)

    def _find_product_raw(self, query: str) -> sqlite3.Row | None:
        return self.catalog_read._find_product_raw(query)

    def set_metadata(self, key: str, value: str) -> None:
        self.catalog_write.set_metadata(key, value)

    def import_template_once(
        self,
        products: Iterable[tuple[int, str, str, int]],
        metadata: dict[str, str] | None = None,
    ) -> None:
        self.catalog_write.import_template_once(products, metadata=metadata)

    def add_product_after(
        self,
        code: str,
        name: str,
        reference_code: str,
        stock: int,
        synchronize_template: Callable[[int], list[int]] | None = None,
        restore_template: Callable[[], None] | None = None,
        stock_minimo: int = 5,
        stock_maximo: int = 100,
        cod_barras: str = "",
    ) -> tuple[int, str]:
        return self.catalog_write.add_product_after(
            code=code,
            name=name,
            reference_code=reference_code,
            stock=stock,
            synchronize_template=synchronize_template,
            restore_template=restore_template,
            stock_minimo=stock_minimo,
            stock_maximo=stock_maximo,
            cod_barras=cod_barras,
        )

    def update_product(self, *args, **kwargs):
        return self.catalog_write.update_product(*args, **kwargs)

    def actualizar_ubicacion(self, code: str, ubicacion: str) -> bool:
        return self.catalog_write.actualizar_ubicacion(code, ubicacion)

    def set_product_barcode(self, code: object, cod_barras: object) -> None:
        self.catalog_write.set_product_barcode(code, cod_barras)

    def set_product_active(self, code: str, active: bool) -> None:
        self.catalog_write.set_product_active(code, active)

    def sync_active_status_with_codes(self, active_codes: Iterable[str]) -> tuple[int, int]:
        return self.catalog_write.sync_active_status_with_codes(active_codes)

    def update_product_thresholds(
        self, code: str, stock_minimo: int, stock_maximo: int
    ) -> None:
        self.catalog_write.update_product_thresholds(code, stock_minimo, stock_maximo)

    def update_stocks(self, *args, **kwargs) -> int:
        return self.catalog_write.update_stocks(*args, **kwargs)

    def record_dispatch(
        self,
        tipo_origen: str,
        nombre_archivo: str,
        total_articulos: int,
        detalles: list[tuple[str, int, int, int]],
        reporte_archivo: str = "",
        usuario: str = "sistema",
    ) -> int:
        return self.movements_repo.record_dispatch(
            tipo_origen=tipo_origen,
            nombre_archivo=nombre_archivo,
            total_articulos=total_articulos,
            detalles=detalles,
            reporte_archivo=reporte_archivo,
            usuario=usuario,
        )

    def register_movements(
        self,
        movements: list[tuple[str, str, int, str]],
        usuario: str = "sistema",
        detalle: str = "",
    ) -> None:
        self.movements_repo.register_movements(
            movements, usuario=usuario, detalle=detalle
        )

    def enrich_latest_movements(
        self,
        product_codes: Iterable[str],
        usuario: str = "sistema",
        detalle: str = "",
        movement_type: str | None = None,
    ) -> None:
        self.movements_repo.enrich_latest_movements(
            product_codes, usuario=usuario, detalle=detalle, movement_type=movement_type
        )

    def list_recent_movements(
        self,
        product_code: str = "",
        movement_type: str = "",
        limit: int = 150,
    ) -> list[sqlite3.Row]:
        return self.movements_repo.list_recent_movements(
            product_code=product_code, movement_type=movement_type, limit=limit
        )

    def query_movements(
        self,
        date_from: str,
        date_to: str,
        movement_type: str | None = None,
        top_n: int | None = None,
    ) -> list[sqlite3.Row]:
        return self.movements_repo.query_movements(
            date_from=date_from,
            date_to=date_to,
            movement_type=movement_type,
            top_n=top_n,
        )

    def get_period_movements_summary(
        self,
        date_from: str,
        date_to: str,
        order_by: str = "catalog",
        strict_after_from: bool = False,
    ) -> dict[str, Any]:
        return self.movements_report_repo.get_period_movements_summary(
            date_from=date_from,
            date_to=date_to,
            order_by=order_by,
            strict_after_from=strict_after_from,
        )

    def get_product_kardex(
        self,
        product_query: str,
        date_from: str = "",
        date_to: str = "",
        limit: int = 300,
    ) -> dict[str, Any]:
        return self.movements_report_repo.get_product_kardex(
            product_query=product_query,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )

    def get_rotation_ranking(
        self,
        date_from: str,
        date_to: str,
        dias_periodo: int = 30,
        top_n: int = 60,
    ) -> list[dict[str, Any]]:
        return self.movements_report_repo.get_rotation_ranking(
            date_from=date_from,
            date_to=date_to,
            dias_periodo=dias_periodo,
            top_n=top_n,
        )

    def obtener_mapa_runway_inventario(self, dias_ventana: int = 14) -> dict[str, float]:
        """Retorna {codigo_producto: dias_runway} según el ritmo de salidas recientes."""
        return self.movements_report_repo.obtener_mapa_runway_inventario(dias_ventana=dias_ventana)

    def record_physical_inventory(
        self,
        usuario: str,
        nombre_archivo: str,
        reporte_unificado: str,
        detalles: list[tuple[str, str, int, int, int, str]],
    ) -> int:
        return self.physical_repo.record_physical_inventory(
            usuario=usuario,
            nombre_archivo=nombre_archivo,
            reporte_unificado=reporte_unificado,
            detalles=detalles,
        )

    def list_physical_inventories(self, limit: int = 20) -> list[sqlite3.Row]:
        return self.physical_repo.list_physical_inventories(limit=limit)

    def get_physical_inventory_details(self, inventario_id: int) -> list[sqlite3.Row]:
        return self.physical_repo.get_physical_inventory_details(inventario_id)

    def get_latest_physical_inventory(
        self,
    ) -> tuple[sqlite3.Row | None, list[sqlite3.Row]]:
        return self.physical_repo.get_latest_physical_inventory()

    def get_replenishment_analysis(self, only_critical: bool = True) -> list[sqlite3.Row]:
        return self.notifications_repo.get_replenishment_analysis(only_critical=only_critical)

    def create_admin_notification(
        self,
        title: str,
        message: str,
        operator_username: str,
        notification_type: str = "descuento",
        details: str = "",
    ) -> int:
        return self.notifications_repo.create_admin_notification(
            title=title,
            message=message,
            operator_username=operator_username,
            notification_type=notification_type,
            details=details,
        )

    def list_admin_notifications(
        self, unread_only: bool = False, limit: int = 50
    ) -> list[sqlite3.Row]:
        return self.notifications_repo.list_admin_notifications(
            unread_only=unread_only, limit=limit
        )

    def get_unread_notifications_count(self) -> int:
        return self.notifications_repo.get_unread_notifications_count()

    def mark_notification_as_read(self, notification_id: int) -> None:
        self.notifications_repo.mark_notification_as_read(notification_id)

    def mark_all_notifications_as_read(self) -> int:
        return self.notifications_repo.mark_all_notifications_as_read()
