import sys
sys.path.insert(0, '.')
import sqlite3
import re
import csv
import pypdf
import openpyxl
from copy import copy
from pathlib import Path

# Paths
db_path = Path("data/productos.sqlite3")
excel_path = Path("Descuentos/Productos.xlsx")
pdf_path = Path("Documentacion/ListadoProductos2.pdf")

# 1. Load Barcodes
barcodes = {}
for path in ["data/inventario_import.csv", "data/codigos_barras_import.csv"]:
    try:
        with open(path, mode="r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 2:
                    code = parts[1].strip()
                    m = re.search(r'\b(77\d{11})\b', line)
                    if code and m and code not in barcodes:
                        barcodes[code] = m.group(1)
    except Exception as e:
        print(f"Error reading {path}: {e}")

# 2. Parse PDF
reader = pypdf.PdfReader(str(pdf_path))

def parse_brand_page(page_text, brand_name):
    items = []
    lines = page_text.split("\n")
    for line in lines:
        line = line.strip()
        if not line or line.startswith("ULTRA TECH") or line.startswith("VITATECH") or "Código Artículo" in line or "de 49" in line:
            continue
        m = re.match(r"^([A-Za-z0-9_-]+)\s+(.+?)\s+(-?\d+[\.,]\d+)\s*$", line)
        if not m:
            m = re.match(r"^([A-Za-z0-9_-]+)\s+(.+?)(-?\d+[\.,]\d{2,3})\s*$", line)
        if m:
            code = m.group(1).strip()
            name = m.group(2).strip()
            items.append((code, name, brand_name))
    return items

pdf_products = []
for p in range(36, 42): # Ultra Tech: p. 37-42
    pdf_products.extend(parse_brand_page(reader.pages[p].extract_text(), "Ultra Tech"))

for p in range(44, 47): # Vitatech: p. 45-47
    pdf_products.extend(parse_brand_page(reader.pages[p].extract_text(), "Vitatech"))

print(f"Total extracted from PDF: {len(pdf_products)}")

# 3. Check existing in DB
conn = sqlite3.connect(str(db_path))
cur = conn.cursor()
existing_codes = {str(row[0]).strip() for row in cur.execute("SELECT code FROM products").fetchall()}

# Filter missing
to_add = []
for code, name, brand in pdf_products:
    if code not in existing_codes and code not in [x[0] for x in to_add]:
        to_add.append((code, name, brand))

print(f"Products to add: {len(to_add)}")

# Get current max display_order in product_catalog_rows
max_order = cur.execute("SELECT coalesce(max(display_order), -1) FROM product_catalog_rows").fetchone()[0]
print(f"Current max display_order: {max_order}")

# 4. Open Excel to get next row and prepare updates
wb = openpyxl.load_workbook(str(excel_path))
ws = wb["Hoja1"]

# Find the last row with data in Excel
last_excel_row = 4
for r in range(4, ws.max_row + 1):
    if ws.cell(r, 1).value is not None and str(ws.cell(r, 2).value or "").strip():
        last_excel_row = max(last_excel_row, r)

print(f"Last populated Excel row: {last_excel_row}")

# Style reference from last_excel_row
ref_row = last_excel_row

start_excel_row = last_excel_row + 1
start_display_order = max_order + 1

excel_updates = []
db_product_rows = []
db_catalog_rows = []

for idx, (code, name, brand) in enumerate(to_add):
    curr_excel_row = start_excel_row + idx
    curr_order = start_display_order + idx
    barcode = barcodes.get(code, "")

    # SQLite products table: code, name, stock, stock_minimo, stock_maximo, active, stock_fisico, cod_barras, ubicacion
    db_product_rows.append((code, name, 0, 5, 100, 1, barcode, ""))
    
    # SQLite product_catalog_rows: product_code, display_name, display_order, template_row
    db_catalog_rows.append((code, name, curr_order, curr_excel_row))

    # Excel cell values
    code_val = int(code) if code.isdigit() else code
    excel_updates.append((curr_excel_row, code_val, name, 0, None, 0))

# 5. Apply Excel Updates
print(f"Writing {len(excel_updates)} rows to Excel...")
for row_idx, code_val, name_val, st_ini, desc, st_fin in excel_updates:
    # Set values
    ws.cell(row_idx, 1, code_val)
    ws.cell(row_idx, 2, name_val)
    ws.cell(row_idx, 3, st_ini)
    ws.cell(row_idx, 4, desc)
    ws.cell(row_idx, 5, st_fin)

    # Copy styling from ref_row
    for col in range(1, 6):
        src_cell = ws.cell(ref_row, col)
        dst_cell = ws.cell(row_idx, col)
        if src_cell.has_style:
            dst_cell.font = copy(src_cell.font)
            dst_cell.border = copy(src_cell.border)
            dst_cell.fill = copy(src_cell.fill)
            dst_cell.number_format = copy(src_cell.number_format)
            dst_cell.alignment = copy(src_cell.alignment)

# Save Excel
wb.save(str(excel_path))
wb.close()
print("Excel updated and saved successfully.")

# 6. Apply SQLite Updates in transaction
print(f"Inserting into SQLite products table...")
cur.executemany(
    """
    INSERT INTO products (code, name, stock, stock_minimo, stock_maximo, active, cod_barras, ubicacion)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
    db_product_rows
)

print(f"Inserting into SQLite product_catalog_rows table...")
cur.executemany(
    """
    INSERT INTO product_catalog_rows (product_code, display_name, display_order, template_row)
    VALUES (?, ?, ?, ?)
    """,
    db_catalog_rows
)

conn.commit()
conn.close()
print("SQLite database committed successfully.")

print("\n--- Summary of Operation ---")
print(f"Added products: {len(to_add)}")
print(f"New total products in DB: {len(existing_codes) + len(to_add)}")
print(f"New last Excel row: {start_excel_row + len(to_add) - 1}")
print("Done!")
