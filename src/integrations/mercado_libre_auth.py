"""Configuración cifrada y autenticación OAuth con la API REST de Mercado Libre."""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import os
from pathlib import Path
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

from .. import secretos
from ..paths import application_root

CONFIG_ML_PATH_DEFAULT = "data/config_mercadolibre.json"
API_BASE_URL = "https://api.mercadolibre.com"
_CAMPOS_SECRETOS_ML = ("client_secret", "access_token", "refresh_token")


def _obtener_ruta_config_ml(root_path: Path | None = None) -> Path:
    root = root_path or application_root()
    return root / CONFIG_ML_PATH_DEFAULT


def cargar_config_mercadolibre(root_path: Path | None = None) -> dict[str, Any]:
    """Carga la configuración de la API de Mercado Libre desde disco o variables de entorno."""
    ruta = _obtener_ruta_config_ml(root_path)
    res = {
        "app_id": "",
        "client_secret": "",
        "seller_id": "",
        "access_token": "",
        "refresh_token": "",
        "activo": False,
        "filtro_estado": "paid",
        "horas_atras": 48,
        "auto_descontar": False,
        "ultima_sincronizacion": "",
    }
    necesita_migracion = False
    if ruta.exists():
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                data = json.load(f)
                raw_secretos = {
                    campo: str(data.get(campo, "")).strip()
                    for campo in _CAMPOS_SECRETOS_ML
                }
                necesita_migracion = any(
                    val and not secretos.esta_cifrado(val)
                    for val in raw_secretos.values()
                )
                secretos_descifrados: dict[str, str] = {}
                for campo, raw_val in raw_secretos.items():
                    try:
                        secretos_descifrados[campo] = secretos.descifrar(raw_val)
                    except secretos.SecretoError:
                        secretos_descifrados[campo] = ""

                res = {
                    "app_id": str(data.get("app_id", "")).strip(),
                    "client_secret": secretos_descifrados["client_secret"],
                    "seller_id": str(data.get("seller_id", "")).strip(),
                    "access_token": secretos_descifrados["access_token"],
                    "refresh_token": secretos_descifrados["refresh_token"],
                    "activo": bool(data.get("activo", False)),
                    "filtro_estado": str(data.get("filtro_estado", "paid")).strip() or "paid",
                    "horas_atras": int(data.get("horas_atras", 48)),
                    "auto_descontar": bool(data.get("auto_descontar", False)),
                    "ultima_sincronizacion": str(data.get("ultima_sincronizacion", "")),
                }
        except Exception:
            pass

    if necesita_migracion:
        try:
            guardar_config_mercadolibre(res, root_path=root_path)
        except Exception:
            pass

    for clave, env_nombres in [
        ("app_id", ["STOCKAGENT_MELI_APP_ID", "MELI_APP_ID"]),
        ("client_secret", ["STOCKAGENT_MELI_CLIENT_SECRET", "MELI_CLIENT_SECRET"]),
        ("seller_id", ["STOCKAGENT_MELI_SELLER_ID", "MELI_SELLER_ID"]),
        ("access_token", ["STOCKAGENT_MELI_ACCESS_TOKEN", "MELI_ACCESS_TOKEN"]),
        ("refresh_token", ["STOCKAGENT_MELI_REFRESH_TOKEN", "MELI_REFRESH_TOKEN"]),
    ]:
        if not res.get(clave):
            for env_nombre in env_nombres:
                val = os.environ.get(env_nombre)
                if val:
                    res[clave] = val.strip()
                    break

    return res


def guardar_config_mercadolibre(config: dict[str, Any], root_path: Path | None = None) -> None:
    """Persiste la configuración de la API de Mercado Libre en disco cifrando secretos."""
    ruta = _obtener_ruta_config_ml(root_path)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    a_guardar = dict(config)
    for campo in _CAMPOS_SECRETOS_ML:
        a_guardar[campo] = secretos.cifrar(str(a_guardar.get(campo) or "").strip())
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(a_guardar, f, indent=2, ensure_ascii=False)


