import sys
sys.path.insert(0, '.')
import sqlite3
from src.auth.password import verificar_clave

conn = sqlite3.connect('data/usuarios.sqlite3')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

users = cur.execute("SELECT id, username, role, password_hash FROM users").fetchall()

passwords = [
    "pasteur731", "master1713", "admin", "admin123", "admin1234", "Admin123", "Admin1234",
    "123456", "12345678", "123456789", "1234567890", "password", "Password123",
    "gregory", "Gregory", "gregory123", "Gregory123", "glrd4726ml", "glrd4726ml@gmail.com",
    "otto", "Otto", "otto123", "Otto123", "lucia", "Lucia", "lucia123", "Lucia123",
    "picker", "Picker", "picker123", "Picker123", "MercadoLibre", "mercadolibre",
    "auditoria", "Auditoria", "auditoria123", "Auditoria123", "StockAgent", "StockAgent2026",
    "UltraTech", "ultratech", "Vitatech", "vitatech", "Depósito", "deposito", "Deposito",
    "Pasteur731", "pasteur", "Pasteur", "1713"
]

for u in users:
    found = False
    for p in passwords:
        if verificar_clave(p, u['password_hash']):
            print(f"FOUND: User '{u['username']}' (role: {u['role']}) -> Password: '{p}'")
            found = True
            break
    if not found:
        print(f"NOT FOUND: User '{u['username']}'")

conn.close()
