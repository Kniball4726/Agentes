"""Repositorio desacoplado para máquina de estados de despacho y seguimiento por código/remito."""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from ..core.exceptions import OrderStoreError
from .models import ESTADOS_DESPACHO, _COLUMNAS_DESPACHO, Pedido
from .protocols import AuditLogFn, MapPedidoFn, OrderConnectFn

_COLUMNAS_SELECT_PEDIDO = (
    "id, nota_pedido, numero_pedido, cliente, bultos, logistica, armador, "
    "tipo_archivo, nombre_archivo, agregado, articulos_descontados, "
    "resumen_items, created_at, estado, fecha_retiro, archivo_descuento, "
    f"cierre_id, cierre_mercado_id, archivo_hash, canal, {_COLUMNAS_DESPACHO}"
)


class DispatchRepository:
    """Repositorio que gestiona transiciones de estado de despacho (`armado` -> `despachado` -> `entregado`)."""

    def __init__(
        self,
        connect_fn: OrderConnectFn,
        map_pedido_fn: MapPedidoFn,
        audit_fn: AuditLogFn,
    ) -> None:
        self._connect = connect_fn
        self._map_pedido = map_pedido_fn
        self._audit = audit_fn

    @staticmethod
    def extraer_remito_de_codigo(texto: str) -> str:
        """Extrae el número de remito de un payload QR o texto escaneado."""
        limpio = (texto or "").strip()
        coincidencia = re.search(r"REMITO:\s*([^|]+)", limpio, re.IGNORECASE)
        return coincidencia.group(1).strip() if coincidencia else limpio

    @staticmethod
    def extraer_datos_qr_despacho(texto: str) -> dict[str, Any]:
        """Extrae remito, índice de bulto y total de bultos de un código QR de rótulo o texto plano."""
        limpio = (texto or "").strip()
        remito = DispatchRepository.extraer_remito_de_codigo(limpio)
        bulto_num: int | None = None
        total_bultos: int | None = None
        coinc_bulto = re.search(r"BULTOS?:\s*(\d+)\s*/\s*(\d+)", limpio, re.IGNORECASE)
        if coinc_bulto:
            try:
                bulto_num = int(coinc_bulto.group(1))
                total_bultos = int(coinc_bulto.group(2))
            except ValueError:
                bulto_num = None
                total_bultos = None
        return {
            "remito": remito,
            "bulto_num": bulto_num,
            "total_bultos": total_bultos,
        }

    def listar_pedidos_por_estado_despacho(
        self,
        estados: tuple[str, ...] | None = None,
        limit: int = 200,
    ) -> list[Pedido]:
        """Lista pedidos no anulados filtrados por estado de despacho."""
        limite_seguro = max(1, min(int(limit or 200), 1000))
        with self._connect() as connection:
            if estados:
                est_validos = [e.strip().lower() for e in estados if e and e.strip().lower() in ESTADOS_DESPACHO]
                if not est_validos:
                    return []
                placeholders = ", ".join("?" for _ in est_validos)
                orden = (
                    "ORDER BY CASE WHEN despachado_at != '' THEN despachado_at ELSE created_at END DESC, id DESC"
                    if "armado" not in est_validos
                    else "ORDER BY id DESC"
                )
                rows = connection.execute(
                    f"SELECT {_COLUMNAS_SELECT_PEDIDO} FROM pedidos "
                    f"WHERE estado != 'anulado' AND LOWER(COALESCE(estado_despacho, 'armado')) IN ({placeholders}) "
                    f"{orden} LIMIT ?",
                    (*est_validos, limite_seguro),
                ).fetchall()
            else:
                rows = connection.execute(
                    f"SELECT {_COLUMNAS_SELECT_PEDIDO} FROM pedidos "
                    "WHERE estado != 'anulado' ORDER BY id DESC LIMIT ?",
                    (limite_seguro,),
                ).fetchall()
        return [self._map_pedido(r) for r in rows]

    def obtener_bultos_escaneados(self, pedido_id: int) -> list[int]:
        """Devuelve la lista ordenada de números de bulto ya escaneados para un pedido."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT bulto_num FROM despacho_bultos_escaneados WHERE pedido_id = ? ORDER BY bulto_num ASC",
                (pedido_id,),
            ).fetchall()
        return [int(r["bulto_num"]) for r in rows]

    def obtener_mapa_bultos_escaneados(self, pedido_ids: list[int]) -> dict[int, list[int]]:
        """Devuelve `{pedido_id: [bultos_escaneados]}` en una sola consulta SQL."""
        ids_limpios = [int(pid) for pid in pedido_ids if pid is not None]
        if not ids_limpios:
            return {}
        placeholders = ", ".join("?" for _ in ids_limpios)
        resultado: dict[int, list[int]] = {pid: [] for pid in ids_limpios}
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT pedido_id, bulto_num FROM despacho_bultos_escaneados "
                f"WHERE pedido_id IN ({placeholders}) ORDER BY pedido_id ASC, bulto_num ASC",
                tuple(ids_limpios),
            ).fetchall()
        for r in rows:
            resultado.setdefault(int(r["pedido_id"]), []).append(int(r["bulto_num"]))
        return resultado

    def buscar_pedido_por_nota(self, nota_pedido: str) -> Pedido | None:
        """Busca un pedido por su nota/remito sin distinguir mayúsculas."""
        nota = (nota_pedido or "").strip()
        if not nota:
            return None
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT {_COLUMNAS_SELECT_PEDIDO} FROM pedidos WHERE nota_pedido = ? COLLATE NOCASE LIMIT 1",
                (nota,),
            ).fetchone()
        return self._map_pedido(row) if row is not None else None

    def actualizar_estado_despacho(
        self,
        pedido_id: int,
        nuevo_estado: str,
        usuario: str = "Sistema",
        permitir_retroceso: bool = False,
    ) -> Pedido:
        """Valida y actualiza el estado de despacho de un pedido con registro de auditoría."""
        if nuevo_estado not in ESTADOS_DESPACHO:
            raise ValueError(f"Estado de despacho inválido: {nuevo_estado}")

        with self._connect() as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT nota_pedido, estado, estado_despacho FROM pedidos WHERE id = ?",
                (pedido_id,),
            ).fetchone()
            if row is None:
                raise OrderStoreError("No se encontró el pedido.")
            if row["estado"] == "anulado":
                raise OrderStoreError("El pedido está anulado y no admite cambios de estado.")

            actual = row["estado_despacho"] or "armado"
            idx_actual = ESTADOS_DESPACHO.index(actual)
            idx_nuevo = ESTADOS_DESPACHO.index(nuevo_estado)
            if idx_nuevo == idx_actual:
                raise OrderStoreError(f"El pedido ya figura como '{actual}'.")
            if idx_nuevo < idx_actual and not permitir_retroceso:
                raise OrderStoreError("Solo un administrador puede retroceder el estado de un pedido.")
            if idx_nuevo > idx_actual + 1:
                raise OrderStoreError(
                    f"Primero debe marcarse como '{ESTADOS_DESPACHO[idx_actual + 1]}'."
                )

            ahora = "strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')"
            if nuevo_estado == "despachado":
                connection.execute(
                    f"UPDATE pedidos SET estado_despacho = ?, despachado_at = {ahora}, despachado_por = ?, "
                    "entregado_at = '', entregado_por = '' WHERE id = ?",
                    (nuevo_estado, usuario, pedido_id),
                )
            elif nuevo_estado == "entregado":
                connection.execute(
                    f"UPDATE pedidos SET estado_despacho = ?, entregado_at = {ahora}, entregado_por = ? WHERE id = ?",
                    (nuevo_estado, usuario, pedido_id),
                )
            else:
                connection.execute(
                    "UPDATE pedidos SET estado_despacho = ?, despachado_at = '', despachado_por = '', "
                    "entregado_at = '', entregado_por = '' WHERE id = ?",
                    (nuevo_estado, pedido_id),
                )
                connection.execute(
                    "DELETE FROM despacho_bultos_escaneados WHERE pedido_id = ?",
                    (pedido_id,),
                )
            remito = row["nota_pedido"]

        self._audit(
            usuario=usuario,
            accion="ESTADO_DESPACHO",
            detalle=f"Remito {remito}: {actual} → {nuevo_estado}",
        )
        with self._connect() as connection:
            fila = connection.execute(
                f"SELECT {_COLUMNAS_SELECT_PEDIDO} FROM pedidos WHERE id = ?",
                (pedido_id,),
            ).fetchone()
        return self._map_pedido(fila)

    def avanzar_estado_lote(
        self,
        pedido_ids: list[int],
        nuevo_estado: str,
        usuario: str = "Operador",
        permitir_retroceso: bool = False,
    ) -> int:
        """Actualiza por lote el estado de despacho de múltiples pedidos válidos."""
        if not pedido_ids:
            return 0
        nuevo = nuevo_estado.strip().lower()
        if nuevo not in ESTADOS_DESPACHO:
            raise OrderStoreError(f"Estado de despacho inválido: '{nuevo_estado}'")
        actualizados = 0
        for pid in pedido_ids:
            try:
                self.actualizar_estado_despacho(
                    pid, nuevo, usuario=usuario, permitir_retroceso=permitir_retroceso
                )
                actualizados += 1
            except Exception:
                continue
        return actualizados

    def avanzar_estado_por_codigo(
        self,
        codigo: str = "",
        usuario: str = "Sistema",
        *,
        codigo_qr_o_remito: str = "",
        nuevo_estado: str | None = None,
        permitir_retroceso: bool = False,
    ) -> tuple[bool, str, Pedido | None]:
        """Avanza el estado de un pedido buscado por texto QR o número de remito."""
        raw = codigo or codigo_qr_o_remito
        remito = self.extraer_remito_de_codigo(raw)
        pedido = self.buscar_pedido_por_nota(remito)
        if pedido is None:
            return False, f"No se encontró ningún pedido con el remito '{remito}'.", None
        if pedido.estado == "anulado":
            return False, f"El pedido {pedido.nota_pedido} se encuentra ANULADO.", pedido
        if nuevo_estado:
            destino = nuevo_estado.strip().lower()
        else:
            idx = ESTADOS_DESPACHO.index(pedido.estado_despacho)
            if idx >= len(ESTADOS_DESPACHO) - 1:
                return False, f"El pedido {pedido.nota_pedido} ya figura como ENTREGADO.", pedido
            destino = ESTADOS_DESPACHO[idx + 1]
        try:
            actualizado = self.actualizar_estado_despacho(
                pedido.id, destino, usuario=usuario, permitir_retroceso=permitir_retroceso
            )
            return (
                True,
                f"Remito #{actualizado.nota_pedido} ({actualizado.cliente}) → {actualizado.estado_despacho.upper()}",
                actualizado,
            )
        except Exception as e:
            return False, str(e), pedido

    def registrar_escaneo_bulto_despacho(
        self,
        codigo_qr_o_remito: str,
        usuario: str = "Despachador",
    ) -> dict[str, Any]:
        """Procesa el escaneo QR/pistola de un bulto y pasa el pedido de `armado` → `despachado` al completar los bultos."""
        datos = self.extraer_datos_qr_despacho(codigo_qr_o_remito)
        remito = str(datos["remito"] or "").strip()
        bulto_num: int | None = datos["bulto_num"]
        total_qr: int | None = datos["total_bultos"]

        if not remito:
            return {
                "ok": False,
                "completado": False,
                "duplicado": False,
                "requiere_confirmacion_bultos": False,
                "mensaje": "Código vacío. Escanee el QR del rótulo o ingrese un número de remito.",
                "pedido": None,
                "bultos_escaneados": [],
                "bultos_esperados": 0,
            }

        ahora_sql = "strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')"
        auditoria_detalle = ""

        with self._connect() as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                f"SELECT {_COLUMNAS_SELECT_PEDIDO} FROM pedidos WHERE nota_pedido = ? COLLATE NOCASE LIMIT 1",
                (remito,),
            ).fetchone()
            if row is None:
                return {
                    "ok": False,
                    "completado": False,
                    "duplicado": False,
                    "requiere_confirmacion_bultos": False,
                    "mensaje": f"No se encontró ningún pedido con el remito '{remito}'.",
                    "pedido": None,
                    "bultos_escaneados": [],
                    "bultos_esperados": 0,
                }

            pedido = self._map_pedido(row)
            if pedido.estado == "anulado":
                return {
                    "ok": False,
                    "completado": False,
                    "duplicado": False,
                    "requiere_confirmacion_bultos": False,
                    "mensaje": f"El pedido #{pedido.nota_pedido} está ANULADO y no puede despacharse.",
                    "pedido": pedido,
                    "bultos_escaneados": [],
                    "bultos_esperados": pedido.bultos,
                }

            if pedido.estado_despacho != "armado":
                return {
                    "ok": False,
                    "completado": False,
                    "duplicado": True,
                    "requiere_confirmacion_bultos": False,
                    "mensaje": f"El pedido #{pedido.nota_pedido} ({pedido.cliente}) ya figura como '{pedido.estado_despacho.upper()}'.",
                    "pedido": pedido,
                    "bultos_escaneados": list(range(1, pedido.bultos + 1)),
                    "bultos_esperados": pedido.bultos,
                }

            esperados = max(1, int(pedido.bultos or 1))
            escaneados = [
                int(r["bulto_num"])
                for r in connection.execute(
                    "SELECT bulto_num FROM despacho_bultos_escaneados WHERE pedido_id = ? ORDER BY bulto_num ASC",
                    (pedido.id,),
                ).fetchall()
            ]

            # Caso 1: Escaneo plano sin número de bulto específico
            if bulto_num is None:
                if esperados > 1:
                    return {
                        "ok": True,
                        "completado": False,
                        "duplicado": False,
                        "requiere_confirmacion_bultos": True,
                        "mensaje": (
                            f"Remito #{pedido.nota_pedido} ({pedido.cliente}) tiene {esperados} bultos "
                            f"({len(escaneados)}/{esperados} verificados). Escanee el QR de cada bulto o despache manualmente."
                        ),
                        "pedido": pedido,
                        "bultos_escaneados": escaneados,
                        "bultos_esperados": esperados,
                    }
                bulto_num = 1

            # Caso 2: QR con BULTO:i/n (o pedido de 1 bulto)
            if total_qr is not None and total_qr != esperados:
                return {
                    "ok": False,
                    "completado": False,
                    "duplicado": False,
                    "requiere_confirmacion_bultos": False,
                    "mensaje": (
                        f"El rótulo indica {total_qr} bulto(s), pero el pedido #{pedido.nota_pedido} "
                        f"registra {esperados} bulto(s). Verifique los rótulos o despache manualmente."
                    ),
                    "pedido": pedido,
                    "bultos_escaneados": escaneados,
                    "bultos_esperados": esperados,
                }
            if bulto_num < 1 or bulto_num > esperados:
                return {
                    "ok": False,
                    "completado": False,
                    "duplicado": False,
                    "requiere_confirmacion_bultos": False,
                    "mensaje": (
                        f"Número de bulto inválido ({bulto_num}) para el remito #{pedido.nota_pedido} "
                        f"(esperados: 1..{esperados})."
                    ),
                    "pedido": pedido,
                    "bultos_escaneados": escaneados,
                    "bultos_esperados": esperados,
                }
            if bulto_num in escaneados:
                return {
                    "ok": False,
                    "completado": False,
                    "duplicado": True,
                    "requiere_confirmacion_bultos": False,
                    "mensaje": (
                        f"El bulto {bulto_num}/{esperados} del remito #{pedido.nota_pedido} ya fue escaneado "
                        f"({len(escaneados)}/{esperados} verificados)."
                    ),
                    "pedido": pedido,
                    "bultos_escaneados": escaneados,
                    "bultos_esperados": esperados,
                }

            connection.execute(
                f"""
                INSERT INTO despacho_bultos_escaneados (pedido_id, bulto_num, total_bultos, escaneado_por, escaneado_at)
                VALUES (?, ?, ?, ?, {ahora_sql})
                """,
                (pedido.id, bulto_num, esperados, usuario),
            )
            escaneados.append(bulto_num)
            escaneados.sort()

            if len(escaneados) >= esperados:
                connection.execute(
                    f"UPDATE pedidos SET estado_despacho = 'despachado', despachado_at = {ahora_sql}, "
                    "despachado_por = ?, entregado_at = '', entregado_por = '' WHERE id = ?",
                    (usuario, pedido.id),
                )
                fila_upd = connection.execute(
                    f"SELECT {_COLUMNAS_SELECT_PEDIDO} FROM pedidos WHERE id = ?",
                    (pedido.id,),
                ).fetchone()
                pedido_upd = self._map_pedido(fila_upd)
                auditoria_detalle = (
                    f"Remito {pedido.nota_pedido}: armado → despachado "
                    f"(QR verificado: {len(escaneados)}/{esperados} bulto(s))"
                )
            else:
                pedido_upd = pedido

        if auditoria_detalle:
            self._audit(
                usuario=usuario,
                accion="ESTADO_DESPACHO",
                detalle=auditoria_detalle,
            )
            return {
                "ok": True,
                "completado": True,
                "duplicado": False,
                "requiere_confirmacion_bultos": False,
                "mensaje": (
                    f"Remito #{pedido_upd.nota_pedido} ({pedido_upd.cliente}) → DESPACHADO "
                    f"({len(escaneados)}/{esperados} bulto(s) verificados)."
                ),
                "pedido": pedido_upd,
                "bultos_escaneados": escaneados,
                "bultos_esperados": esperados,
            }

        faltantes = esperados - len(escaneados)
        return {
            "ok": True,
            "completado": False,
            "duplicado": False,
            "requiere_confirmacion_bultos": False,
            "mensaje": (
                f"Bulto {bulto_num}/{esperados} verificado para remito #{pedido_upd.nota_pedido} "
                f"({pedido_upd.cliente}). Faltan {faltantes} bulto(s)."
            ),
            "pedido": pedido_upd,
            "bultos_escaneados": escaneados,
            "bultos_esperados": esperados,
        }

    def despachar_pedido_manual(
        self,
        pedido_id: int,
        cantidad_bultos: int,
        usuario: str = "Despachador",
    ) -> tuple[bool, str, Pedido | None]:
        """Marca manualmente un pedido `armado` como `despachado` validando la cantidad exacta de bultos."""
        try:
            cant = int(cantidad_bultos)
        except (TypeError, ValueError):
            return False, "Ingrese una cantidad válida de bultos.", None
        if cant < 1:
            return False, "La cantidad de bultos debe ser al menos 1.", None

        ahora_sql = "strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')"
        with self._connect() as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                f"SELECT {_COLUMNAS_SELECT_PEDIDO} FROM pedidos WHERE id = ?",
                (pedido_id,),
            ).fetchone()
            if row is None:
                return False, "No se encontró el pedido seleccionado.", None

            pedido = self._map_pedido(row)
            if pedido.estado == "anulado":
                return False, f"El pedido #{pedido.nota_pedido} está ANULADO y no puede despacharse.", pedido
            if pedido.estado_despacho != "armado":
                return (
                    False,
                    f"El pedido #{pedido.nota_pedido} ya figura como '{pedido.estado_despacho.upper()}'.",
                    pedido,
                )

            esperados = max(1, int(pedido.bultos or 1))
            if cant != esperados:
                return (
                    False,
                    f"Cantidad de bultos incorrecta: el remito #{pedido.nota_pedido} registra "
                    f"{esperados} bulto(s), pero se ingresaron {cant}.",
                    pedido,
                )

            for b_idx in range(1, esperados + 1):
                connection.execute(
                    f"""
                    INSERT OR IGNORE INTO despacho_bultos_escaneados
                        (pedido_id, bulto_num, total_bultos, escaneado_por, escaneado_at)
                    VALUES (?, ?, ?, ?, {ahora_sql})
                    """,
                    (pedido.id, b_idx, esperados, usuario),
                )
            connection.execute(
                f"UPDATE pedidos SET estado_despacho = 'despachado', despachado_at = {ahora_sql}, "
                "despachado_por = ?, entregado_at = '', entregado_por = '' WHERE id = ?",
                (usuario, pedido.id),
            )
            fila_upd = connection.execute(
                f"SELECT {_COLUMNAS_SELECT_PEDIDO} FROM pedidos WHERE id = ?",
                (pedido.id,),
            ).fetchone()
            pedido_upd = self._map_pedido(fila_upd)

        self._audit(
            usuario=usuario,
            accion="ESTADO_DESPACHO",
            detalle=(
                f"Remito {pedido_upd.nota_pedido}: armado → despachado "
                f"(manual, {esperados}/{esperados} bulto(s) confirmados)"
            ),
        )
        return (
            True,
            f"Remito #{pedido_upd.nota_pedido} ({pedido_upd.cliente}) → DESPACHADO "
            f"({esperados} bulto(s) confirmados).",
            pedido_upd,
        )
