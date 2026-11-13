import sqlite3

conn = sqlite3.connect('data/productos.sqlite3')
cur = conn.cursor()
print('Triggers:', cur.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger'").fetchall())
print('Indices:', cur.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index'").fetchall())
conn.close()
