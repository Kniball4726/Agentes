"""Pruebas unitarias e integración Git para el módulo de auto-actualización."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from src import auto_updater


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )


def _crear_repo_con_remoto(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Crea remoto bare + clon de servidor + clon de casa con commit inicial en master."""
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "--bare", str(remote))

    casa = tmp_path / "casa"
    _git(tmp_path, "clone", str(remote), str(casa))
    _git(casa, "config", "user.email", "casa@example.com")
    _git(casa, "config", "user.name", "Casa")
    _git(casa, "checkout", "-b", "master")
    (casa / "app.py").write_text("VERSION = 1\n", encoding="utf-8")
    (casa / "requirements.lock").write_text("pytest==9.2.0\n", encoding="utf-8")
    _git(casa, "add", ".")
    _git(casa, "commit", "-m", "Commit inicial")
    _git(casa, "push", "-u", "origin", "master")
    _git(remote, "symbolic-ref", "HEAD", "refs/heads/master")

    servidor = tmp_path / "servidor"
    _git(tmp_path, "clone", "-b", "master", str(remote), str(servidor))
    _git(servidor, "config", "user.email", "srv@example.com")
    _git(servidor, "config", "user.name", "Servidor")
    return remote, casa, servidor


def test_ventana_horaria_diurna_nocturna_e_invalida() -> None:
    assert auto_updater.esta_en_ventana_horaria("", datetime(2026, 11, 27, 14, 0)) is True
    assert auto_updater.esta_en_ventana_horaria("08:00-18:00", datetime(2026, 11, 27, 12, 30)) is True
    assert auto_updater.esta_en_ventana_horaria("08:00-18:00", datetime(2026, 11, 27, 19, 0)) is False

    # Cruce de medianoche
    assert auto_updater.esta_en_ventana_horaria("20:00-07:00", datetime(2026, 11, 27, 23, 15)) is True
    assert auto_updater.esta_en_ventana_horaria("20:00-07:00", datetime(2026, 11, 28, 5, 45)) is True
    assert auto_updater.esta_en_ventana_horaria("20:00-07:00", datetime(2026, 11, 28, 11, 0)) is False

    # Formato inválido no bloquea operación
    assert auto_updater.esta_en_ventana_horaria("invalido", datetime(2026, 11, 28, 11, 0)) is True


def test_flags_reinicio_y_puerto() -> None:
    flags = auto_updater.construir_flags_reinicio(
        ["--port", "9000", "--http", "--ocultar-consola", "--reiniciar"]
    )
    assert "--port" in flags and "9000" in flags
    assert "--http" in flags
    assert "--ocultar-consola" in flags
    assert "--no-browser" in flags
    assert "--no-auto-update" in flags
    assert "--reiniciar" not in flags

    with patch.dict(os.environ, {"STOCKAGENT_PORT": "8660"}, clear=False):
        assert auto_updater.extraer_puerto_de_argv([]) == 8660
        assert auto_updater.extraer_puerto_de_argv(["--port", "8770"]) == 8770


def test_git_fetch_y_pull_real_entre_casa_y_servidor(tmp_path: Path) -> None:
    _remote, casa, servidor = _crear_repo_con_remoto(tmp_path)
    cfg = auto_updater.AutoUpdateConfig(
        habilitado_inicio=True,
        habilitado_watcher=True,
        rama="master",
        remoto="origin",
        instalar_dependencias=True,
    )

    # Sin cambios aún
    check_inicial = auto_updater.verificar_actualizacion_remota(servidor, cfg)
    assert check_inicial.ok is True
    assert check_inicial.hay_cambios is False

    # Push desde casa modificando código y requirements.lock
    (casa / "app.py").write_text("VERSION = 2\n", encoding="utf-8")
    (casa / "requirements.lock").write_text("pytest==9.2.0\nhttpx==0.28.1\n", encoding="utf-8")
    _git(casa, "add", ".")
    _git(casa, "commit", "-m", "Cambio desde casa")
    _git(casa, "push", "origin", "master")

    check_nuevo = auto_updater.verificar_actualizacion_remota(servidor, cfg)
    assert check_nuevo.ok is True
    assert check_nuevo.hay_cambios is True
    assert check_nuevo.commits_pendientes == 1
    assert check_nuevo.puede_fast_forward is True

    with patch("src.auto_updater._instalar_dependencias_actualizadas", return_value=True) as mock_pip:
        res_apply = auto_updater.aplicar_actualizacion_local(servidor, cfg)

    assert res_apply.ok is True
    assert res_apply.actualizado is True
    assert res_apply.dependencias_actualizadas is True
    mock_pip.assert_called_once()
    assert (servidor / "app.py").read_text(encoding="utf-8") == "VERSION = 2\n"


