import sqlite3

conn = sqlite3.connect('data/usuarios.sqlite3')
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT id, username, role, active, must_change_password FROM users").fetchall()
for r in rows:
    print(dict(r))
conn.close()
