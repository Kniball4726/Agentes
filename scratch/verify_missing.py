import sqlite3
import re
import csv
import pypdf

# 1. DB products
conn = sqlite3.connect('data/productos.sqlite3')
cur = conn.cursor()
db_codes = {str(row[0]).strip(): row[1] for row in cur.execute("SELECT code, name FROM products").fetchall()}
conn.close()

# 2. Barcodes from CSV
barcodes = {}
for path in ["data/inventario_import.csv", "data/codigos_barras_import.csv"]:
    try:
        with open(path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                c = row.get("Codigo", "").strip()
                b = row.get("Cod_Barras", "").strip()
                if c and b and c not in barcodes:
                    barcodes[c] = b
    except Exception:
        pass

# 3. PDF parsing
reader = pypdf.PdfReader("Documentacion/ListadoProductos2.pdf")

def parse_brand_page(page_text):
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
            stock_str = m.group(3).strip().replace(".", "").replace(",", ".")
            try:
                stock_val = int(float(stock_str))
            except:
                stock_val = 0
            items.append((code, name, stock_val))
    return items

ultra_items = []
for p in range(36, 42):
    ultra_items.extend(parse_brand_page(reader.pages[p].extract_text()))

vita_items = []
for p in range(44, 47):
    vita_items.extend(parse_brand_page(reader.pages[p].extract_text()))

missing_ultra = [it for it in ultra_items if it[0] not in db_codes]
missing_vita = [it for it in vita_items if it[0] not in db_codes]

print(f"Missing Ultra Tech: {len(missing_ultra)}")
print(f"Missing Vitatech: {len(missing_vita)}")
print(f"Total Missing: {len(missing_ultra) + len(missing_vita)}")

# Let's verify if any code has whitespace issues
for c, n, s in missing_ultra + missing_vita:
    assert c == c.strip()
    assert n == n.strip()
