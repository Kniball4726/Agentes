import sqlite3
import re
import pypdf

conn = sqlite3.connect('data/productos.sqlite3')
cur = conn.cursor()
db = {row[0]: row[1] for row in cur.execute("SELECT code, name FROM products").fetchall()}
conn.close()

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
            items.append((code, name))
    return items

ultra_items = []
for p in range(36, 42):
    ultra_items.extend(parse_brand_page(reader.pages[p].extract_text()))

vita_items = []
for p in range(44, 47):
    vita_items.extend(parse_brand_page(reader.pages[p].extract_text()))

print("Sample comparison of existing Ultra Tech items (PDF name vs DB name):")
matched_u = 0
for code, pdf_name in ultra_items:
    if code in db:
        matched_u += 1
        if matched_u <= 10:
            print(f"Code {code}:")
            print(f"  PDF: {pdf_name}")
            print(f"  DB : {db[code]}")

print("\nSample comparison of existing Vitatech items (PDF name vs DB name):")
matched_v = 0
for code, pdf_name in vita_items:
    if code in db:
        matched_v += 1
        if matched_v <= 10:
            print(f"Code {code}:")
            print(f"  PDF: {pdf_name}")
            print(f"  DB : {db[code]}")
