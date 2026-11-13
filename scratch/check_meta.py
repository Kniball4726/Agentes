import sqlite3

conn = sqlite3.connect('data/productos.sqlite3')
cur = conn.cursor()
print(cur.execute("SELECT key, value FROM product_catalog_metadata").fetchall())
conn.close()
