"""Módulo Conector Oficial con la API REST de Mercado Libre para StockAgent.

Permite:
1. Configurar credenciales OAuth (App ID, Client Secret, Access Token, Refresh Token).
2. Probar la conexión en tiempo real con la API de Mercado Libre (`/users/me`).
3. Renovar automáticamente el Access Token vía OAuth cuando expire.
4. Consultar y sincronizar desatendidamente órdenes recientes pagadas (`/orders/search`).
5. Emparejar artículos por SKU del vendedor (100% de precisión) o por título/descripción (fuzzy matching).
6. Descontar stock de forma atómica en SQLite y generar el comprobante .docx oficial en disco.
"""

import hashlib
from pathlib import Path
from typing import Any

from docx import Document

from ..core.environment import get_data_dir
from ..core.security_utils import resolver_ruta_confinada, sanitizar_componente_archivo
from ..parsers.mercado_libre_parser import _buscar_codigo
from ..parsers.remito_parser import normalizar_codigo
from ..paths import application_root
from ..stock.models import RegistroDescuento
from .mercado_libre_auth import (
    API_BASE_URL,
    CONFIG_ML_PATH_DEFAULT,
    _CAMPOS_SECRETOS_ML,
    _obtener_ruta_config_ml,
    cargar_config_mercadolibre,
    consultar_ordenes_ml,
    guardar_config_mercadolibre,
    renovar_token_ml,
    verificar_credenciales_ml,
)

__all__ = [
    "API_BASE_URL",
    "CONFIG_ML_PATH_DEFAULT",
    "cargar_config_mercadolibre",
    "consultar_ordenes_ml",
    "descontar_orden_ml_api",
    "generar_documento_orden_ml_docx",
    "guardar_config_mercadolibre",
    "mapear_orden_ml_a_items",
    "renovar_token_ml",
    "verificar_credenciales_ml",
]


def mapear_orden_ml_a_items(
    orden: dict[str, Any],
    catalogo: dict[str, tuple[int, str, int]],
) -> dict[str, Any]:
    """Empareja los ítems de una orden de Mercado Libre con el catálogo de StockAgent.
    
    Estrategia de matching:
    1. SKU exacto del vendedor (seller_sku o seller_custom_field) contra el código de catálogo.
    2. Si no hay SKU o no coincide, fuzzy matching semántico del título contra los nombres del catálogo.
    """
    orden_id = str(orden.get("id", ""))
    ref_pedido = f"ML-{orden_id}"
    buyer = orden.get("buyer") or {}
    nombre_comprador = (
        f"{buyer.get('first_name', '')} {buyer.get('last_name', '')}".strip()
        or str(buyer.get("nickname", "Comprador Mercado Libre"))
    )
    fecha_creacion = str(orden.get("date_created", ""))[:19].replace("T", " ")
    shipping = orden.get("shipping") or {}
    shipping_id = str(shipping.get("id", ""))

    descripciones_catalogo: dict[str, list[str]] = {}
    for cod, data in catalogo.items():
        nom = data[1]
        if nom:
            descripciones_catalogo.setdefault(cod, []).append(nom)

    items_coincidentes: list[dict[str, Any]] = []
    items_no_coincidentes: list[dict[str, Any]] = []

    for item_elem in orden.get("order_items", []):
        it_obj = item_elem.get("item") or {}
        sku_candidato = normalizar_codigo(
            str(it_obj.get("seller_sku") or it_obj.get("seller_custom_field") or "").strip()
        )
        titulo = str(it_obj.get("title", "")).strip()
        cantidad = int(item_elem.get("quantity", 1))
        precio_unitario = float(item_elem.get("unit_price", 0.0))

        codigo_encontrado: str | None = None
        metodo = ""

        # 1. Matching por SKU
        if sku_candidato and sku_candidato in catalogo:
            codigo_encontrado = sku_candidato
            metodo = "SKU"
        else:
            # 2. Matching fuzzy por título
            codigo_fuzzy, _ = _buscar_codigo(titulo, descripciones_catalogo)
            if codigo_fuzzy and codigo_fuzzy in catalogo:
                codigo_encontrado = codigo_fuzzy
                metodo = "Fuzzy Título"

        if codigo_encontrado:
            fila, nombre_prod, stock_act = catalogo[codigo_encontrado]
            items_coincidentes.append({
                "codigo": codigo_encontrado,
                "nombre": nombre_prod,
                "cantidad": cantidad,
                "stock_actual": stock_act,
                "precio": precio_unitario,
                "fila": fila,
                "metodo": metodo,
                "stock_suficiente": stock_act >= cantidad,
            })
        else:
            items_no_coincidentes.append({
                "titulo": titulo,
                "sku": sku_candidato,
                "cantidad": cantidad,
                "precio": precio_unitario,
            })

    total_unidades = sum(it["cantidad"] for it in items_coincidentes)
    total_importe = sum(it["cantidad"] * it["precio"] for it in items_coincidentes)
    todos_coinciden = len(items_no_coincidentes) == 0 and len(items_coincidentes) > 0
    stock_suficiente = all(it["stock_suficiente"] for it in items_coincidentes)

    return {
        "orden_id": orden_id,
        "ref_pedido": ref_pedido,
        "cliente": nombre_comprador,
        "fecha": fecha_creacion,
        "shipping_id": shipping_id,
        "items_coincidentes": items_coincidentes,
        "items_no_coincidentes": items_no_coincidentes,
        "total_unidades": total_unidades,
        "total_importe": total_importe,
        "todos_coinciden": todos_coinciden,
        "stock_suficiente": stock_suficiente,
    }