def renovar_token_ml(
    config: dict[str, Any], root_path: Path | None = None
) -> tuple[bool, str, str]:
    """Renueva el Access Token de Mercado Libre utilizando el Refresh Token y Client Secret."""
    app_id = config.get("app_id", "").strip()
    client_secret = config.get("client_secret", "").strip()
    refresh_token = config.get("refresh_token", "").strip()

    if not app_id or not client_secret or not refresh_token:
        return False, "Faltan App ID, Client Secret o Refresh Token para renovar el token.", ""

    url = f"{API_BASE_URL}/oauth/token"
    payload = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "client_id": app_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "StockAgent/2.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            nuevo_access = str(data.get("access_token", ""))
            nuevo_refresh = str(data.get("refresh_token", refresh_token))
            user_id = str(data.get("user_id", ""))

            if not nuevo_access:
                return False, "Mercado Libre no retornó un access_token válido.", ""

            config["access_token"] = nuevo_access
            config["refresh_token"] = nuevo_refresh
            if user_id and not config.get("seller_id"):
                config["seller_id"] = user_id

            guardar_config_mercadolibre(config, root_path=root_path)
            return True, "Token renovado exitosamente.", nuevo_access

    except urllib.error.HTTPError as he:
        detalle = he.read().decode("utf-8", errors="ignore")
        return False, f"Error HTTP {he.code} al renovar token: {detalle}", ""
    except Exception as e:
        return False, f"Error de conexión al renovar token: {e}", ""


def verificar_credenciales_ml(
    config: dict[str, Any] | None = None, root_path: Path | None = None
) -> tuple[bool, str, dict[str, Any]]:
    """Comprueba la validez del Access Token consultando el perfil del usuario autenticado (/users/me)."""
    cfg = config or cargar_config_mercadolibre(root_path)
    token = cfg.get("access_token", "").strip()

    if not token:
        return False, "Falta ingresar el Access Token de Mercado Libre.", {}

    url = f"{API_BASE_URL}/users/me"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "StockAgent/2.0",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            nickname = data.get("nickname", "Desconocido")
            user_id = data.get("id", "")

            # Guardar automáticamente el seller_id si no estaba cargado
            if user_id and not cfg.get("seller_id"):
                cfg["seller_id"] = str(user_id)
                guardar_config_mercadolibre(cfg, root_path=root_path)

            return True, f"Conexión exitosa con la cuenta '{nickname}' (ID: {user_id})", data

    except urllib.error.HTTPError as he:
        if he.code == 401 and cfg.get("refresh_token"):
            # Intentar renovación automática
            exito_renov, msg_renov, nuevo_tok = renovar_token_ml(cfg, root_path=root_path)
            if exito_renov:
                cfg["access_token"] = nuevo_tok
                return verificar_credenciales_ml(cfg, root_path=root_path)
            return False, f"Token expirado y falló la renovación: {msg_renov}", {}
        return False, f"Error HTTP {he.code} de Mercado Libre: {he.reason}", {}
    except Exception as e:
        return False, f"Error de red al conectar con Mercado Libre: {e}", {}


def consultar_ordenes_ml(
    config: dict[str, Any] | None = None,
    horas: int = 48,
    limit: int = 50,
    root_path: Path | None = None,
) -> tuple[bool, str, list[dict[str, Any]]]:
    """Descarga de la API de Mercado Libre las órdenes recientes pagadas."""
    cfg = config or cargar_config_mercadolibre(root_path)
    token = cfg.get("access_token", "").strip()
    if not token:
        return False, "No hay Access Token configurado.", []

    seller_id = cfg.get("seller_id", "").strip()
    if not seller_id:
        # Intentar obtener el seller_id de la cuenta
        ok_conn, _, user_data = verificar_credenciales_ml(cfg, root_path=root_path)
        if ok_conn and user_data.get("id"):
            seller_id = str(user_data["id"])
            cfg["seller_id"] = seller_id
        else:
            seller_id = "me"

    fecha_desde = datetime.now() - timedelta(hours=horas)
    fecha_desde_iso = fecha_desde.strftime("%Y-%m-%dT%H:%M:%S.000-03:00")

    params = {
        "seller": seller_id,
        "order.status": cfg.get("filtro_estado", "paid"),
        "order.date_created.from": fecha_desde_iso,
        "sort": "date_desc",
        "limit": str(min(limit, 50)),
    }

    url = f"{API_BASE_URL}/orders/search?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "StockAgent/2.0",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])

            cfg["ultima_sincronizacion"] = datetime.now().isoformat()
            guardar_config_mercadolibre(cfg, root_path=root_path)

            return True, f"Se sincronizaron {len(results)} órdenes de Mercado Libre.", results

    except urllib.error.HTTPError as he:
        if he.code == 401 and cfg.get("refresh_token"):
            ok_renov, _, _ = renovar_token_ml(cfg, root_path=root_path)
            if ok_renov:
                return consultar_ordenes_ml(cfg, horas=horas, limit=limit, root_path=root_path)
        return False, f"Error HTTP {he.code} al consultar órdenes: {he.reason}", []
    except Exception as e:
        return False, f"Error al consultar órdenes de Mercado Libre: {e}", []
