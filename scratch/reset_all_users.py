import sys
sys.path.insert(0, '.')
import sqlite3
from pathlib import Path
from src.auth.password import hash_clave
from src.auth import UserStore

conn = sqlite3.connect('data/usuarios.sqlite3')
cur = conn.cursor()

# Map of users and their passwords
user_passwords = {
    'Auditoria': 'master1713',
    'Admin': 'pasteur731',
    'Lucia': 'pasteur731',
    'Gregory': 'pasteur731',
    'Otto': 'pasteur731',
    'Picker': 'pasteur731'
}

print("Setting clean modern hashes for all users...")
for username, pwd in user_passwords.items():
    new_hash = hash_clave(pwd)
    cur.execute(
        "UPDATE users SET password_hash = ?, active = 1, must_change_password = 0, updated_at = CURRENT_TIMESTAMP WHERE username = ?",
        (new_hash, username)
    )
    print(f"  Updated '{username}' -> password: '{pwd}'")

# Clear login attempts
cur.execute("DELETE FROM login_attempts")
print("Cleared login_attempts table.")

conn.commit()
conn.close()

# Verify with UserStore
print("\nVerifying authentication with UserStore:")
store = UserStore(Path('data/usuarios.sqlite3'))
for username, pwd in user_passwords.items():
    u = store.authenticate(username, pwd)
    print(f"  User '{username}': {'AUTHENTICATED OK (role: ' + u.role + ')' if u else 'FAILED'}")
