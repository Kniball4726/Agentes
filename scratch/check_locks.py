import sqlite3

conn = sqlite3.connect('data/usuarios.sqlite3')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

attempts = cur.execute("SELECT * FROM login_attempts").fetchall()
print("Login attempts / locks:", len(attempts))
for a in attempts:
    print(dict(a))

conn.close()
