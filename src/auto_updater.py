"""Auto-actualización desde Git (arranque/reinicio y vigilancia en segundo plano)."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Sequence

from .paths import application_root

logger = logging.getLogger("stockagent.updater")

EXIT_CODE_RELAUNCH_BAT = 75
_RE_GIT_REF = re.compile(r"^[A-Za-z0-9_./-]+$")
_RUTAS_IGNORADAS_ACTIVIDAD = frozenset({"/api/v1/sistema/ping", "/favicon.ico"})
_FLAGS_REINICIO = ("--force", "--forzar", "--reiniciar", "--restart")
_FLAGS_SIN_ACTUALIZAR = ("--no-auto-update", "--sin-actualizar")
_FLAGS_OCULTAR_CONSOLA = ("--hide-console", "--ocultar-consola", "--silent")
_FLAGS_PRESERVAR_VALOR = ("--host", "--port", "--ssl-cert", "--ssl-key", "--inactividad", "--timeout", "--env")
_FLAGS_PRESERVAR_BOOLEANOS = (
    "--qa",
    "--desktop",
    "--https",
    "--http",
    "--no-tray",
    "--sin-tray",
    "--ocultar-consola",
    "--hide-console",
    "--silent",
)


def _cargar_dotenv_si_existe(root: Path) -> None:
    try:
        from dotenv import load_dotenv

        env_file = root / ".env"
        if env_file.is_file():
            load_dotenv(env_file, override=False)
    except Exception:
        pass


def _env_bool(nombre: str, default: bool) -> bool:
    raw = os.environ.get(nombre)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off")


def _env_float(nombre: str, default: float, minimo: float = 0.0) -> float:
    raw = os.environ.get(nombre)
    if raw is None or not raw.strip():
        return default
    try:
        val = float(raw.strip())
        return max(minimo, val)
    except ValueError:
        return default


def _sanitizar_ref_git(valor: str, fallback: str) -> str:
    limpio = (valor or "").strip()
    if limpio and _RE_GIT_REF.match(limpio) and ".." not in limpio and not limpio.startswith("-"):
        return limpio
    return fallback


@dataclass(frozen=True)
class AutoUpdateConfig:
    """Parámetros de auto-actualización leídos desde variables de entorno."""

    habilitado_inicio: bool = True
    habilitado_watcher: bool = True
    rama: str = "master"
    remoto: str = "origin"
    intervalo_minutos: float = 5.0
    primer_chequeo_segundos: float = 45.0
    inactividad_http_segundos: float = 120.0
    inactividad_ws_segundos: float = 600.0
    ventana_horaria: str = ""
    instalar_dependencias: bool = True
    git_timeout_segundos: float = 15.0


def cargar_config_auto_update(root: Path | None = None) -> AutoUpdateConfig:
    """Carga la configuración de auto-actualización desde `.env` y el entorno actual."""
    raiz = root or application_root()
    _cargar_dotenv_si_existe(raiz)
    intervalo = _env_float("STOCKAGENT_AUTO_UPDATE_INTERVAL_MIN", 5.0, minimo=0.0)
    if 0.0 < intervalo < 1.0:
        intervalo = 1.0
    return AutoUpdateConfig(
        habilitado_inicio=_env_bool("STOCKAGENT_AUTO_UPDATE_ON_START", True),
        habilitado_watcher=_env_bool("STOCKAGENT_AUTO_UPDATE_WATCH", True),
        rama=_sanitizar_ref_git(os.environ.get("STOCKAGENT_AUTO_UPDATE_BRANCH", "master"), "master"),
        remoto=_sanitizar_ref_git(os.environ.get("STOCKAGENT_AUTO_UPDATE_REMOTE", "origin"), "origin"),
        intervalo_minutos=intervalo,
        primer_chequeo_segundos=_env_float("STOCKAGENT_AUTO_UPDATE_INITIAL_DELAY_SECONDS", 45.0, minimo=5.0),
        inactividad_http_segundos=_env_float("STOCKAGENT_AUTO_UPDATE_IDLE_SECONDS", 120.0, minimo=0.0),
        inactividad_ws_segundos=_env_float("STOCKAGENT_AUTO_UPDATE_WS_IDLE_SECONDS", 600.0, minimo=0.0),
        ventana_horaria=os.environ.get("STOCKAGENT_AUTO_UPDATE_WINDOW", "").strip(),
        instalar_dependencias=_env_bool("STOCKAGENT_AUTO_UPDATE_PIP", True),
        git_timeout_segundos=_env_float("STOCKAGENT_AUTO_UPDATE_TIMEOUT_SECONDS", 15.0, minimo=3.0),
    )


@dataclass
class GitCheckResult:
    ok: bool
    hay_cambios: bool = False
    commits_pendientes: int = 0
    commit_local: str = ""
    commit_remoto: str = ""
    rama_actual: str = ""
    puede_fast_forward: bool = True
    error: str = ""


@dataclass
class UpdateApplyResult:
    ok: bool
    actualizado: bool = False
    mensaje: str = ""
    commit_anterior: str = ""
    commit_nuevo: str = ""
    archivos_cambiados: list[str] = field(default_factory=list)
    dependencias_actualizadas: bool = False
    error: str = ""


_LOCK_ACTIVIDAD = threading.Lock()
_ULTIMO_HTTP_ACTIVO: float = time.monotonic()
_ULTIMO_WS_EVENTO: float = time.monotonic()
_WS_ABIERTOS: int = 0


def registrar_actividad_http(ruta: str) -> None:
    """Registra una petición HTTP de negocio (ignora pings periódicos de conectividad)."""
    if (ruta or "") in _RUTAS_IGNORADAS_ACTIVIDAD:
        return
    global _ULTIMO_HTTP_ACTIVO
    with _LOCK_ACTIVIDAD:
        _ULTIMO_HTTP_ACTIVO = time.monotonic()


def registrar_ws_abierto() -> None:
    """Incrementa el conteo de sesiones WebSocket activas."""
    global _WS_ABIERTOS, _ULTIMO_WS_EVENTO
    with _LOCK_ACTIVIDAD:
        _WS_ABIERTOS += 1
        _ULTIMO_WS_EVENTO = time.monotonic()


def registrar_ws_cerrado() -> None:
    """Decrementa el conteo de sesiones WebSocket activas."""
    global _WS_ABIERTOS
    with _LOCK_ACTIVIDAD:
        _WS_ABIERTOS = max(0, _WS_ABIERTOS - 1)


def registrar_ws_actividad() -> None:
    """Actualiza la marca temporal de última interacción de cliente por WebSocket."""
    global _ULTIMO_WS_EVENTO
    with _LOCK_ACTIVIDAD:
        _ULTIMO_WS_EVENTO = time.monotonic()


def obtener_estado_actividad() -> dict[str, float | int]:
    """Devuelve métricas actuales de actividad HTTP/WebSocket para evaluar ventana de reinicio."""
    ahora = time.monotonic()
    with _LOCK_ACTIVIDAD:
        return {
            "ws_abiertos": _WS_ABIERTOS,
            "segundos_sin_http": max(0.0, ahora - _ULTIMO_HTTP_ACTIVO),
            "segundos_sin_ws": max(0.0, ahora - _ULTIMO_WS_EVENTO),
        }


def resetear_estado_actividad_para_tests(
    *,
    ws_abiertos: int = 0,
    segundos_sin_http: float = 0.0,
    segundos_sin_ws: float = 0.0,
) -> None:
    """Reinicia contadores internos de actividad para pruebas unitarias determinísticas."""
    global _WS_ABIERTOS, _ULTIMO_HTTP_ACTIVO, _ULTIMO_WS_EVENTO
    ahora = time.monotonic()
    with _LOCK_ACTIVIDAD:
        _WS_ABIERTOS = max(0, int(ws_abiertos))
        _ULTIMO_HTTP_ACTIVO = ahora - max(0.0, float(segundos_sin_http))
        _ULTIMO_WS_EVENTO = ahora - max(0.0, float(segundos_sin_ws))


def esta_en_ventana_horaria(ventana: str, ahora: datetime | None = None) -> bool:
    """Evalúa si ``ahora`` cae dentro de un rango ``HH:MM-HH:MM`` (admite cruce de medianoche)."""
    texto = (ventana or "").strip()
    if not texto:
        return True
    match = re.match(r"^(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})$", texto)
    if not match:
        logger.warning("Formato inválido de STOCKAGENT_AUTO_UPDATE_WINDOW (%r); se ignora restricción.", texto)
        return True
    h1, m1, h2, m2 = (int(g) for g in match.groups())
    if not (0 <= h1 <= 23 and 0 <= h2 <= 23 and 0 <= m1 <= 59 and 0 <= m2 <= 59):
        return True
    ref = ahora or datetime.now()
    actual_min = ref.hour * 60 + ref.minute
    inicio_min = h1 * 60 + m1
    fin_min = h2 * 60 + m2
    if inicio_min == fin_min:
        return True
    if inicio_min < fin_min:
        return inicio_min <= actual_min < fin_min
    return actual_min >= inicio_min or actual_min < fin_min


def _subprocess_hidden_kwargs() -> dict[str, object]:
    if sys.platform == "win32":
        create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        return {"creationflags": create_no_window}
    return {}


def _run_git(
    args: Sequence[str],
    root: Path,
    timeout: float = 15.0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        **_subprocess_hidden_kwargs(),
    )


def es_repositorio_git(root: Path | None = None) -> bool:
    """Indica si el entorno actual es un clon Git ejecutable desde código fuente."""
    if getattr(sys, "frozen", False):
        return False
    raiz = root or application_root()
    return (raiz / ".git").exists() and shutil.which("git") is not None


def obtener_rama_actual(root: Path, timeout: float = 10.0) -> str:
    res = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], root, timeout=timeout)
    if res.returncode != 0:
        return ""
    return res.stdout.strip()


def obtener_commit_hash(root: Path, ref: str = "HEAD", corto: bool = False, timeout: float = 10.0) -> str:
    args = ["rev-parse"]
    if corto:
        args.append("--short")
    args.append(ref)
    res = _run_git(args, root, timeout=timeout)
    if res.returncode != 0:
        return ""
    return res.stdout.strip()


def tiene_cambios_locales_rastreados(root: Path, timeout: float = 10.0) -> bool:
    """Devuelve True si hay modificaciones sin commitear en archivos rastreados por Git."""
    res = _run_git(["status", "--porcelain", "-uno"], root, timeout=timeout)
    if res.returncode != 0:
        return True
    return bool(res.stdout.strip())


def verificar_actualizacion_remota(
    root: Path | None = None,
    config: AutoUpdateConfig | None = None,
) -> GitCheckResult:
    """Consulta el remoto con ``git fetch`` sin modificar archivos del árbol de trabajo."""
    raiz = root or application_root()
    cfg = config or cargar_config_auto_update(raiz)
    if not es_repositorio_git(raiz):
        return GitCheckResult(ok=False, error="No es un repositorio Git o falta el ejecutable git.")

    try:
        rama_actual = obtener_rama_actual(raiz, timeout=cfg.git_timeout_segundos)
        if not rama_actual or rama_actual == "HEAD":
            return GitCheckResult(ok=False, rama_actual=rama_actual, error="HEAD desacoplado; no se actualiza.")
        if rama_actual != cfg.rama:
            return GitCheckResult(
                ok=False,
                rama_actual=rama_actual,
                error=f"Rama actual '{rama_actual}' distinta de '{cfg.rama}'.",
            )

        res_fetch = _run_git(["fetch", cfg.remoto, cfg.rama], raiz, timeout=cfg.git_timeout_segundos)
        if res_fetch.returncode != 0:
            err = (res_fetch.stderr or res_fetch.stdout or "Fallo git fetch").strip()
            return GitCheckResult(ok=False, rama_actual=rama_actual, error=err)

        ref_remota = f"{cfg.remoto}/{cfg.rama}"
        commit_local = obtener_commit_hash(raiz, "HEAD", timeout=cfg.git_timeout_segundos)
        commit_remoto = obtener_commit_hash(raiz, ref_remota, timeout=cfg.git_timeout_segundos)
        if not commit_local or not commit_remoto:
            return GitCheckResult(
                ok=False,
                rama_actual=rama_actual,
                commit_local=commit_local,
                commit_remoto=commit_remoto,
                error="No se pudo resolver SHA local o remoto.",
            )

        res_count = _run_git(
            ["rev-list", "--count", f"HEAD..{ref_remota}"],
            raiz,
            timeout=cfg.git_timeout_segundos,
        )
        pendientes = int(res_count.stdout.strip()) if res_count.returncode == 0 and res_count.stdout.strip().isdigit() else 0

        res_ff = _run_git(
            ["merge-base", "--is-ancestor", "HEAD", ref_remota],
            raiz,
            timeout=cfg.git_timeout_segundos,
        )
        puede_ff = res_ff.returncode == 0

        return GitCheckResult(
            ok=True,
            hay_cambios=pendientes > 0,
            commits_pendientes=pendientes,
            commit_local=commit_local,
            commit_remoto=commit_remoto,
            rama_actual=rama_actual,
            puede_fast_forward=puede_ff,
        )
    except subprocess.TimeoutExpired:
        return GitCheckResult(ok=False, error="Tiempo de espera agotado al consultar GitHub.")
    except Exception as exc:
        return GitCheckResult(ok=False, error=str(exc))


def _sha256_archivo(ruta: Path) -> str:
    if not ruta.is_file():
        return ""
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _resolver_python_venv(root: Path) -> str:
    candidato = root / ".venv" / "Scripts" / "python.exe"
    if candidato.is_file():
        return str(candidato)
    return sys.executable


def _instalar_dependencias_actualizadas(root: Path, timeout_s: float = 180.0) -> bool:
    lock_file = root / "requirements.lock"
    req_file = root / "requirements.txt"
    objetivo = lock_file if lock_file.is_file() else req_file
    if not objetivo.is_file():
        return False
    python_exe = _resolver_python_venv(root)
    logger.info("Dependencias modificadas; ejecutando pip install -r %s ...", objetivo.name)
    res = subprocess.run(
        [python_exe, "-m", "pip", "install", "--disable-pip-version-check", "-r", str(objetivo)],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s,
        check=False,
        **_subprocess_hidden_kwargs(),
    )
    if res.returncode != 0:
        logger.warning("Fallo al actualizar dependencias con pip: %s", (res.stderr or res.stdout).strip())
        return False
    logger.info("Dependencias Python actualizadas correctamente.")
    return True


def aplicar_actualizacion_local(
    root: Path | None = None,
    config: AutoUpdateConfig | None = None,
    *,
    forzar_fetch: bool = True,
) -> UpdateApplyResult:
    """Descarga cambios fast-forward desde ``origin/<rama>`` e instala dependencias si cambiaron."""
    raiz = root or application_root()
    cfg = config or cargar_config_auto_update(raiz)
    if not es_repositorio_git(raiz):
        return UpdateApplyResult(ok=False, error="No es un repositorio Git.")

    try:
        if tiene_cambios_locales_rastreados(raiz, timeout=cfg.git_timeout_segundos):
            msg = "Hay cambios locales sin commitear; se omite actualización automática para proteger el árbol."
            logger.warning(msg)
            return UpdateApplyResult(ok=False, error=msg)

        if forzar_fetch:
            check = verificar_actualizacion_remota(raiz, cfg)
            if not check.ok:
                return UpdateApplyResult(ok=False, error=check.error)
            if not check.hay_cambios:
                return UpdateApplyResult(
                    ok=True,
                    actualizado=False,
                    mensaje="El repositorio ya está en la última versión.",
                    commit_anterior=check.commit_local,
                    commit_nuevo=check.commit_local,
                )
            if not check.puede_fast_forward:
                msg = "La rama local divergió del remoto; se requiere revisión manual de Git."
                logger.warning(msg)
                return UpdateApplyResult(ok=False, error=msg)

        commit_antes = obtener_commit_hash(raiz, "HEAD", timeout=cfg.git_timeout_segundos)
        hashes_req_antes = {
            "requirements.lock": _sha256_archivo(raiz / "requirements.lock"),
            "requirements.txt": _sha256_archivo(raiz / "requirements.txt"),
        }

        res_pull = _run_git(
            ["pull", "--ff-only", cfg.remoto, cfg.rama],
            raiz,
            timeout=max(cfg.git_timeout_segundos, 30.0),
        )
        if res_pull.returncode != 0:
            err = (res_pull.stderr or res_pull.stdout or "Fallo git pull --ff-only").strip()
            return UpdateApplyResult(ok=False, commit_anterior=commit_antes, error=err)

        commit_despues = obtener_commit_hash(raiz, "HEAD", timeout=cfg.git_timeout_segundos)
        cambiados: list[str] = []
        if commit_antes and commit_despues and commit_antes != commit_despues:
            res_diff = _run_git(
                ["diff", "--name-only", commit_antes, commit_despues],
                raiz,
                timeout=cfg.git_timeout_segundos,
            )
            if res_diff.returncode == 0:
                cambiados = [linea.strip() for linea in res_diff.stdout.splitlines() if linea.strip()]

        deps_cambiaron = any(
            _sha256_archivo(raiz / nombre) != hash_prev
            for nombre, hash_prev in hashes_req_antes.items()
        )
        deps_actualizadas = False
        if deps_cambiaron and cfg.instalar_dependencias:
            deps_actualizadas = _instalar_dependencias_actualizadas(raiz)

        actualizado = bool(commit_antes and commit_despues and commit_antes != commit_despues)
        return UpdateApplyResult(
            ok=True,
            actualizado=actualizado,
            mensaje="Actualización aplicada correctamente." if actualizado else "Sin cambios nuevos.",
            commit_anterior=commit_antes,
            commit_nuevo=commit_despues,
            archivos_cambiados=cambiados,
            dependencias_actualizadas=deps_actualizadas,
        )
    except subprocess.TimeoutExpired:
        return UpdateApplyResult(ok=False, error="Tiempo de espera agotado al ejecutar git pull.")
    except Exception as exc:
        return UpdateApplyResult(ok=False, error=str(exc))


def _puerto_local_activo(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            return True
    except OSError:
        return False


def obtener_pids_puerto(port: int) -> list[int]:
    """Devuelve los PIDs escuchando en ``port`` local (Windows netstat)."""
    pids: list[int] = []
    if sys.platform != "win32":
        return pids
    try:
        salida = subprocess.check_output(
            ["netstat", "-ano"],
            text=True,
            encoding="utf-8",
            errors="replace",
            **_subprocess_hidden_kwargs(),
        )
        patron_puerto = re.compile(rf":{port}\s")
        for linea in salida.splitlines():
            if patron_puerto.search(linea) and "LISTENING" in linea:
                partes = linea.strip().split()
                if partes and partes[-1].isdigit():
                    pid = int(partes[-1])
                    if pid > 0 and pid not in pids:
                        pids.append(pid)
    except Exception:
        pass
    return pids


def detener_servidor_en_puerto(port: int, timeout_s: float = 12.0) -> bool:
    """Detiene cualquier proceso escuchando en ``port`` y espera a que libere el socket."""
    pids = obtener_pids_puerto(port)
    for pid in pids:
        if pid == os.getpid():
            continue
        try:
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                capture_output=True,
                check=False,
                **_subprocess_hidden_kwargs(),
            )
        except Exception:
            pass

    limite = time.monotonic() + timeout_s
    while time.monotonic() < limite:
        if not _puerto_local_activo(port):
            return True
        time.sleep(0.25)
    return not _puerto_local_activo(port)


def extraer_puerto_de_argv(argv: Sequence[str], default_port: int = 8550) -> int:
    """Obtiene el puerto efectivo considerando flags CLI y ``STOCKAGENT_PORT``."""
    args = list(argv)
    for idx, arg in enumerate(args):
        if arg == "--port" and idx + 1 < len(args):
            try:
                return int(args[idx + 1])
            except ValueError:
                break
    try:
        return int(os.environ.get("STOCKAGENT_PORT", str(default_port)))
    except ValueError:
        return default_port


def tiene_flag_reinicio(argv: Sequence[str]) -> bool:
    return any(arg.lower() in _FLAGS_REINICIO for arg in argv)


def tiene_flag_sin_actualizar(argv: Sequence[str]) -> bool:
    return any(arg.lower() in _FLAGS_SIN_ACTUALIZAR for arg in argv)


def construir_flags_reinicio(argv: Sequence[str]) -> list[str]:
    """Preserva los flags de ejecución relevantes añadiendo ``--no-browser`` y ``--no-auto-update``."""
    resultado: list[str] = []
    args = list(argv)
    i = 0
    while i < len(args):
        arg = args[i]
        low = arg.lower()
        if low in _FLAGS_PRESERVAR_VALOR and i + 1 < len(args):
            resultado.extend([arg, args[i + 1]])
            i += 2
            continue
        if low in _FLAGS_PRESERVAR_BOOLEANOS and arg not in resultado:
            resultado.append(arg)
        i += 1

    for obligatorio in ("--no-browser", "--no-auto-update"):
        if obligatorio not in [x.lower() for x in resultado]:
            resultado.append(obligatorio)
    return resultado


def lanzar_handoff_reinicio(
    root: Path | None = None,
    port: int = 8550,
    argv: Sequence[str] = (),
    wait_pid: int | None = None,
) -> bool:
    """Lanza un proceso independiente que espera el cierre actual, actualiza y relanza el servidor."""
    raiz = root or application_root()
    python_exe = _resolver_python_venv(raiz)
    pid_espera = os.getpid() if wait_pid is None else wait_pid
    flags_preservados = construir_flags_reinicio(argv)

    cmd = [
        python_exe,
        "-m",
        "src.auto_updater",
        "--restart-handoff",
        "--wait-pid",
        str(pid_espera),
        "--port",
        str(port),
        *flags_preservados,
    ]
    kwargs: dict[str, object] = {
        "cwd": str(raiz),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if sys.platform == "win32":
        create_new_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        kwargs["creationflags"] = create_new_group | create_no_window
    else:
        kwargs["start_new_session"] = True

    try:
        subprocess.Popen(cmd, **kwargs)  # type: ignore[arg-type]
        return True
    except Exception as exc:
        logger.error("No se pudo iniciar proceso de handoff de reinicio: %s", exc)
        return False


def _lanzar_servidor_desacoplado(root: Path, flags: Sequence[str]) -> bool:
    oculto = any(f.lower() in _FLAGS_OCULTAR_CONSOLA for f in flags)
    bat_path = root / "iniciar_servidor_web.bat"
    kwargs: dict[str, object] = {
        "cwd": str(root),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if sys.platform == "win32" and bat_path.is_file():
        cmd = ["cmd.exe", "/c", str(bat_path), *flags]
        create_new_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        if oculto:
            create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            kwargs["creationflags"] = create_new_group | create_no_window
        else:
            create_new_console = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)
            kwargs["creationflags"] = create_new_group | create_new_console
    else:
        python_exe = _resolver_python_venv(root)
        cmd = [python_exe, str(root / "main.py"), *flags]
        if sys.platform == "win32":
            create_new_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
            create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            kwargs["creationflags"] = create_new_group | create_no_window
        else:
            kwargs["start_new_session"] = True

    try:
        subprocess.Popen(cmd, **kwargs)  # type: ignore[arg-type]
        return True
    except Exception as exc:
        logger.error("No se pudo relanzar el servidor tras handoff: %s", exc)
        return False


def ejecutar_pre_start(argv: Sequence[str], root: Path | None = None) -> int:
    """Paso ejecutado antes de arrancar ``main.py`` desde los scripts de inicio."""
    raiz = root or application_root()
    cfg = cargar_config_auto_update(raiz)
    if not cfg.habilitado_inicio or tiene_flag_sin_actualizar(argv):
        return 0
    if not es_repositorio_git(raiz):
        return 0

    puerto = extraer_puerto_de_argv(argv)
    if _puerto_local_activo(puerto):
        if not tiene_flag_reinicio(argv):
            # Ya hay un servidor corriendo; no mutar código bajo una instancia viva.
            return 0
        logger.info("Deteniendo servidor previo en puerto %s antes de actualizar...", puerto)
        detener_servidor_en_puerto(puerto, timeout_s=12.0)

    res = aplicar_actualizacion_local(raiz, cfg, forzar_fetch=True)
    if res.actualizado:
        print(
            f"[AUTO-UPDATE] Repositorio actualizado ({res.commit_anterior[:7]} -> {res.commit_nuevo[:7]}).",
            flush=True,
        )
        logger.info(
            "Actualización en arranque aplicada: %s -> %s (%d archivo(s)).",
            res.commit_anterior[:7],
            res.commit_nuevo[:7],
            len(res.archivos_cambiados),
        )
        if any(p.lower().endswith("iniciar_servidor_web.bat") for p in res.archivos_cambiados):
            return EXIT_CODE_RELAUNCH_BAT
    elif not res.ok and res.error:
        print(f"[AUTO-UPDATE] Omitido ({res.error}). Continuando con la versión local.", flush=True)
        logger.warning("Auto-actualización al arranque omitida: %s", res.error)
    return 0


def _pid_activo(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            res = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                **_subprocess_hidden_kwargs(),
            )
            return str(pid) in res.stdout
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def ejecutar_restart_handoff(argv: Sequence[str], root: Path | None = None) -> int:
    """Espera el cierre del servidor previo, aplica pull + pip y relanza el servidor."""
    raiz = root or application_root()
    args = list(argv)
    wait_pid = 0
    port = extraer_puerto_de_argv(args)

    filtered: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--wait-pid" and i + 1 < len(args):
            if args[i + 1].isdigit():
                wait_pid = int(args[i + 1])
            i += 2
            continue
        if arg == "--restart-handoff":
            i += 1
            continue
        filtered.append(arg)
        i += 1

    limite = time.monotonic() + 14.0
    while time.monotonic() < limite:
        sigue_pid = wait_pid > 0 and _pid_activo(wait_pid)
        sigue_puerto = _puerto_local_activo(port)
        if not sigue_pid and not sigue_puerto:
            break
        time.sleep(0.3)

    if (wait_pid > 0 and _pid_activo(wait_pid)) or _puerto_local_activo(port):
        logger.warning("Instancia previa aún activa tras espera; forzando cierre antes de reiniciar.")
        if wait_pid > 0 and sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/PID", str(wait_pid)],
                capture_output=True,
                check=False,
                **_subprocess_hidden_kwargs(),
            )
        detener_servidor_en_puerto(port, timeout_s=6.0)

    cfg = cargar_config_auto_update(raiz)
    res = aplicar_actualizacion_local(raiz, cfg, forzar_fetch=True)
    if res.actualizado:
        logger.info(
            "Handoff aplicó actualización %s -> %s (deps=%s).",
            res.commit_anterior[:7],
            res.commit_nuevo[:7],
            res.dependencias_actualizadas,
        )
    elif not res.ok:
        logger.warning("Handoff no pudo actualizar (%s); relanzando servidor de todos modos.", res.error)

    flags_relanzar = construir_flags_reinicio(filtered)
    ok = _lanzar_servidor_desacoplado(raiz, flags_relanzar)
    return 0 if ok else 1


class AutoUpdateWatcher:
    """Vigilante periódico en segundo plano que detecta cambios en Git y reinicia en inactividad."""

    def __init__(
        self,
        *,
        port: int = 8550,
        argv: Sequence[str] = (),
        root: Path | None = None,
        config: AutoUpdateConfig | None = None,
        on_restart_requested: Optional[Callable[[], None]] = None,
        notifier: Optional[Callable[[str, str], None]] = None,
        pending_excel_fn: Optional[Callable[[], Sequence[object]]] = None,
    ):
        self.root = root or application_root()
        self.port = port
        self.argv = tuple(argv)
        self.config = config or cargar_config_auto_update(self.root)
        self.on_restart_requested = on_restart_requested
        self.notifier = notifier
        self._pending_excel_fn = pending_excel_fn

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._reinicio_en_curso = False
        self._lock = threading.Lock()
        self._ultimo_sha_notificado: str = ""
        self._ultimo_sha_bloqueado: str = ""

    def _notificar(self, titulo: str, mensaje: str) -> None:
        if callable(self.notifier):
            try:
                self.notifier(titulo, mensaje)
                return
            except Exception:
                pass
        try:
            from .tray import service as tray_service

            tray = getattr(tray_service, "_INSTANCIA_ACTIVA", None)
            if tray is not None:
                tray.mostrar_notificacion(titulo, mensaje)
        except Exception:
            pass

    def _hay_excel_pendiente(self) -> bool:
        try:
            if callable(self._pending_excel_fn):
                return bool(self._pending_excel_fn())
            from .inventory import StockManager

            return bool(StockManager.obtener_pendientes_sincronizacion_excel())
        except Exception:
            return False

    def esta_listo_para_reiniciar(self, ahora: datetime | None = None) -> tuple[bool, str]:
        """Evalúa ventana horaria, colas Excel e inactividad HTTP/WS antes de reiniciar."""
        if not esta_en_ventana_horaria(self.config.ventana_horaria, ahora=ahora):
            return False, f"fuera de ventana horaria ({self.config.ventana_horaria})"
        if self._hay_excel_pendiente():
            return False, "sincronización de Excel pendiente"

        act = obtener_estado_actividad()
        if act["segundos_sin_http"] < self.config.inactividad_http_segundos:
            return False, "actividad HTTP reciente"
        if act["ws_abiertos"] > 0 and act["segundos_sin_ws"] < self.config.inactividad_ws_segundos:
            return False, "sesión WebSocket activa recientemente"
        return True, "inactivo"

    def iniciar_reinicio_con_actualizacion(self, *, motivo: str = "automático") -> bool:
        """Lanza el handoff de actualización y solicita apagado limpio del servidor actual."""
        with self._lock:
            if self._reinicio_en_curso:
                return False
            self._reinicio_en_curso = True

        logger.info("Iniciando actualización y reinicio del servidor (%s)...", motivo)
        self._notificar(
            "StockAgent: Actualizando",
            "Descargando últimos cambios desde GitHub y reiniciando servidor...",
        )
        lanzado = lanzar_handoff_reinicio(
            root=self.root,
            port=self.port,
            argv=self.argv,
            wait_pid=os.getpid(),
        )
        if not lanzado:
            with self._lock:
                self._reinicio_en_curso = False
            return False

        self.detener()
        if callable(self.on_restart_requested):
            try:
                self.on_restart_requested()
            except Exception as exc:
                logger.error("Error al solicitar cierre limpio para reinicio: %s", exc)
        return True

    def revisar_una_vez(self, ahora: datetime | None = None) -> bool:
        """Ejecuta una iteración de vigilancia contra ``origin/<rama>``."""
        if not self.config.habilitado_watcher or self.config.intervalo_minutos <= 0:
            return False
        if self._reinicio_en_curso:
            return False
        if not es_repositorio_git(self.root):
            return False

        check = verificar_actualizacion_remota(self.root, self.config)
        if not check.ok or not check.hay_cambios:
            return False

        sha_remoto = check.commit_remoto
        if not check.puede_fast_forward:
            if sha_remoto != self._ultimo_sha_bloqueado:
                self._ultimo_sha_bloqueado = sha_remoto
                logger.warning("Actualización remota %s requiere merge manual (no fast-forward).", sha_remoto[:7])
            return False

        if tiene_cambios_locales_rastreados(self.root, timeout=self.config.git_timeout_segundos):
            if sha_remoto != self._ultimo_sha_bloqueado:
                self._ultimo_sha_bloqueado = sha_remoto
                logger.warning(
                    "Actualización remota %s detectada, pero hay cambios locales sin commitear.",
                    sha_remoto[:7],
                )
            return False

        listo, razon = self.esta_listo_para_reiniciar(ahora=ahora)
        if not listo:
            if sha_remoto != self._ultimo_sha_notificado:
                self._ultimo_sha_notificado = sha_remoto
                logger.info(
                    "Nueva versión %s (%d commit(s)) pendiente en GitHub; esperando (%s).",
                    sha_remoto[:7],
                    check.commits_pendientes,
                    razon,
                )
                self._notificar(
                    "StockAgent: Actualización disponible",
                    f"Hay {check.commits_pendientes} cambio(s) nuevo(s) en GitHub. Se reiniciará al quedar inactivo.",
                )
            return False

        return self.iniciar_reinicio_con_actualizacion(motivo="vigilancia automática")

    def _loop(self) -> None:
        espera_inicial = self.config.primer_chequeo_segundos
        if self._stop_event.wait(espera_inicial):
            return
        intervalo_s = max(60.0, self.config.intervalo_minutos * 60.0)
        while not self._stop_event.is_set():
            try:
                if self.revisar_una_vez():
                    break
            except Exception as exc:  # noqa: BLE001
                logger.debug("Error en ciclo de auto-actualización: %s", exc)
            if self._stop_event.wait(intervalo_s):
                break

    def iniciar(self) -> bool:
        """Arranca el hilo demonio de vigilancia si está habilitado."""
        if not self.config.habilitado_watcher or self.config.intervalo_minutos <= 0:
            return False
        if not es_repositorio_git(self.root):
            return False
        if self._thread is not None and self._thread.is_alive():
            return True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="StockAgentAutoUpdateWatcher",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "Vigilante de auto-actualización activo (rama=%s, intervalo=%.0f min).",
            self.config.rama,
            self.config.intervalo_minutos,
        )
        return True

    def detener(self) -> None:
        """Detiene el hilo de vigilancia inmediatamente."""
        self._stop_event.set()


_WATCHER_ACTIVO: Optional[AutoUpdateWatcher] = None


def iniciar_watcher_auto_update(
    *,
    port: int = 8550,
    argv: Sequence[str] = (),
    on_restart_requested: Optional[Callable[[], None]] = None,
) -> Optional[AutoUpdateWatcher]:
    """Inicia y registra el vigilante global de auto-actualización."""
    global _WATCHER_ACTIVO
    watcher = AutoUpdateWatcher(
        port=port,
        argv=argv,
        on_restart_requested=on_restart_requested,
    )
    if watcher.iniciar():
        _WATCHER_ACTIVO = watcher
        return watcher
    # Guardamos igualmente la instancia para permitir reinicio manual desde System Tray.
    _WATCHER_ACTIVO = watcher
    return watcher


def obtener_watcher_activo() -> Optional[AutoUpdateWatcher]:
    return _WATCHER_ACTIVO


def solicitar_actualizacion_y_reinicio_manual(
    *,
    port: int = 8550,
    argv: Sequence[str] = (),
    notifier: Optional[Callable[[str, str], None]] = None,
    on_restart_requested: Optional[Callable[[], None]] = None,
) -> tuple[bool, str]:
    """Consulta GitHub bajo demanda y reinicia si hay cambios nuevos disponibles."""
    raiz = application_root()
    if not es_repositorio_git(raiz):
        msg = "Esta instalación no es un repositorio Git."
        if callable(notifier):
            notifier("StockAgent", msg)
        return False, msg

    cfg = cargar_config_auto_update(raiz)
    check = verificar_actualizacion_remota(raiz, cfg)
    if not check.ok:
        msg = f"No se pudo consultar GitHub: {check.error}"
        if callable(notifier):
            notifier("StockAgent: Error al actualizar", msg)
        return False, msg

    if not check.hay_cambios:
        msg = f"Ya estás en la última versión ({check.commit_local[:7]})."
        if callable(notifier):
            notifier("StockAgent al día", msg)
        return False, msg

    if not check.puede_fast_forward:
        msg = "La rama local divergió de GitHub; requiere revisión manual."
        if callable(notifier):
            notifier("StockAgent: Actualización bloqueada", msg)
        return False, msg

    if tiene_cambios_locales_rastreados(raiz, timeout=cfg.git_timeout_segundos):
        msg = "Hay cambios locales sin commitear en esta PC; no se sobrescribirán."
        if callable(notifier):
            notifier("StockAgent: Actualización bloqueada", msg)
        return False, msg

    watcher = obtener_watcher_activo()
    if watcher is not None:
        iniciado = watcher.iniciar_reinicio_con_actualizacion(motivo="manual desde bandeja")
        return iniciado, "Actualización iniciada; reiniciando servidor..." if iniciado else "Reinicio ya en curso."

    if callable(notifier):
        notifier("StockAgent: Actualizando", "Descargando cambios y reiniciando servidor...")
    ok = lanzar_handoff_reinicio(root=raiz, port=port, argv=argv or sys.argv[1:], wait_pid=os.getpid())
    if ok and callable(on_restart_requested):
        try:
            on_restart_requested()
        except Exception as exc:
            logger.error("Error al solicitar cierre limpio para reinicio manual: %s", exc)
    return ok, "Actualización iniciada." if ok else "No se pudo lanzar el reinicio."


def _cli_main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--pre-start" in args:
        return ejecutar_pre_start([a for a in args if a != "--pre-start"])
    if "--restart-handoff" in args:
        return ejecutar_restart_handoff(args)
    if "--check" in args:
        res = verificar_actualizacion_remota()
        if not res.ok:
            print(f"[AUTO-UPDATE] Error: {res.error}", file=sys.stderr)
            return 1
        if res.hay_cambios:
            print(f"[AUTO-UPDATE] {res.commits_pendientes} commit(s) nuevo(s): {res.commit_local[:7]} -> {res.commit_remoto[:7]}")
        else:
            print(f"[AUTO-UPDATE] Al día en {res.rama_actual} ({res.commit_local[:7]}).")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli_main())
