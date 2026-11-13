import sys
sys.path.insert(0, '.')
import sqlite3
from src.auth.password import verificar_clave

conn = sqlite3.connect('data/usuarios.sqlite3')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

users = cur.execute("SELECT id, username, role, active, must_change_password, nombre, email, password_hash FROM users").fetchall()

print(f"Total users in DB: {len(users)}")
for u in users:
    print(f"ID: {u['id']}, User: {u['username']}, Role: {u['role']}, Active: {u['active']}, MustChangePwd: {u['must_change_password']}")
    # Test common default passwords if any
    common_passwords = ["master1713", "admin", "admin123", "operador", "123456", "12345678", "password", "StockAgent2026", "stockagent"]
    matched = None
    for pwd in common_passwords:
        if verificar_clave(pwd, u['password_hash']):
            matched = pwd
            break
    if matched:
        print(f"   -> Password matches default: '{matched}'")
    else:
        print(f"   -> Hash starts with: {u['password_hash'][:25]}...")

conn.close()
