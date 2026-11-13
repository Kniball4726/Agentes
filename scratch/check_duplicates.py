import sqlite3
import re
import pypdf
from collections import Counter

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

print("Ultra tech total items:", len(ultra_items))
ultra_codes = [x[0] for x in ultra_items]
c_ultra = Counter(ultra_codes)
dup_ultra = [k for k, v in c_ultra.items() if v > 1]
print("Ultra Tech duplicate codes in section:", [(k, c_ultra[k]) for k in dup_ultra])

print("\nVitatech total items:", len(vita_items))
vita_codes = [x[0] for x in vita_items]
c_vita = Counter(vita_codes)
dup_vita = [k for k, v in c_vita.items() if v > 1]
print("Vitatech duplicate codes in section:", [(k, c_vita[k]) for k in dup_vita])

# Check overlap between Ultra Tech and Vitatech
overlap = set(ultra_codes).intersection(set(vita_codes))
print("Overlap between Ultra and Vita codes:", overlap)
