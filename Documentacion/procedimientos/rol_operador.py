# -*- coding: utf-8 -*-
"""Generador de Manual de Procedimiento y Uso Botón por Botón para el Rol Operador."""

from __future__ import annotations

from pathlib import Path

from .fichas import (
    VERSION_PROC_ACTUAL,
    agregar_fichas_modulo,
    construir_cierre_manual_rol,
    iniciar_manual_rol,
)


def construir_manual_operador(ruta_destino: Path) -> Path:
    """Genera el Manual de Procedimiento y Uso Botón por Botón para el Rol Operador."""
    codigo_doc = "MAN-PROC-OPE-2026"
    titulo_doc = "Manual de Procedimiento y Uso de Botones (Rol Operador)"
    doc, est, story = iniciar_manual_rol(
        ruta_destino, codigo_doc, titulo_doc,
        "Rol Operador (Preparación de Pedidos, Escaneo, Despachos y Cierre de Jornada)",
        "Guía técnica y operativa botón por botón: funcionalidad detallada, flujo paso a paso, "
        "modificación de bases de datos, rótulos térmicos QR, hojas de ruta y operación segura en LAN HTTPS.",
    )

    agregar_fichas_modulo(
        story, est,
        "1. Alcance, Rol y Flujo Diario del Operador", [],
        intro_texto=(
            "El presente manual describe de forma procedimental cada comando visible para el perfil <b>Operador</b>. "
            "El operario de depósito recepciona remitos, prepara bultos, escanea inventario en vivo, procesa envíos "
            "de Mercado Libre y ejecuta de manera exclusiva el <b>Cierre de Jornada</b> con emisión de Hojas de Ruta."
        ),
    )

    agregar_fichas_modulo(
        story, est,
        "2. Botonera de Acceso Rápido (Entrada, Salida, Cargar Pedido y Mercado Libre)",
        [
            {
                "nombre_boton": "⚡ Entrada Rápida (+ Stock)",
                "icono_str": "[➕ Entrada]",
                "modulo": "ACCESO RÁPIDO (CABECERA)",
                "proposito_funcional": "Recepción instantánea por devoluciones, transferencias o sobrantes con modo pistoleo continuo y motivo tipificado obligatorio.",
                "datos_modificados": "Incremento atómico en SQLite (`productos.sqlite3`) y `Productos.xlsx`; asiento en `stock_movements` (`ingreso_rapido`), `logs_auditoria` y webhook saliente.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Entrada'</b> en la cabecera (o F2 / Ctrl+K -> 'Entrada Rápida').",
                    "Escanear el código de barras con pistola o tipear SKU y presionar Enter.",
                    "Confirmar cantidad o botones rápidos (+1, +5, +10, +50) o habilitar modo pistoleo continuo.",
                    "Seleccionar el motivo obligatorio y presionar <b>'Confirmar Entrada'</b>.",
                ],
                "resultado_obtenido": "Aumento atómico inmediato del stock disponible con trazabilidad forense.",
                "validaciones_advertencias": "Motivo estrictamente obligatorio. Si el código no existe, emite alerta sonora de error.",
            },
            {
                "nombre_boton": "⚡ Salida Rápida (- Stock)",
                "icono_str": "[➖ Salida]",
                "modulo": "ACCESO RÁPIDO (CABECERA)",
                "proposito_funcional": "Baja inmediata por roturas, mermas, muestras comerciales, consumo interno o devoluciones a proveedor con motivo obligatorio.",
                "datos_modificados": "Decremento en `productos.sqlite3` y `Productos.xlsx`; asiento en `stock_movements` (`salida_rapida`), auditoría y evento webhook.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Salida'</b> en la cabecera (o F2 / Ctrl+K -> 'Salida Rápida').",
                    "Escanear código de barras o tipear SKU y revisar stock proyectado.",
                    "Indicar cantidad, seleccionar motivo obligatorio y presionar <b>'Confirmar Salida'</b>.",
                ],
                "resultado_obtenido": "Descuento inmediato del inventario con auditoría de usuario y motivo.",
                "validaciones_advertencias": "Si la salida dejase el saldo negativo, el sistema advierte preventivamente en rojo.",
            },
            {
                "nombre_boton": "📄 Cargar Pedido",
                "icono_str": "[➕ Pedido]",
                "modulo": "ACCESO RÁPIDO (CABECERA)",
                "proposito_funcional": "Acceso directo prioritario para escanear y cargar remitos mayoristas o planillas de canje de preparación inmediata.",
                "datos_modificados": "Inserta pedido en `pedidos` (estado 'Preparado'), descuenta stock en SQLite y resguarda copia en `data/pedidos_archivos/`.",
                "pasos_procedimiento": [
                    "Pulsar el botón azul <b>'Cargar Pedido'</b> en la botonera superior.",
                    "Adjuntar el remito PDF/Excel, verificar cliente y asignar transporte/bultos.",
                    "Confirmar con <b>'Cargar y Descontar'</b>.",
                ],
                "resultado_obtenido": "Pedido descontado en tiempo real sin desplegar secciones laterales.",
                "validaciones_advertencias": "Valida hash SHA-256 anti-duplicados y suficiencia de stock.",
            },
            {
                "nombre_boton": "🛍️ Mercado Libre",
                "icono_str": "[🛒 MeLi]",
                "modulo": "ACCESO RÁPIDO (CABECERA)",
                "proposito_funcional": "Acceso directo para escanear paquetes con pistola o cargar comprobantes DOCX de Mercado Libre.",
                "datos_modificados": "Descuenta existencias en SQLite y `Productos.xlsx` con auditoría y hash SHA-256.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Mercado Libre'</b> en la cabecera.",
                    "Escanear ítems con el lector (EAN-13 / SKU) o cambiar a pestaña Archivo (.docx).",
                    "Confirmar el descuento y emitir rótulos de envío si corresponde.",
                ],
                "resultado_obtenido": "Despacho ágil e-commerce con confirmación acústica 880 Hz.",
                "validaciones_advertencias": "Requiere códigos catalogados en el maestro de productos.",
            },
        ],
        intro_texto="Ubicada permanentemente en la cabecera, reúne las 4 operaciones de mayor frecuencia en el depósito.",
    )

    agregar_fichas_modulo(
        story, est,
        "3. Módulos: ENTRADA DE MERCADERÍA, PREPARACIÓN Y DESPACHO",
        [
            {
                "nombre_boton": "Ingreso de Fábrica",
                "icono_str": "[📥]",
                "modulo": "ENTRADA DE MERCADERÍA",
                "proposito_funcional": "Recepción ágil de mercadería entrante de planta mediante lector de barras/SKU, bultos múltiplos de 12 y ajustes (+/-).",
                "datos_modificados": "Incremento atómico en `productos.sqlite3` y `Productos.xlsx`; historial `stock_movements` (`ingreso_fabrica`).",
                "pasos_procedimiento": [
                    "Pulsar <b>'Ingreso de Fábrica'</b> en el menú lateral.",
                    "Elegir lote de entrada ([12], [24], [36], [48], [60], [120]) o ajustar (+/-).",
                    "Pistolear cada código y pulsar <b>'Confirmar Ingreso a Depósito'</b>.",
                ],
                "resultado_obtenido": "Existencias actualizadas en depósito para su despacho inmediato.",
                "validaciones_advertencias": "El rol Operador únicamente suma ingresos; sobrescribir stock está reservado a Administrador.",
            },
            {
                "nombre_boton": "Cargar / Armar Pedido",
                "icono_str": "[➕]",
                "modulo": "PREPARACIÓN Y DESPACHO",
                "proposito_funcional": "Carga formal de Remito PDF o Planilla de Canje Excel con cálculo de bultos, transporte y fecha de retiro.",
                "datos_modificados": "Inserta en `pedidos` (`cierre_id = NULL`), decrementa existencias en SQLite y guarda comprobante en `data/pedidos_archivos/`.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Cargar / Armar Pedido'</b> en el panel lateral.",
                    "Adjuntar comprobante .pdf o .xlsx y validar razón social separada del código de cliente.",
                    "Ajustar bultos (`[-]` / `[+]`), elegir empresa de logística y validar fecha de retiro.",
                    "Pulsar <b>'Cargar y Descontar'</b> (confirmación sonora 880 Hz).",
                ],
                "resultado_obtenido": "Pedido listo para rotulación QR y sumado al contador pendiente de Cierre de Jornada.",
                "validaciones_advertencias": "Verifica hash criptográfico SHA-256 para bloquear comprobantes ya procesados.",
            },
            {
                "nombre_boton": "Descontar Mercado Libre",
                "icono_str": "[🏪]",
                "modulo": "PREPARACIÓN Y DESPACHO",
                "proposito_funcional": "Despacho de órdenes de Mercado Libre en modo Escáner en Vivo (con botón Undo) o carga de archivos DOCX.",
                "datos_modificados": "Deducción en SQLite y `Productos.xlsx`, creación del pedido `docx` con hash SHA-256.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Descontar Mercado Libre'</b>.",
                    "Pistolear códigos de barras (usar <b>'↩️ Deshacer Último'</b> si hubo lectura errónea).",
                    "Ingresar opcionalmente guía y destinatario y pulsar <b>'Confirmar y Descontar'</b>.",
                ],
                "resultado_obtenido": "Descuento exacto unitario y rótulos térmicos o A4 a 1 clic.",
                "validaciones_advertencias": "Emite alerta acústica grave si el SKU no existe y advertencia ámbar si entra en quiebre.",
            },
            {
                "nombre_boton": "Descontar Mercado Full",
                "icono_str": "[🚚]",
                "modulo": "PREPARACIÓN Y DESPACHO",
                "proposito_funcional": "Procesa transferencias en bloque hacia centros de fulfillment Mercado Libre Full desde planilla Excel oficial.",
                "datos_modificados": "Descuento masivo de depósito central y registro en tabla de pedidos con logística 'Mercado Libre Full'.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Descontar Mercado Full'</b> y adjuntar planilla .xlsx.",
                    "Verificar unidades totales y bultos y presionar <b>'Procesar Envío Full'</b>.",
                ],
                "resultado_obtenido": "Documento de descuento consolidado y rótulos de bulto.",
                "validaciones_advertencias": "Verifica suficiencia previa de existencias antes de confirmar la transferencia.",
            },
            {
                "nombre_boton": "Historial de Pedidos y Reimpresión",
                "icono_str": "[🧾]",
                "modulo": "PREPARACIÓN E INFORMES",
                "proposito_funcional": "Reimpresión de comprobantes, rótulos QR (A4 o térmico 80 mm), edición de bultos/transporte y anulación/desarme de pedidos.",
                "datos_modificados": "Tabla `pedidos` (actualiza bultos, chofer, fecha, estado DESPACHADO o restituye stock al desarmar).",
                "pasos_procedimiento": [
                    "Abrir <b>'Historial de Pedidos'</b> desde el menú lateral o la paleta F2.",
                    "Filtrar por cliente, remito o estado; usar acciones Ver Detalle, Rótulos QR, Editar o Anular/Desarmar.",
                ],
                "resultado_obtenido": "Reimpresión directa y trazabilidad completa de pedidos del turno.",
                "validaciones_advertencias": "Edición y desarme permitidos solo en pedidos sin `cierre_id` asignado.",
            },
            {
                "nombre_boton": "Gestión de Clientes",
                "icono_str": "[👤]",
                "modulo": "CLIENTES",
                "proposito_funcional": "Consulta, alta y actualización del directorio comercial de clientes y transportes habituales.",
                "datos_modificados": "Tabla `clientes` (razón social, CUIT, teléfono, dirección y transporte preferido).",
                "pasos_procedimiento": [
                    "Pulsar <b>'Gestión de Clientes'</b>.",
                    "Buscar cliente o pulsar <b>'Nuevo Cliente'</b>, completar datos y guardar.",
                ],
                "resultado_obtenido": "Padrón actualizado para autocompletado de remitos.",
                "validaciones_advertencias": "No se admiten razones sociales duplicadas.",
            },
        ],
    )

    agregar_fichas_modulo(
        story, est,
        "4. Módulo: CONTROL DE DEPÓSITO Y CIERRE DE JORNADA",
        [
            {
                "nombre_boton": "Inventario en Vivo (Escáner)",
                "icono_str": "[📷]",
                "modulo": "CONTROL Y CIERRE",
                "proposito_funcional": "Conteo físico rápido mediante cámara móvil o pistola USB (EAN-13 / SKU) para comparar existencias en estanterías.",
                "datos_modificados": "Sesión de relevamiento físico en memoria/SQLite para auditoría de diferencias.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Inventario en Vivo (Escáner)'</b>.",
                    "Escanear códigos de barra o ajustar cajas (+12 / +24).",
                    "Presionar <b>'Guardar Conteo'</b> al concluir la ronda.",
                ],
                "resultado_obtenido": "Relevamiento físico digitalizado en tiempo real.",
                "validaciones_advertencias": "Alerta sonora inmediata ante códigos no catalogados.",
            },
            {
                "nombre_boton": "Cierre de Jornada",
                "icono_str": "[✅]",
                "modulo": "CONTROL Y CIERRE",
                "proposito_funcional": "Función exclusiva del Operador. Exhibe contador vivo `'Cierre de Jornada (N)'`, consolida pedidos preparados pendientes, sincroniza `Productos.xlsx`, genera informe PDF/Excel y emite Hoja de Ruta.",
                "datos_modificados": "Crea registro en `cierres_jornada`, vincula pedidos con `cierre_id`, vuelca a `Productos.xlsx` y emite `Cierre_#ID.pdf` y `Hoja_Ruta_#ID.pdf`.",
                "pasos_procedimiento": [
                    "Al finalizar el turno, pulsar <b>'Cierre de Jornada'</b> y revisar la pestaña Pendientes.",
                    "(Opcional) Indicar correo destinatario y pulsar <b>'Ejecutar Cierre de Jornada'</b>.",
                    "Imprimir Hoja de Ruta General o segmentada por transporte para firma del chofer.",
                ],
                "resultado_obtenido": "Consolidación contable del turno, copia de seguridad automática y bandeja lista para el turno siguiente.",
                "validaciones_advertencias": "Solo habilitado con pedidos pendientes. Tras cerrar, los pedidos quedan inmutables.",
            },
            {
                "nombre_boton": "Barra Móvil (Thumb Zone) y Semáforo LAN",
                "icono_str": "[📱]",
                "modulo": "ERGONOMÍA MÓVIL Y RED",
                "proposito_funcional": "Navegación inferior a una mano (<768 px) y búfer offline con sincronización `/api/v1/despacho/escanear-lote` más semáforo RTT (Verde/Amarillo/Rojo).",
                "datos_modificados": "Cola local offline sincronizada de forma atómica al recuperar señal Wi-Fi/LAN.",
                "pasos_procedimiento": [
                    "Supervisar el indicador LED superior (Verde <50 ms, Amarillo 50-200 ms, Rojo desconectado).",
                    "Ante cortes breves, continuar escaneando y pulsar <b>'SINCRONIZAR'</b> al reconectar.",
                ],
                "resultado_obtenido": "Continuidad operativa sin pérdida de lecturas en zonas ciegas.",
                "validaciones_advertencias": "Todos los lotes offline son revalidados en servidor al sincronizar.",
            },
        ],
        page_break=True,
    )

    agregar_fichas_modulo(
        story, est,
        "5. Módulos: INFORMES, PREFERENCIAS Y RED LOCAL HTTPS",
        [
            {
                "nombre_boton": "Centro de Reportes / Abrir Informe",
                "icono_str": "[📊]",
                "modulo": "INFORMES",
                "proposito_funcional": "Consulta el catálogo de informes PDF/Excel generados y los abre en el visor autenticado con token temporal `?dt=`.",
                "datos_modificados": "Ninguno (visualización segura mediante rutas autenticadas `/api/v1/documentos/`).",
                "pasos_procedimiento": [
                    "Pulsar <b>'Centro de Reportes'</b> o <b>'Abrir informe'</b> en el panel lateral.",
                    "Seleccionar el comprobante para abrirlo o descargarlo sobre HTTPS.",
                ],
                "resultado_obtenido": "Visualización protegida con token efímero HMAC.",
                "validaciones_advertencias": "Requiere sesión iniciada; los enlaces `?dt=` caducan automáticamente.",
            },
            {
                "nombre_boton": "Compartir por Correo / WhatsApp Web",
                "icono_str": "[✉️]",
                "modulo": "INFORMES",
                "proposito_funcional": "Envío rápido de comprobantes adjuntos vía SMTP cifrado o apertura de WhatsApp Web con resumen de despacho.",
                "datos_modificados": "Asienta registro de envío en `logs_auditoria`.",
                "pasos_procedimiento": [
                    "Elegir <b>'Compartir por correo'</b> (ingresar destinatario) o <b>'WhatsApp Web'</b>.",
                    "Confirmar despacho del mensaje al cliente o transportista.",
                ],
                "resultado_obtenido": "Notificación inmediata al destinatario.",
                "validaciones_advertencias": "Correo requiere configuración SMTP activa (custodiada por Master).",
            },
            {
                "nombre_boton": "Impresión Térmica Directa y Manual de Uso (?dt=)",
                "icono_str": "[🖨️]",
                "modulo": "HERRAMIENTAS Y ACCESO LAN",
                "proposito_funcional": "Envía rótulos 100x150 mm directo al Spooler Windows (`user_preferences`) y abre el PDF oficial vía `/documentacion/Manual_Operador.pdf?dt=...`. En PC cliente de red local se utiliza `crear_acceso_directo_cliente.bat` sobre HTTPS (puerto 8550, Firewall Privado).",
                "datos_modificados": "Tabla `user_preferences` en SQLite.",
                "pasos_procedimiento": [
                    "En 'Preferencias de Interfaz', activar Spooler directo y seleccionar impresora térmica.",
                    "Para obtener esta guía actualizada, pulsar <b>'Manual de Uso'</b> (URL firmada `?dt=`).",
                ],
                "resultado_obtenido": "Impresión instantánea y manual oficial vigente en un clic.",
                "validaciones_advertencias": "Si una PC cliente muestra alerta SSL, instalar `data/certs/stockagent.crt` con `instalar_certificado.bat`.",
            },
        ],
    )

    return construir_cierre_manual_rol(
        doc, story, est, codigo_doc, titulo_doc, ruta_destino,
        incluir_distribucion=True, incluir_acta=True, version=VERSION_PROC_ACTUAL,
    )
