import sys
sys.path.insert(0, '.')
from pathlib import Path
from src.auth import UserStore

store = UserStore(Path('data/usuarios.sqlite3'))

checks = [
    ('Admin', 'pasteur731'),
    ('Lucia', 'pasteur731'),
    ('Gregory', 'pasteur731'),
    ('Otto', 'pasteur731'),
    ('Picker', 'pasteur731'),
    ('Auditoria', 'master1713')
]

for u, p in checks:
    res = store.authenticate_detailed(u, p)
    print(f"User: {u:<10} | Status: {res.status} | Logged: {res.user is not None} | Error: '{res.error}'")
