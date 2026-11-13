import sqlite3
import re
import pypdf

# 1. Connect to DB and fetch all existing codes and names
conn = sqlite3.connect('data/productos.sqlite3')
cur = conn.cursor()
db_products = {row[0]: row[1] for row in cur.execute("SELECT code, name FROM products").fetchall()}
conn.close()

print(f"Total products in DB: {len(db_products)}")

# 2. Extract products from PDF
reader = pypdf.PdfReader("Documentacion/ListadoProductos2.pdf")

# Line regex: Code (alphanumeric or starting with A or numbers), Name, Stock (number with decimal comma)
# e.g., "119 3 EN 1 FAT BURNER SYSTEM 0,000"
# or "2735 CHRISTMAS PROTEIN BAR ... 87,000"
# or "28 BCAA 120 CAPS 28,000"
# Let's inspect each line in pages 37-42 and 45-47
def parse_brand_page(page_text):
    items = []
    lines = page_text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("ULTRA TECH") or line.startswith("VITATECH"):
            continue
        if "Código" in line and "Artículo" in line:
            continue
        if "Página" in line and "de 49" in line:
            continue
        # match code at start: usually alphanumeric e.g. 119, 2156, A709, 02461, etc.
        # stock at end: e.g. -426,000 or 0,000 or 122,000 or -96,00
        m = re.match(r"^([A-Za-z0-9_-]+)\s+(.+?)\s+(-?\d+[\.,]\d+)\s*$", line)
        if m:
            code = m.group(1).strip()
            name = m.group(2).strip()
            stock_str = m.group(3).strip()
            items.append((code, name, stock_str, line))
        else:
            # check if line has code and name but stuck stock
            m2 = re.match(r"^([A-Za-z0-9_-]+)\s+(.+?)(-?\d+[\.,]\d{2,3})\s*$", line)
            if m2:
                code = m2.group(1).strip()
                name = m2.group(2).strip()
                stock_str = m2.group(3).strip()
                items.append((code, name, stock_str, line))
            else:
                items.append((None, None, None, line))
    return items

ultra_items = []
for p in range(36, 42): # 37-42
    ultra_items.extend(parse_brand_page(reader.pages[p].extract_text()))

vita_items = []
for p in range(44, 47): # 45-47
    vita_items.extend(parse_brand_page(reader.pages[p].extract_text()))

print(f"\n--- ULTRA TECH (Pages 37-42) ---")
print(f"Total parsed lines: {len(ultra_items)}")
unparsed_ultra = [it for it in ultra_items if it[0] is None]
print(f"Unparsed lines ({len(unparsed_ultra)}):")
for u in unparsed_ultra:
    print(f"  {u[3]}")

print(f"\n--- VITATECH (Pages 45-47) ---")
print(f"Total parsed lines: {len(vita_items)}")
unparsed_vita = [it for it in vita_items if it[0] is None]
print(f"Unparsed lines ({len(unparsed_vita)}):")
for u in unparsed_vita:
    print(f"  {u[3]}")
