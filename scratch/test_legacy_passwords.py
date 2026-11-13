import sys
sys.path.insert(0, '.')
import sqlite3
import hashlib
import hmac

def verificar_legacy(password: str, stored_hash: str) -> bool:
    try:
        salt_text, digest_text = stored_hash.split(":", maxsplit=1)
        salt = bytes.fromhex(salt_text)
        expected = bytes.fromhex(digest_text)
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        600_000,
    )
    return hmac.compare_digest(actual, expected)

conn = sqlite3.connect('data/usuarios.sqlite3')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

users = cur.execute("SELECT id, username, role, active, password_hash FROM users").fetchall()

passwords_to_try = [
    "master1713", "admin", "admin123", "administrador", "operador", "picker", "consulta",
    "123456", "12345678", "123456789", "password", "StockAgent", "StockAgent2026",
    "gregory", "otto", "lucia", "auditoria", "Auditoria", "Gregory", "Otto", "Admin", "Lucia", "Picker"
]

for u in users:
    print(f"\nUser: {u['username']} (Role: {u['role']})")
    matched = None
    for p in passwords_to_try:
        if ":" in u['password_hash']:
            if verificar_legacy(p, u['password_hash']):
                matched = p
                break
        elif "$" in u['password_hash']:
            from src.auth.password import verificar_clave
            if verificar_clave(p, u['password_hash']):
                matched = p
                break
    if matched:
        print(f"  -> PASSWORD MATCH: '{matched}'")
    else:
        print("  -> Could not guess password from common list.")

conn.close()