def test_protege_cambios_locales_y_retorna_75_si_cambia_bat(tmp_path: Path) -> None:
    _remote, casa, servidor = _crear_repo_con_remoto(tmp_path)
    cfg = auto_updater.AutoUpdateConfig(rama="master", remoto="origin", instalar_dependencias=False)

    # Push desde casa modificando iniciar_servidor_web.bat
    (casa / "iniciar_servidor_web.bat").write_text("@echo off\necho v2\n", encoding="utf-8")
    _git(casa, "add", ".")
    _git(casa, "commit", "-m", "Actualiza bat")
    _git(casa, "push", "origin", "master")

    # Cambio local sin commitear en servidor bloquea pull
    (servidor / "app.py").write_text("LOCAL_DIRTY = True\n", encoding="utf-8")
    res_dirty = auto_updater.aplicar_actualizacion_local(servidor, cfg)
    assert res_dirty.ok is False
    assert "cambios locales" in res_dirty.error.lower()

    # Al limpiar cambio local, pre_start aplica actualización y retorna 75 por el .bat
    _git(servidor, "checkout", "--", "app.py")
    with patch("src.auto_updater._puerto_local_activo", return_value=False), patch(
        "src.auto_updater.cargar_config_auto_update", return_value=cfg
    ):
        rc = auto_updater.ejecutar_pre_start([], root=servidor)
    assert rc == auto_updater.EXIT_CODE_RELAUNCH_BAT


def test_watcher_espera_inactividad_y_reinicia_cuando_queda_libre(tmp_path: Path) -> None:
    _remote, casa, servidor = _crear_repo_con_remoto(tmp_path)

    (casa / "app.py").write_text("VERSION = 3\n", encoding="utf-8")
    _git(casa, "add", ".")
    _git(casa, "commit", "-m", "Push nocturno")
    _git(casa, "push", "origin", "master")

    cfg = auto_updater.AutoUpdateConfig(
        habilitado_watcher=True,
        rama="master",
        remoto="origin",
        intervalo_minutos=5.0,
        inactividad_http_segundos=120.0,
        inactividad_ws_segundos=600.0,
        ventana_horaria="",
    )
    notifs: list[tuple[str, str]] = []
    reinicios = [0]
    excel_pendiente = [False]

    watcher = auto_updater.AutoUpdateWatcher(
        port=8550,
        argv=["--ocultar-consola"],
        root=servidor,
        config=cfg,
        on_restart_requested=lambda: reinicios.__setitem__(0, reinicios[0] + 1),
        notifier=lambda t, m: notifs.append((t, m)),
        pending_excel_fn=lambda: ["Productos.xlsx"] if excel_pendiente[0] else [],
    )

    try:
        # 1. Ping periódico NO debe contar como actividad HTTP real
        auto_updater.resetear_estado_actividad_para_tests(ws_abiertos=0, segundos_sin_http=300.0, segundos_sin_ws=300.0)
        auto_updater.registrar_actividad_http("/api/v1/sistema/ping")
        assert auto_updater.obtener_estado_actividad()["segundos_sin_http"] >= 299.0

        # 2. Actividad HTTP reciente pospone reinicio
        auto_updater.registrar_actividad_http("/api/v1/productos")
        with patch("src.auto_updater.lanzar_handoff_reinicio") as mock_handoff:
            assert watcher.revisar_una_vez() is False
            mock_handoff.assert_not_called()
        assert len(notifs) == 1
        assert "disponible" in notifs[0][0].lower()

        # 3. WebSocket activo pospone reinicio aunque no haya HTTP reciente
        auto_updater.resetear_estado_actividad_para_tests(ws_abiertos=1, segundos_sin_http=300.0, segundos_sin_ws=30.0)
        with patch("src.auto_updater.lanzar_handoff_reinicio") as mock_handoff:
            assert watcher.revisar_una_vez() is False
            mock_handoff.assert_not_called()

        # 4. Cola Excel pendiente pospone reinicio
        auto_updater.resetear_estado_actividad_para_tests(ws_abiertos=0, segundos_sin_http=300.0, segundos_sin_ws=300.0)
        excel_pendiente[0] = True
        with patch("src.auto_updater.lanzar_handoff_reinicio") as mock_handoff:
            assert watcher.revisar_una_vez() is False
            mock_handoff.assert_not_called()

        # 5. Al quedar inactivo y sin cola Excel, lanza handoff y solicita apagado limpio
        excel_pendiente[0] = False
        with patch("src.auto_updater.lanzar_handoff_reinicio", return_value=True) as mock_handoff:
            assert watcher.revisar_una_vez() is True
            mock_handoff.assert_called_once()
        assert reinicios[0] == 1
    finally:
        watcher.detener()
        auto_updater.resetear_estado_actividad_para_tests()


