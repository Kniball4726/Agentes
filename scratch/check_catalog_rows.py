import sqlite3

conn = sqlite3.connect('data/productos.sqlite3')
cur = conn.cursor()

rows = cur.execute("SELECT id, product_code, display_name, display_order, template_row FROM product_catalog_rows ORDER BY display_order LIMIT 20").fetchall()
print("First 20 catalog rows:")
for r in rows:
    print(r)

max_order = cur.execute("SELECT max(display_order), count(*) FROM product_catalog_rows").fetchone()
print("Max order, count:", max_order)

# Check if there is an Excel file like Productos.xlsx
conn.close()
