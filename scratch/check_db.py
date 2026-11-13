import sqlite3

conn = sqlite3.connect('data/productos.sqlite3')
cur = conn.cursor()

tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", tables)

for t in tables:
    name = t[0]
    schema = cur.execute(f"SELECT sql FROM sqlite_master WHERE name='{name}'").fetchone()
    print(f"\n--- Table: {name} ---")
    print(schema[0] if schema else "None")
    count = cur.execute(f"SELECT count(*) FROM {name}").fetchone()
    print(f"Row count: {count[0]}")

conn.close()
