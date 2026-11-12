"""Script para actualizar códigos de barras en la base de datos de productos."""

from __future__ import annotations

import csv
from pathlib import Path
import sqlite3
import sys

# Asegurar raíz del proyecto en sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.product_store import ProductStore
from src.products.barcode_utils import normalizar_codigo_lector


def ejecutar_importacion(csv_path: Path, db_path: Path) -> dict:
    store = ProductStore(db_path)
    actualizados: list[tuple[str, str, str]] = []
    no_encontrados: list[tuple[str, str]] = []
    duplicados: set[str] = set()

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        idx_cod = 1
        idx_bar = 4
        if header:
            norm_header = [h.strip().lower() for h in header]
            for i, h in enumerate(norm_header):
                if h in ("codigo", "código", "product_code", "sku"):
                    idx_cod = i
                elif "barr" in h or h in ("barcode", "ean", "ean13"):
                    idx_bar = i

        for row in reader:
            if len(row) > max(idx_cod, idx_bar):
                cod = normalizar_codigo_lector(row[idx_cod])
                bar = normalizar_codigo_lector(row[idx_bar])
                if not cod or not bar:
                    continue
                if cod in duplicados:
                    continue
                duplicados.add(cod)

                prod = store.get_product(cod)
                if prod is not None:
                    db_code = str(prod["code"])
                    store.set_product_barcode(db_code, bar)
                    actualizados.append((db_code, str(prod["name"]), bar))
                else:
                    no_encontrados.append((cod, bar))

    store.invalidar_cache()

    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        total_con_bar = cur.execute(
            "SELECT count(code) FROM products WHERE cod_barras != ''"
        ).fetchone()[0]
        total_prod = cur.execute("SELECT count(code) FROM products").fetchone()[0]

    return {
        "actualizados": actualizados,
        "no_encontrados": no_encontrados,
        "total_con_bar": total_con_bar,
        "total_prod": total_prod,
    }


if __name__ == "__main__":
    db = Path("data/productos.sqlite3")
    csv_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/codigos_barras_import.csv")
    res = ejecutar_importacion(csv_file, db)
    print(f"Archivo procesado: {csv_file}")
    print(f"Productos actualizados/vinculados: {len(res['actualizados'])}")
    print(f"Productos sin coincidencia en el catálogo: {len(res['no_encontrados'])}")
    print(f"Total productos en catálogo con código de barras: {res['total_con_bar']}/{res['total_prod']}")
