import sqlite3

conn = sqlite3.connect('data/productos.sqlite3')
cur = conn.cursor()

rows = cur.execute("SELECT id, product_code, display_name, display_order, template_row FROM product_catalog_rows ORDER BY display_order").fetchall()
print(f"Total rows in product_catalog_rows: {len(rows)}")
print("First 10:")
for r in rows[:10]:
    print(r)
print("\nLast 10:")
for r in rows[-10:]:
    print(r)

# Check if there are any products in `products` NOT in `product_catalog_rows`
missing_in_cat = cur.execute("SELECT code, name FROM products WHERE code NOT IN (SELECT product_code FROM product_catalog_rows)").fetchall()
print(f"\nProducts in products table but NOT in product_catalog_rows: {len(missing_in_cat)}")

conn.close()
