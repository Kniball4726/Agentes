import pytest


@pytest.fixture(autouse=True)
def _clave_master_de_pruebas(monkeypatch):
    """El sistema ya no tiene clave master por defecto: las pruebas definen una explícita y reproducible."""
    monkeypatch.setenv("STOCKAGENT_MASTER_PASSWORD", "master1713")
    monkeypatch.delenv("STOCKAGENT_MASTER_USER", raising=False)
