"""Repositorio y operaciones de gestión de clientes comerciales."""

from __future__ import annotations

import sqlite3
from typing import Any

from .models import Cliente


class ClientRepositoryMixin:
    """Mixin que proporciona operaciones CRUD para la entidad Cliente."""

    def listar_clientes(self) -> list[Cliente]:
        """Retorna todos los clientes activos ordenados alfabéticamente."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, nombre, activo, created_at, codigo, direccion FROM clientes WHERE activo = 1 ORDER BY nombre COLLATE NOCASE"
            ).fetchall()
        return [
            Cliente(
                id=r["id"],
                nombre=r["nombre"],
                activo=bool(r["activo"]),
                created_at=r["created_at"],
                codigo=r["codigo"] or "",
                direccion=r["direccion"] or "",
            )
            for r in rows
        ]

    def listar_nombres_clientes(self) -> list[str]:
        """Retorna los nombres de todos los clientes activos."""
        return [c.nombre for c in self.listar_clientes()]

    def buscar_clientes(self, query: str = "") -> list[Cliente]:
        """Busca clientes activos filtrando por nombre, código o dirección."""
        q = (query or "").strip()
        if not q:
            return self.listar_clientes()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, nombre, activo, created_at, codigo, direccion
                FROM clientes
                WHERE activo = 1 AND (
                    nombre LIKE ? COLLATE NOCASE
                    OR codigo LIKE ?
                    OR direccion LIKE ? COLLATE NOCASE
                )
                ORDER BY nombre COLLATE NOCASE
                """,
                (f"%{q}%", f"%{q}%", f"%{q}%"),
            ).fetchall()
        return [
            Cliente(
                id=r["id"],
                nombre=r["nombre"],
                activo=bool(r["activo"]),
                created_at=r["created_at"],
                codigo=r["codigo"] or "",
                direccion=r["direccion"] or "",
            )
            for r in rows
        ]

    def crear_cliente(
        self,
        nombre: str,
        usuario: str = "Sistema",
        codigo: str = "",
        direccion: str = "",
    ) -> Cliente:
        """Crea un nuevo cliente o reactiva uno inactivo existente."""
        nombre = nombre.strip()
        codigo = codigo.strip()
        direccion = direccion.strip()
        if not nombre:
            raise ValueError("El nombre del cliente no puede estar vacío.")
        if len(nombre) > 120:
            raise ValueError("El nombre del cliente no puede superar los 120 caracteres.")

        with self._connect() as connection:
            existente = connection.execute(
                "SELECT id, nombre, activo, created_at, codigo, direccion FROM clientes WHERE nombre = ? COLLATE NOCASE",
                (nombre,),
            ).fetchone()

        if existente:
            if existente["activo"] == 1:
                raise ValueError(f"El cliente '{nombre}' ya existe.")
            with self._connect() as connection, connection:
                connection.execute(
                    "UPDATE clientes SET activo = 1, nombre = ?, codigo = COALESCE(NULLIF(?, ''), codigo), direccion = COALESCE(NULLIF(?, ''), direccion) WHERE id = ?",
                    (nombre, codigo, direccion, existente["id"]),
                )
            self.registrar_auditoria(usuario, "REACTIVAR_CLIENTE", f"Reactivación de cliente '{nombre}'")
            return Cliente(
                id=existente["id"],
                nombre=nombre,
                activo=True,
                created_at=existente["created_at"],
                codigo=codigo or (existente["codigo"] or ""),
                direccion=direccion or (existente["direccion"] or ""),
            )

        try:
            with self._connect() as connection, connection:
                cursor = connection.execute(
                    "INSERT INTO clientes (nombre, activo, codigo, direccion) VALUES (?, 1, ?, ?)",
                    (nombre, codigo, direccion),
                )
                row = connection.execute(
                    "SELECT id, nombre, activo, created_at, codigo, direccion FROM clientes WHERE id = ?",
                    (cursor.lastrowid,),
                ).fetchone()
        except sqlite3.IntegrityError as error:
            raise ValueError(f"El cliente '{nombre}' ya existe.") from error
        cliente_nuevo = Cliente(
            id=row["id"],
            nombre=row["nombre"],
            activo=bool(row["activo"]),
            created_at=row["created_at"],
            codigo=row["codigo"] or "",
            direccion=row["direccion"] or "",
        )
        self.registrar_auditoria(usuario, "CREAR_CLIENTE", f"Alta de cliente '{nombre}' (código: '{codigo}')")
        return cliente_nuevo

    def registrar_cliente(
        self,
        nombre: str,
        usuario: str = "Sistema",
        codigo: str = "",
        direccion: str = "",
    ) -> Cliente:
        """Alias compatible para crear o asegurar la existencia de un cliente."""
        return self.crear_cliente(nombre, usuario=usuario, codigo=codigo, direccion=direccion)

    def obtener_o_crear_cliente(
        self,
        nombre: str,
        codigo: str = "",
        direccion: str = "",
        usuario: str = "Sistema",
    ) -> Cliente:
        """Busca un cliente por nombre; si no existe, lo crea. Si existe y se proporcionan código o dirección vacíos, los actualiza."""
        nombre = nombre.strip()
        codigo = codigo.strip()
        direccion = direccion.strip()
        if not nombre:
            raise ValueError("El nombre del cliente no puede estar vacío.")

        with self._connect() as connection:
            existente = connection.execute(
                "SELECT id, nombre, activo, created_at, codigo, direccion FROM clientes WHERE nombre = ? COLLATE NOCASE",
                (nombre,),
            ).fetchone()
            if not existente and codigo:
                existente = connection.execute(
                    "SELECT id, nombre, activo, created_at, codigo, direccion FROM clientes WHERE codigo = ? AND codigo != ''",
                    (codigo,),
                ).fetchone()

        if existente:
            c_id = existente["id"]
            c_nom = existente["nombre"]
            c_activo = bool(existente["activo"])
            c_cod = existente["codigo"] or ""
            c_dir = existente["direccion"] or ""
            update_needed = False
            if not c_activo:
                c_activo = True
                update_needed = True
            if codigo and not c_cod:
                c_cod = codigo
                update_needed = True
            if direccion and not c_dir:
                c_dir = direccion
                update_needed = True

            if update_needed:
                with self._connect() as connection, connection:
                    connection.execute(
                        "UPDATE clientes SET activo = 1, codigo = ?, direccion = ? WHERE id = ?",
                        (c_cod, c_dir, c_id),
                    )
            return Cliente(
                id=c_id,
                nombre=c_nom,
                activo=c_activo,
                created_at=existente["created_at"],
                codigo=c_cod,
                direccion=c_dir,
            )

        return self.crear_cliente(nombre, usuario=usuario, codigo=codigo, direccion=direccion)

    def actualizar_cliente(
        self,
        cliente_id: int,
        nuevo_nombre: str,
        actualizar_pedidos: bool = True,
        usuario: str = "Sistema",
        codigo: str | None = None,
        direccion: str | None = None,
    ) -> Cliente:
        """Actualiza el nombre, código y dirección de un cliente y opcionalmente sus pedidos vinculados."""
        nuevo_nombre = nuevo_nombre.strip()
        if not nuevo_nombre:
            raise ValueError("El nombre del cliente no puede estar vacío.")
        if len(nuevo_nombre) > 120:
            raise ValueError("El nombre del cliente no puede superar los 120 caracteres.")

        with self._connect() as connection:
            actual = connection.execute(
                "SELECT id, nombre, activo, created_at, codigo, direccion FROM clientes WHERE id = ?",
                (cliente_id,),
            ).fetchone()
            if not actual:
                raise ValueError(f"No se encontró el cliente con ID {cliente_id}.")

            nombre_anterior = actual["nombre"]
            if nombre_anterior.strip().lower() != nuevo_nombre.lower():
                existente = connection.execute(
                    "SELECT id FROM clientes WHERE nombre = ? COLLATE NOCASE AND id != ?",
                    (nuevo_nombre, cliente_id),
                ).fetchone()
                if existente:
                    raise ValueError(f"Ya existe otro cliente con el nombre '{nuevo_nombre}'.")

            nuevo_codigo = actual["codigo"] if codigo is None else codigo.strip()
            nueva_direccion = actual["direccion"] if direccion is None else direccion.strip()

            with connection:
                connection.execute(
                    "UPDATE clientes SET nombre = ?, codigo = ?, direccion = ? WHERE id = ?",
                    (nuevo_nombre, nuevo_codigo, nueva_direccion, cliente_id),
                )
                if actualizar_pedidos and nombre_anterior != nuevo_nombre:
                    connection.execute(
                        "UPDATE pedidos SET cliente = ? WHERE cliente = ? COLLATE NOCASE",
                        (nuevo_nombre, nombre_anterior),
                    )

        self.registrar_auditoria(
            usuario,
            "ACTUALIZAR_CLIENTE",
            f"Cliente ID {cliente_id} actualizado ('{nombre_anterior}' -> '{nuevo_nombre}', cod: '{nuevo_codigo}')",
        )
        return Cliente(
            id=cliente_id,
            nombre=nuevo_nombre,
            activo=bool(actual["activo"]),
            created_at=actual["created_at"],
            codigo=nuevo_codigo,
            direccion=nueva_direccion,
        )

    def eliminar_cliente(self, cliente_id: int, usuario: str = "Sistema") -> None:
        """Da de baja lógica a un cliente desactivándolo."""
        with self._connect() as connection:
            actual = connection.execute(
                "SELECT id, nombre FROM clientes WHERE id = ?",
                (cliente_id,),
            ).fetchone()
            if not actual:
                raise ValueError(f"No se encontró el cliente con ID {cliente_id}.")

            with connection:
                connection.execute(
                    "UPDATE clientes SET activo = 0 WHERE id = ?",
                    (cliente_id,),
                )

        self.registrar_auditoria(
            usuario,
            "ELIMINAR_CLIENTE",
            f"Cliente ID {cliente_id} ('{actual['nombre']}') desactivado",
        )
