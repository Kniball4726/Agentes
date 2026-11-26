# -*- coding: utf-8 -*-
"""Generador de Manual de Procedimiento y Uso Botón por Botón para el Rol Master."""

from __future__ import annotations

from pathlib import Path

from .fichas import (
    VERSION_PROC_ACTUAL,
    agregar_fichas_modulo,
    construir_cierre_manual_rol,
    iniciar_manual_rol,
)


def construir_manual_master(ruta_destino: Path) -> Path:
    """Genera el Manual de Procedimiento y Uso Botón por Botón para el Rol Master."""
    codigo_doc = "MAN-PROC-MST-2026"
    titulo_doc = "Manual de Procedimiento y Uso de Botones (Rol Master)"
    doc, est, story = iniciar_manual_rol(
        ruta_destino, codigo_doc, titulo_doc,
        "Rol Master (Seguridad de la Información, Auditoría Forense, API y Resguardo)",
        "Guía técnica botón por botón: gestión IAM suprema, auditoría inmutable, rollback documental, "
        "secretos cifrados DPAPI/Fernet, API REST segura (Swagger apagado por defecto), HTTPS TLS y acceso LAN Privado.",
    )

    agregar_fichas_modulo(
        story, est,
        "1. Principios de Seguridad y Segregación SoD (Rol Master)", [],
        intro_texto=(
            "El rol <b>Master</b> (`Auditoria`) es la máxima autoridad técnica y de seguridad. Bajo Segregación de Funciones "
            "(ISO/IEC 27001 §5.3), no realiza tareas operativas de pedidos ni stock para conservar imparcialidad forense. "
            "Administra IAM, auditoría inmutable, respaldos, rollback, integraciones cifradas, HTTPS TLS y control de API REST."
        ),
    )

    agregar_fichas_modulo(
        story, est,
        "2. Panel de Acceso Rápido Master (Seguridad & IAM)",
        [
            {
                "nombre_boton": "Gestionar usuarios",
                "icono_str": "[🔐 Usuarios]",
                "modulo": "ACCESO RÁPIDO / SEGURIDAD",
                "proposito_funcional": "Aprovisionamiento integral de cuentas (Administrador, Operador, Picker, Despachador y Consulta), reseteo con cambio obligatorio, desbloqueo y alta/baja de administradores.",
                "datos_modificados": "Tabla `users` en SQLite con PBKDF2-SHA256 (600.000 iteraciones) y evento en `logs_auditoria`.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Gestionar usuarios'</b> en cabecera o menú SEGURIDAD Y ACCESOS.",
                    "Seleccionar cuenta, asignar rol (incluye promoción exclusiva a Administrador, Picker o Despachador) o resetear clave temporal con confirmación destructiva.",
                ],
                "resultado_obtenido": "Control IAM centralizado con cumplimiento estricto de SoD.",
                "validaciones_advertencias": "La cuenta Master raíz está protegida contra eliminación o degradación.",
            },
            {
                "nombre_boton": "Registro de Auditoría",
                "icono_str": "[🛡️ Auditoría]",
                "modulo": "ACCESO RÁPIDO / SEGURIDAD",
                "proposito_funcional": "Consola forense de lectura con tarjetas responsivas sobre la bitácora inmutable de accesos, bloqueos por fuerza bruta, descuentos, cambios de stock, desarmado/eliminación de pedidos (`DESARMAR_PEDIDO`, `ELIMINAR_PEDIDO`), despachos y rollbacks.",
                "datos_modificados": "Ninguno (lectura protegida de `logs_auditoria` append-only).",
                "pasos_procedimiento": [
                    "Pulsar <b>'Registro de Auditoría'</b>.",
                    "Filtrar por usuario, acción (`CIERRE_JORNADA`, `ELIMINAR_PEDIDO`, `LOGIN_FALLIDO`, `RESTAURAR`) o fecha y exportar.",
                ],
                "resultado_obtenido": "Inspección forense en tiempo real con IP y marca de tiempo.",
                "validaciones_advertencias": "Los registros de auditoría no admiten borrado ni modificación por ningún usuario.",
            },
        ],
    )

    agregar_fichas_modulo(
        story, est,
        "3. Módulos: DATOS, RESGUARDO E INTEGRACIONES CIFRADAS",
        [
            {
                "nombre_boton": "Copia de Seguridad / Restaurar documentos / Archivado Histórico",
                "icono_str": "[💾]",
                "modulo": "DATOS Y RESGUARDO",
                "proposito_funcional": "Respaldos `.zip` en `data/backups/`, potestad exclusiva Master para rollback documental de lotes erróneos y migración de históricos hacia `historico.sqlite3` con `VACUUM`.",
                "datos_modificados": "Archivos `.zip`, reposición atómica de SQLite / `Productos.xlsx` o compactación histórica.",
                "pasos_procedimiento": [
                    "En <b>'Copia de Seguridad'</b>, generar respaldo íntegro o configurar espejo de red.",
                    "En <b>'Restaurar documentos'</b>, previsualizar el rollback autorizado y confirmar reposición (conexiones SQLite con `closing()` en `src/core/sqlite_utils.py`).",
                    "En <b>'Archivado Histórico'</b>, definir fecha de corte y ejecutar compactación.",
                ],
                "resultado_obtenido": "Continuidad operativa, recuperación ante errores críticos y base operativa ágil.",
                "validaciones_advertencias": "Todo rollback queda asentado con usuario Master en auditoría forense.",
            },
            {
                "nombre_boton": "Configuración SMTP / Alertas Telegram / Mercado Libre API",
                "icono_str": "[⚙️]",
                "modulo": "INTEGRACIONES (CIFRADO DPAPI/FERNET)",
                "proposito_funcional": "Configuración de correo saliente institucional con TLS estricto, Bot de Telegram con escape HTML anti-inyección y credenciales OAuth 2.0 de Mercado Libre.",
                "datos_modificados": "Almacena credenciales cifradas localmente vía `src/secretos.py` (DPAPI `enc:dpapi:` en Windows o Fernet `enc:fernet:` con `data/.clave_secretos`), enmascarando en la UI los secretos ya guardados.",
                "pasos_procedimiento": [
                    "Abrir <b>'Configuración SMTP'</b>, <b>'Alertas Telegram'</b> o <b>'Mercado Libre API (Credenciales)'</b>.",
                    "Cargar credenciales (los secretos existentes nunca se pre-rellenan en claro en los campos de texto; dejar vacío conserva el secreto guardado).",
                    "Ejecutar prueba asíncrona de envío/conexión y guardar.",
                ],
                "resultado_obtenido": "Notificaciones y sincronización externa operando sin exponer secretos en disco ni en el DOM/WebSocket.",
                "validaciones_advertencias": "No compartir `.clave_secretos` ni claves `.env` fuera del servidor principal.",
            },
        ],
        page_break=True,
    )

    agregar_fichas_modulo(
        story, est,
        "4. Módulo: API REST, ENDURECIMIENTO HTTPS Y CONCURRENCIA LAN",
        [
            {
                "nombre_boton": "Documentación y Estado (Swagger protegido)",
                "icono_str": "[🚀]",
                "modulo": "API REST Y SERVICIOS",
                "proposito_funcional": "Monitoriza el estado HTTPS/TLS, IP LAN/Tailscale, puerto `8550` y rutas FastAPI. Por endurecimiento de red, `/docs`, `/redoc` y `/openapi.json` están <b>deshabilitados por defecto</b> (`STOCKAGENT_ENABLE_API_DOCS=0`).",
                "datos_modificados": "Ninguno (telemetría de servicio y estado de documentación OpenAPI).",
                "pasos_procedimiento": [
                    "Pulsar <b>'Documentación y Estado'</b> para validar esquema activo (`HTTPS` por defecto), IP LAN/Tailscale y estado de OpenAPI.",
                    "Solo si se requiere depuración local temporal, definir `STOCKAGENT_ENABLE_API_DOCS=1` en `.env` y reiniciar.",
                ],
                "resultado_obtenido": "Superficie de exposición mínima en red local al mantener Swagger desactivado en producción.",
                "validaciones_advertencias": "Desactivar nuevamente `STOCKAGENT_ENABLE_API_DOCS=0` al concluir pruebas técnicas.",
            },
            {
                "nombre_boton": "Gestión de Claves API y Sesiones de API Activas",
                "icono_str": "[🔑]",
                "modulo": "API REST Y SERVICIOS",
                "proposito_funcional": "Emisión y revocación de API Keys (`sk_live_...` con hash SHA-256) y expulsión remota de sesiones JWT activas.",
                "datos_modificados": "Tablas `api_keys` y registro de sesiones revocadas.",
                "pasos_procedimiento": [
                    "En <b>'Gestión de Claves API'</b>, emitir llave con rol mínimo necesario y copiarla (solo visible una vez).",
                    "En <b>'Sesiones de API Activas'</b>, auditar terminales conectadas o revocar sesiones no autorizadas.",
                ],
                "resultado_obtenido": "Integraciones ERP/móviles autenticadas con control granular de revocación.",
                "validaciones_advertencias": "Las claves API y JWT respetan rate-limiting y separación SoD.",
            },
            {
                "nombre_boton": "Hardening de Red LAN, PKI CA+Hoja (<=397d), OTA SHA-256 y Tokens ?dt=",
                "icono_str": "[🔒]",
                "modulo": "INFRAESTRUCTURA DE SEGURIDAD",
                "proposito_funcional": "Documenta la arquitectura perimetral: PKI local con CA raíz (`stockagent-ca.crt`) y certificado hoja TLS <= 397 días (`stockagent.crt`), cabeceras CSP/HSTS/Referrer-Policy, Firewall Windows en perfil <b>Privado</b>, OTA móvil con firma `SHA-256` y descarga protegida con HMAC `?dt=`.",
                "datos_modificados": "Regla de firewall `StockAgent Web (Puerto 8550)`, certificados X.509 en `data/certs/` y `version.json` con hash `sha256`.",
                "pasos_procedimiento": [
                    "En la PC Servidor, ejecutar `configurar_firewall_red.bat` para habilitar TCP 8550 solo en perfil Privado.",
                    "En PCs cliente LAN, ejecutar `crear_acceso_directo_cliente.bat` e `instalar_certificado.bat` (instala `stockagent-ca.crt`).",
                    "En terminales móviles (`stockagent_mobile`), conectar por HTTPS con Certificate Pinning (TOFU) y almacén cifrado `AndroidKeyStore`.",
                ],
                "resultado_obtenido": "Red local cifrada extremo a extremo, APK verificado con SHA-256 y archivos inaccesibles sin sesión o token `?dt=`.",
                "validaciones_advertencias": "La cola de concurrencia (soft-locks TTL 5 min), idempotencia SHA-256 y heartbeat RTT 12s con limpieza automática en `on_disconnect` operan de forma autónoma.",
            },
        ],
    )

    return construir_cierre_manual_rol(
        doc, story, est, codigo_doc, titulo_doc, ruta_destino,
        incluir_distribucion=True, incluir_acta=False, version=VERSION_PROC_ACTUAL,
    )
