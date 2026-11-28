import tempfile
from pathlib import Path

from src.auth import UserStore
from src.auth.models import DEFAULT_MASTER_PASSWORD
from src.auth.schema import ARCHIVO_CLAVE_INICIAL


def test_sin_env_se_genera_clave_aleatoria_y_no_la_historica(monkeypatch):
    monkeypatch.delenv("STOCKAGENT_MASTER_PASSWORD", raising=False)
    with tempfile.TemporaryDirectory() as tmp:
        store = UserStore(Path(tmp) / "users.sqlite3")

        assert store.authenticate("Auditoria", DEFAULT_MASTER_PASSWORD) is None

        archivo = Path(tmp) / ARCHIVO_CLAVE_INICIAL
        assert archivo.exists()
        clave = next(
            linea.split(":", 1)[1].strip()
            for linea in archivo.read_text(encoding="utf-8").splitlines()
            if linea.startswith("Clave temporal:")
        )
        assert clave != DEFAULT_MASTER_PASSWORD
        assert len(clave) >= 10

        user = store.authenticate("Auditoria", clave)
        assert user is not None and user.role == "master"
        assert user.must_change_password is True

        # Al cambiar la clave del master se borra automáticamente el archivo temporal
        store.change_password(user.id, clave, "NuevaClaveMaster2026!")
        assert not archivo.exists()
        refrescado = store.authenticate("Auditoria", "NuevaClaveMaster2026!")
        assert refrescado is not None and refrescado.must_change_password is False


def test_con_env_se_usa_esa_clave_y_no_se_crea_archivo(monkeypatch):
    monkeypatch.setenv("STOCKAGENT_MASTER_PASSWORD", "ClaveDelEntorno2026!")
    with tempfile.TemporaryDirectory() as tmp:
        store = UserStore(Path(tmp) / "users.sqlite3")
        assert store.authenticate("Auditoria", "ClaveDelEntorno2026!") is not None
        assert not (Path(tmp) / ARCHIVO_CLAVE_INICIAL).exists()
