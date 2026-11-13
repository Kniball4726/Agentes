import sqlite3

conn = sqlite3.connect('data/usuarios.sqlite3')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

users = cur.execute("SELECT id, username, role, active, must_change_password, nombre, email, created_at, updated_at FROM users").fetchall()
for u in users:
    print(dict(u))

conn.close()
