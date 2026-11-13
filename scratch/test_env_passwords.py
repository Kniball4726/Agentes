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
    except Exception:
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

users = cur.execute("SELECT id, username, role, password_hash FROM users").fetchall()

passwords = [
    "admin1234", "admin123", "Admin1234", "Admin1234!", "pasteur731", "master1713",
    "gregory123", "Gregory123", "gregory2026", "lucia123", "Lucia123", "lucia2026",
    "otto123", "Otto123", "picker123", "Picker123", "picker2026", "operador123",
    "operador2026", "stockagent", "StockAgent", "StockAgent2026", "StockAgent2026!"
]

for u in users:
    if ":" in u['password_hash']:
        for p in passwords:
            if verificar_legacy(p, u['password_hash']):
                print(f"MATCH! User '{u['username']}' -> Password: '{p}'")
                break

conn.close()