def test_solicitar_actualizacion_manual_al_dia_y_con_cambios(tmp_path: Path) -> None:
    _remote, casa, servidor = _crear_repo_con_remoto(tmp_path)
    notifs: list[tuple[str, str]] = []
    reinicios = [0]

    with patch("src.auto_updater.application_root", return_value=servidor), patch(
        "src.auto_updater.obtener_watcher_activo", return_value=None
    ):
        ok, msg = auto_updater.solicitar_actualizacion_y_reinicio_manual(
            port=8550,
            notifier=lambda t, m: notifs.append((t, m)),
            on_restart_requested=lambda: reinicios.__setitem__(0, reinicios[0] + 1),
        )
        assert ok is False
        assert "última versión" in msg.lower()
        assert reinicios[0] == 0

        (casa / "app.py").write_text("VERSION = 4\n", encoding="utf-8")
        _git(casa, "add", ".")
        _git(casa, "commit", "-m", "Nuevo fix")
        _git(casa, "push", "origin", "master")

        with patch("src.auto_updater.lanzar_handoff_reinicio", return_value=True) as mock_handoff:
            ok2, _msg2 = auto_updater.solicitar_actualizacion_y_reinicio_manual(
                port=8550,
                notifier=lambda t, m: notifs.append((t, m)),
                on_restart_requested=lambda: reinicios.__setitem__(0, reinicios[0] + 1),
            )
        assert ok2 is True
        mock_handoff.assert_called_once()
        assert reinicios[0] == 1


def test_cargar_config_auto_update_desde_env() -> None:
    env_override = {
        "STOCKAGENT_AUTO_UPDATE_ON_START": "0",
        "STOCKAGENT_AUTO_UPDATE_WATCH": "1",
        "STOCKAGENT_AUTO_UPDATE_BRANCH": "master",
        "STOCKAGENT_AUTO_UPDATE_MODE": "tag",
        "STOCKAGENT_AUTO_UPDATE_TAG_PATTERN": "v*",
        "STOCKAGENT_AUTO_UPDATE_PRERELEASES": "0",
        "STOCKAGENT_AUTO_UPDATE_INTERVAL_MIN": "10",
        "STOCKAGENT_AUTO_UPDATE_IDLE_SECONDS": "180",
        "STOCKAGENT_AUTO_UPDATE_WS_IDLE_SECONDS": "900",
        "STOCKAGENT_AUTO_UPDATE_WINDOW": "20:00-07:00",
    }
    with patch.dict(os.environ, env_override, clear=False):
        cfg = auto_updater.cargar_config_auto_update()
    assert cfg.habilitado_inicio is False
    assert cfg.habilitado_watcher is True
    assert cfg.modo == "tag"
    assert cfg.tag_patron == "v*"
    assert cfg.incluir_prereleases is False
    assert cfg.intervalo_minutos == 10.0
    assert cfg.inactividad_http_segundos == 180.0
    assert cfg.inactividad_ws_segundos == 900.0
    assert cfg.ventana_horaria == "20:00-07:00"
    assert isinstance(MagicMock(), MagicMock)


