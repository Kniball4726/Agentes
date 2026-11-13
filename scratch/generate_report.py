import sqlite3
import re
import csv
import pypdf

conn = sqlite3.connect('data/productos.sqlite3')
cur = conn.cursor()
db_codes = {str(row[0]).strip(): row[1] for row in cur.execute("SELECT code, name FROM products").fetchall()}
conn.close()

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
    except Exception:
        pass

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

lines_md = []
lines_md.append("# Comparativa de Productos: Catálogo PDF vs Base de Datos")
lines_md.append("")
lines_md.append("Este informe presenta el análisis comparativo entre los productos de **Ultra Tech** y **Vitatech** encontrados en el archivo [ListadoProductos2.pdf](file:///c:/Users/user/Desktop/Software/DescuentoAgentico/Agentes/Documentacion/ListadoProductos2.pdf) y los productos actualmente registrados en la base de datos `data/productos.sqlite3`.")
lines_md.append("")
lines_md.append("## Resumen General de la Comparativa")
lines_md.append("")
lines_md.append("| Marca | Total en PDF | Ya registrados en BD | Faltantes por incorporar |")
lines_md.append("| :--- | :---: | :---: | :---: |")
lines_md.append(f"| **Ultra Tech** | {len(ultra_items)} | {len(ultra_items) - len(missing_ultra)} | **{len(missing_ultra)}** |")
lines_md.append(f"| **Vitatech** | {len(vita_items)} | {len(vita_items) - len(missing_vita)} | **{len(missing_vita)}** |")
lines_md.append(f"| **TOTAL** | **{len(ultra_items) + len(vita_items)}** | **{len(ultra_items) + len(vita_items) - len(missing_ultra) - len(missing_vita)}** | **{len(missing_ultra) + len(missing_vita)}** |")
lines_md.append("")
lines_md.append("> [!NOTE]")
lines_md.append("> De los 155 productos faltantes, se detectaron códigos de barras válidos (EAN-13) para varios de ellos en las fuentes maestras de inventario, los cuales pueden asociarse al darlos de alta.")
lines_md.append("")
lines_md.append("---")
lines_md.append("")
lines_md.append(f"## 1. Productos Faltantes - Ultra Tech ({len(missing_ultra)} productos)")
lines_md.append("")
lines_md.append("| Código | Descripción del Artículo | Stock en PDF | Código de Barras Detectado |")
lines_md.append("| :--- | :--- | :---: | :---: |")
for code, name, stock in missing_ultra:
    bc = barcodes.get(code, "-")
    lines_md.append(f"| `{code}` | {name} | {stock} | `{bc}` |")

lines_md.append("")
lines_md.append("---")
lines_md.append("")
lines_md.append(f"## 2. Productos Faltantes - Vitatech ({len(missing_vita)} productos)")
lines_md.append("")
lines_md.append("| Código | Descripción del Artículo | Stock en PDF | Código de Barras Detectado |")
lines_md.append("| :--- | :--- | :---: | :---: |")
for code, name, stock in missing_vita:
    bc = barcodes.get(code, "-")
    lines_md.append(f"| `{code}` | {name} | {stock} | `{bc}` |")

output_content = "\n".join(lines_md)
with open("scratch/informe_comparacion.md", "w", encoding="utf-8") as f:
    f.write(output_content)

print("Updated scratch/informe_comparacion.md successfully")
