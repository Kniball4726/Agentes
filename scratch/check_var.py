import sys
sys.path.insert(0, '.')
import sqlite3
import hashlib
import hmac

def check_legacy(p, h):
    s_t, d_t = h.split(":", 1)
    s = bytes.fromhex(s_t)
    exp = bytes.fromhex(d_t)
    act = hashlib.pbkdf2_hmac("sha256", p.encode("utf-8"), s, 600_000)
    return hmac.compare_digest(act, exp)

conn = sqlite3.connect('data/usuarios.sqlite3')
rows = conn.execute("SELECT username, password_hash FROM users WHERE username IN ('Admin', 'Gregory', 'Picker', 'Auditoria')").fetchall()

variations = [
    "Pasteur731", "pasteur731", "PASTEUR731", "Pasteur731*", "Pasteur731!", "pasteur731!",
    "pasteur", "Pasteur", "123456", "admin1234", "Admin1234", "Admin1234!", "admin", "Admin",
    "gregory", "Gregory", "gregory123", "gregory2026", "gregory731", "glrd4726ml",
    "master1713", "master1713!", "Auditoria1713", "auditoria1713", "picker123", "picker2026"
]

for u, h in rows:
    print(f"Testing {u}...")
    for v in variations:
        if check_legacy(v, h):
            print(f"  >>> MATCH FOR {u}: '{v}'")
            break
conn.close()