def test_seleccionar_ultimo_tag_semver_y_prereleases() -> None:
    tags = ["v1.2.0", "v1.10.0", "v1.10.1-rc1", "v1.9.9", "v2.0.0-beta.1"]
    assert auto_updater.seleccionar_ultimo_tag(tags, incluir_prereleases=False) == "v1.10.0"
    assert auto_updater.seleccionar_ultimo_tag(tags, incluir_prereleases=True) == "v2.0.0-beta.1"
    # Estable siempre le gana a su propio prerelease
    assert auto_updater.seleccionar_ultimo_tag(["v2.0.0-rc1", "v2.0.0"], incluir_prereleases=True) == "v2.0.0"


def test_modo_tag_ignora_commits_sin_tag_y_actualiza_solo_en_release(tmp_path: Path) -> None:
    _remote, casa, servidor = _crear_repo_con_remoto(tmp_path)
    cfg_tag = auto_updater.AutoUpdateConfig(
        modo="tag",
        tag_patron="v*",
        incluir_prereleases=False,
        remoto="origin",
        instalar_dependencias=False,
    )

    # 1. Commit en master SIN tag NO debe disparar actualización en modo tag
    (casa / "app.py").write_text("VERSION = 'wip'\n", encoding="utf-8")
    _git(casa, "add", ".")
    _git(casa, "commit", "-m", "WIP sin release")
    _git(casa, "push", "origin", "master")

    check_sin_tag = auto_updater.verificar_actualizacion_remota(servidor, cfg_tag)
    assert check_sin_tag.ok is True
    assert check_sin_tag.hay_cambios is False

    # 2. Publicar un prerelease v1.0.0-rc1 también se ignora cuando incluir_prereleases=False
    _git(casa, "tag", "v1.0.0-rc1")
    _git(casa, "push", "origin", "v1.0.0-rc1")
    check_rc = auto_updater.verificar_actualizacion_remota(servidor, cfg_tag)
    assert check_rc.ok is True
    assert check_rc.hay_cambios is False

    # 3. Publicar release estable v1.0.0 sí detecta y aplica checkout limpio del tag
    (casa / "app.py").write_text("VERSION = '1.0.0'\n", encoding="utf-8")
    _git(casa, "add", ".")
    _git(casa, "commit", "-m", "Release 1.0.0")
    _git(casa, "tag", "v1.0.0")
    _git(casa, "push", "origin", "master", "v1.0.0")

    check_rel = auto_updater.verificar_actualizacion_remota(servidor, cfg_tag)
    assert check_rel.ok is True
    assert check_rel.hay_cambios is True
    assert check_rel.tag_objetivo == "v1.0.0"
    assert check_rel.puede_fast_forward is True

    res_apply = auto_updater.aplicar_actualizacion_local(servidor, cfg_tag)
    assert res_apply.ok is True
    assert res_apply.actualizado is True
    assert res_apply.tag_nuevo == "v1.0.0"
    assert (servidor / "app.py").read_text(encoding="utf-8") == "VERSION = '1.0.0'\n"

    # 4. Estando ya en HEAD desacoplado de v1.0.0, volver a chequear marca al día
    check_al_dia = auto_updater.verificar_actualizacion_remota(servidor, cfg_tag)
    assert check_al_dia.ok is True
    assert check_al_dia.hay_cambios is False
    assert check_al_dia.tag_actual == "v1.0.0"

    # 5. Nuevo release v1.1.0 desde detached HEAD actualiza limpiamente
    (casa / "app.py").write_text("VERSION = '1.1.0'\n", encoding="utf-8")
    _git(casa, "add", ".")
    _git(casa, "commit", "-m", "Release 1.1.0")
    _git(casa, "tag", "v1.1.0")
    _git(casa, "push", "origin", "master", "v1.1.0")

    res_v2 = auto_updater.aplicar_actualizacion_local(servidor, cfg_tag)
    assert res_v2.ok is True
    assert res_v2.actualizado is True
    assert res_v2.tag_nuevo == "v1.1.0"
    assert (servidor / "app.py").read_text(encoding="utf-8") == "VERSION = '1.1.0'\n"
