import sys
sys.path.insert(0, '.')
import sqlite3
from src.auth.password import verificar_clave, hash_clave

conn = sqlite3.connect('data/usuarios.sqlite3')
row = conn.execute("SELECT id, username, password_hash FROM users WHERE username='Desarrollo'").fetchone()
print('Desarrollo hash in DB:', row[2])
print('verificar_clave(master1713, DB_hash):', verificar_clave('master1713', row[2]))
conn.close()
