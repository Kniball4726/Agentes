"""Pruebas de consistencia para lockfile multiplataforma, linting y pipeline CI."""

from __future__ import annotations

import importlib
import re
import tomllib
from pathlib import Path

from src.products.barcode_utils import normalizar_codigo_lector

ROOT_DIR = Path(__file__).resolve().parent.parent
_RE_PKG_REQ = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?")


def _extraer_nombre_paquete(linea: str) -> str:
    match = _RE_PKG_REQ.match(linea.strip())
    assert match is not None, f"Línea de dependencia inválida: {linea!r}"
    return match.group(1).lower().replace("_", "-")


def test_requirements_lock_cubre_requirements_y_marcadores_plataforma() -> None:
    req_txt = ROOT_DIR / "requirements.txt"
    lock_txt = ROOT_DIR / "requirements.lock"
    assert req_txt.is_file()
    assert lock_txt.is_file()
    gitignore_lines = {line.strip() for line in (ROOT_DIR / ".gitignore").read_text(encoding="utf-8").splitlines()}
    assert "!requirements.lock" in gitignore_lines

    principales = {
        _extraer_nombre_paquete(line)
        for line in req_txt.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }

    lock_lines = [
        line.strip()
        for line in lock_txt.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    bloqueados: dict[str, list[str]] = {}
    for line in lock_lines:
        assert "==" in line, f"Dependencia sin versión fijada con == en requirements.lock: {line}"
        pkg = _extraer_nombre_paquete(line)
        bloqueados.setdefault(pkg, []).append(line)

    faltantes = principales - set(bloqueados)
    assert not faltantes, f"Faltan paquetes de requirements.txt en requirements.lock: {sorted(faltantes)}"

    for pkg_ci in ("flet", "pytest", "pytest-asyncio", "anyio", "uvicorn", "fastapi"):
        assert pkg_ci in bloqueados

    assert any(line.startswith("flet[all]==1.0.5") for line in bloqueados["flet"])
    for win_only in ("pefile", "pywin32-ctypes"):
        assert all('sys_platform == "win32"' in line for line in bloqueados[win_only])
    assert all('sys_platform != "win32"' in line for line in bloqueados["uvloop"])


def test_pyproject_y_ci_configuran_checks_fase_1() -> None:
    pyproject = tomllib.loads((ROOT_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    ruff_lint = pyproject.get("tool", {}).get("ruff", {}).get("lint", {})
    seleccion = set(ruff_lint.get("select", []))
    assert seleccion >= {"E9", "F82", "F811", "B023", "PLR0124"}
    assert seleccion >= {"E", "W", "F", "B", "S", "UP", "SIM"}
    ignorados_globales = set(ruff_lint.get("ignore", []))
    assert "S110" not in ignorados_globales
    assert "S112" not in ignorados_globales

    ci_text = (ROOT_DIR / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "requirements.lock" in ci_text
    assert "ruff check src tests" in ci_text
    assert "tsc --noEmit -p tsconfig.json" in ci_text
    assert "tsc --noEmit -p tsconfig.sw.json" in ci_text
    assert "flutter analyze" in ci_text
    assert "workflow_call:" in ci_text
    assert "--cov=src" in ci_text
    assert "pip-audit" in ci_text

    cd_path = ROOT_DIR / ".github" / "workflows" / "cd.yml"
    assert cd_path.is_file()
    cd_text = cd_path.read_text(encoding="utf-8")
    assert "uses: ./.github/workflows/ci.yml" in cd_text
    assert "needs: [quality-gate]" in cd_text
    assert "ANDROID_KEYSTORE_BASE64" in cd_text

    dependabot_path = ROOT_DIR / ".github" / "dependabot.yml"
    assert dependabot_path.is_file()
    dep_text = dependabot_path.read_text(encoding="utf-8")
    assert 'package-ecosystem: "pip"' in dep_text
    assert 'package-ecosystem: "pub"' in dep_text
    assert 'package-ecosystem: "github-actions"' in dep_text


def test_normalizar_codigo_lector_nan_inf_y_exportaciones_dialogos() -> None:
    assert normalizar_codigo_lector(float("nan")) == ""
    assert normalizar_codigo_lector(float("inf")) == ""
    assert normalizar_codigo_lector(float("-inf")) == ""

    for mod_name in (
        "src.ui.dialogs.dlg_movimientos_rapidos",
        "src.ui.dialogs.dlg_stock_fisico",
        "src.ui.dialogs.dlg_ubicaciones_lotes",
    ):
        mod = importlib.import_module(mod_name)
        for symbol in getattr(mod, "__all__", []):
            assert hasattr(mod, symbol), f"{mod_name}.__all__ exporta símbolo inexistente: {symbol}"


def test_mobile_flutter_tests_y_analysis_options_habilitados_para_ci() -> None:
    mobile_dir = ROOT_DIR / "stockagent_mobile"
    analysis_opts = mobile_dir / "analysis_options.yaml"
    assert analysis_opts.is_file()
    assert "package:flutter_lints/flutter.yaml" in analysis_opts.read_text(encoding="utf-8")

    test_files = list((mobile_dir / "test").rglob("*_test.dart"))
    assert test_files, "El job mobile-check de CI requiere al menos un archivo *_test.dart."
    combined_tests = "\n".join(p.read_text(encoding="utf-8") for p in test_files)
    for model_sym in ("ProductItem", "ProductLocationsSummary", "StockLot", "StockReservation", "AuthUser"):
        assert model_sym in combined_tests

    dart_files = list((mobile_dir / "lib").rglob("*.dart")) + test_files
    assert dart_files
    for dart_file in dart_files:
        txt = dart_file.read_text(encoding="utf-8")
        assert txt.count("(") == txt.count(")"), f"Paréntesis desbalanceados en {dart_file}"
        assert txt.count("{") == txt.count("}"), f"Llaves desbalanceadas en {dart_file}"
        assert txt.count("[") == txt.count("]"), f"Corchetes desbalanceados en {dart_file}"


def test_version_unica_sincronizada_entre_backend_pyproject_y_mobile() -> None:
    from src.version import APP_VERSION, obtener_version_completa

    pyproject = tomllib.loads((ROOT_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject.get("project", {}).get("version") == APP_VERSION

    pubspec_txt = (ROOT_DIR / "stockagent_mobile" / "pubspec.yaml").read_text(encoding="utf-8")
    assert f"version: {obtener_version_completa()}" in pubspec_txt

    cd_txt = (ROOT_DIR / ".github" / "workflows" / "cd.yml").read_text(encoding="utf-8")
    assert "StockAgent.exe --version" in cd_txt
