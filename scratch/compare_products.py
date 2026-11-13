import sqlite3
import re
import pypdf

# 1. Connect to DB
conn = sqlite3.connect('data/productos.sqlite3')
cur = conn.cursor()
db_codes = {str(row[0]).strip(): row[1] for row in cur.execute("SELECT code, name FROM products").fetchall()}
conn.close()

reader = pypdf.PdfReader("Documentacion/ListadoProductos2.pdf")

def parse_brand_page(page_text):
    items = []
    lines = page_text.split("\n")
    for line in lines:
        line = line.strip()
        if not line or line.startswith("ULTRA TECH") or line.startswith("VITATECH"):
            continue
        if "Código" in line and "Artículo" in line:
            continue
        if "Página" in line and "de 49" in line:
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

print(f"Ultra Tech items in PDF: {len(ultra_items)}")
print(f"Vitatech items in PDF: {len(vita_items)}")

missing_ultra = []
existing_ultra = []
for code, name, stock in ultra_items:
    if code in db_codes:
        existing_ultra.append((code, name, stock, db_codes[code]))
    else:
        missing_ultra.append((code, name, stock))

missing_vita = []
existing_vita = []
for code, name, stock in vita_items:
    if code in db_codes:
        existing_vita.append((code, name, stock, db_codes[code]))
    else:
        missing_vita.append((code, name, stock))

print(f"\n--- ULTRA TECH ---")
print(f"Existing in DB: {len(existing_ultra)}")
print(f"Missing from DB: {len(missing_ultra)}")
print("\nMissing Ultra Tech samples (first 20):")
for code, name, stock in missing_ultra[:20]:
    print(f"  [{code}] '{name}' (Stock in PDF: {stock})")

print(f"\n--- VITATECH ---")
print(f"Existing in DB: {len(existing_vita)}")
print(f"Missing from DB: {len(missing_vita)}")
print("\nMissing Vitatech samples (first 20):")
for code, name, stock in missing_vita[:20]:
    print(f"  [{code}] '{name}' (Stock in PDF: {stock})")
