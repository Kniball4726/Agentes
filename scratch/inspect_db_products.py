import sqlite3

conn = sqlite3.connect('data/productos.sqlite3')
cur = conn.cursor()

# Get some sample products
sample = cur.execute("SELECT code, name, stock, stock_minimo, stock_maximo, cod_barras, ubicacion FROM products LIMIT 15").fetchall()
print("Sample products:")
for s in sample:
    print(s)

print("\nTotal products:", cur.execute("SELECT count(*) FROM products").fetchone()[0])

# Check existing Ultra Tech and Vitatech products in DB
db_ultra = cur.execute("SELECT code, name, stock, cod_barras, ubicacion FROM products WHERE name LIKE '%ultra%' or name LIKE '%tech%'").fetchall()
print(f"\nProducts with 'ultra' or 'tech' in name ({len(db_ultra)}):")
for p in db_ultra[:10]:
    print(p)

db_vita = cur.execute("SELECT code, name, stock, cod_barras, ubicacion FROM products WHERE name LIKE '%vita%'").fetchall()
print(f"\nProducts with 'vita' in name ({len(db_vita)}):")
for p in db_vita[:10]:
    print(p)

conn.close()