def generar_documento_orden_ml_docx(orden_procesada: dict[str, Any], ruta_salida: Path) -> Path:
    """Genera un archivo .docx oficial para resguardar la orden de Mercado Libre en pedidos_archivos."""
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    doc.add_heading(f"Mercado Libre · Orden {orden_procesada['orden_id']}", level=1)

    p_meta = doc.add_paragraph()
    p_meta.add_run("Cliente / Comprador: ").bold = True
    p_meta.add_run(f"{orden_procesada.get('cliente', 'Mercado Libre')}\n")
    p_meta.add_run("Fecha: ").bold = True
    p_meta.add_run(f"{orden_procesada.get('fecha', '')}\n")
    p_meta.add_run("Identificador de Envío: ").bold = True
    p_meta.add_run(f"{orden_procesada.get('shipping_id', 'N/A')}\n")
    p_meta.add_run("Total de Artículos: ").bold = True
    p_meta.add_run(f"{orden_procesada.get('total_unidades', 0)} unidades\n")

    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Código (SKU)"
    hdr_cells[1].text = "Descripción de Producto"
    hdr_cells[2].text = "Cant."
    hdr_cells[3].text = "Precio Unitario"

    for it in orden_procesada.get("items_coincidentes", []):
        row_cells = table.add_row().cells
        row_cells[0].text = str(it.get("codigo", ""))
        row_cells[1].text = str(it.get("nombre", ""))
        row_cells[2].text = str(it.get("cantidad", 0))
        row_cells[3].text = f"${it.get('precio', 0.0):,.2f}"

    doc.save(str(ruta_salida))
    return ruta_salida


def descontar_orden_ml_api(
    orden_procesada: dict[str, Any],
    stock_manager: Any,
    order_store: Any,
    armador: str = "Operario",
    root_path: Path | None = None,
) -> tuple[bool, str]:
    """Aplica el descuento de stock atómico de una orden de Mercado Libre y la registra en OrderStore."""
    ref_pedido = orden_procesada["ref_pedido"]
    orden_id = orden_procesada["orden_id"]

    # Validar si ya fue procesada
    if order_store.existe_nota_pedido(ref_pedido):
        return False, f"La orden {ref_pedido} ya fue descontada previamente en el sistema."

    hash_orden = hashlib.sha256(f"ML_API_ORDER_{orden_id}".encode()).hexdigest()
    dup = order_store.buscar_pedido_por_hash(hash_orden)
    if dup:
        return False, f"La orden {ref_pedido} ya fue procesada anteriormente ({dup.created_at[:16]})."

    items = orden_procesada.get("items_coincidentes", [])
    if not items:
        return False, f"La orden {ref_pedido} no tiene ítems válidos para descontar."

    # Generar el archivo .docx de respaldo en el directorio de datos activo
    carpeta_pedidos = (Path(root_path) / "data" / "pedidos_archivos") if root_path is not None else (get_data_dir() / "pedidos_archivos")
    orden_id_seguro = sanitizar_componente_archivo(str(orden_id), fallback="orden")
    nombre_doc = f"ML_API_{orden_id_seguro}.docx"
    ruta_doc = resolver_ruta_confinada(carpeta_pedidos, nombre_doc)
    generar_documento_orden_ml_docx(orden_procesada, ruta_doc)

    # Preparar descuentos para StockManager
    descuentos: list[RegistroDescuento] = []
    for it in items:
        cod = it["codigo"]
        nom = it["nombre"]
        cant = it["cantidad"]
        stk_ant = it["stock_actual"]
        stk_nuevo = int(stk_ant - cant)
        fila = it.get("fila", 0)

        descuentos.append(
            RegistroDescuento(
                codigo=cod,
                nombre_producto=nom,
                fila_excel=fila,
                stock_anterior=stk_ant,
                cantidad_descontada=cant,
                stock_nuevo=stk_nuevo,
                es_nuevo_agregado=False,
            )
        )

    # Actualizar stock base atómico
    stock_manager.actualizar_stock_base(
        descuentos=descuentos,
        sincronizar_excel=True,
        nombre_archivo=nombre_doc,
        usuario=armador,
    )

    total_desc = orden_procesada["total_unidades"]
    resumen_items = f"{len(items)} productos ({total_desc} un.)"
    items_descontados = [(it["codigo"], it["nombre"], it["cantidad"]) for it in items]

    # Registrar en OrderStore
    order_store.registrar_pedido(
        nota_pedido=ref_pedido,
        numero_pedido=ref_pedido,
        cliente=orden_procesada.get("cliente", "Mercado Libre"),
        bultos=1,
        logistica="Transporte",
        armador=armador,
        tipo_archivo="docx",
        nombre_archivo=nombre_doc,
        agregado=False,
        articulos_descontados=total_desc,
        resumen_items=resumen_items,
        archivo_descuento="",
        items=items_descontados,
        archivo_hash=hash_orden,
    )

    return True, f"Orden {ref_pedido} descontada con éxito ({total_desc} unidades)."
