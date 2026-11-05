# -*- coding: utf-8 -*-
"""Manuales de Procedimiento y Uso Operativo Botón por Botón de StockAgent.

Estructurados por roles de usuario (Operador, Administrador, Master y Consulta),
conforme a las directrices de manuales procedimentales de usuario:
- Ficha técnica de cada botón e ícono de la interfaz.
- Funcionalidad y propósito exacto.
- Datos y archivos que modifica (SQLite, Productos.xlsx, PDFs, logs).
- Procedimiento operativo paso a paso (secuencia de uso).
- Resultado obtenido y comprobantes generados.
- Reglas de validación, permisos y tratamiento de errores.
"""

import sys
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

# Asegurar rutas de importación tanto si se ejecuta directo como si se importa como paquete
_doc_dir = Path(__file__).resolve().parent
_root_dir = _doc_dir.parent
for _p in [str(_doc_dir), str(_root_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

try:
    from generar_manual_pdf import (
        ANCHO_UTIL,
        COLOR_ACENTO_ROJO,
        COLOR_PRIMARIO,
        COLOR_SECUNDARIO,
        COLOR_TEXTO,
        MARGEN_DER,
        MARGEN_INF,
        MARGEN_IZQ,
        MARGEN_SUP,
        agregar_acta_capacitacion_personal,
        agregar_formulario_firmas_autorizadas_iso,
        agregar_matriz_distribucion_copias,
        agregar_portada_iso_upel,
        agregar_tarjeta_referencia_rapida,
        crear_canvas_iso_upel,
        obtener_estilos_iso_upel,
    )
except ImportError:
    from .generar_manual_pdf import (
        ANCHO_UTIL,
        COLOR_ACENTO_ROJO,
        COLOR_PRIMARIO,
        COLOR_SECUNDARIO,
        COLOR_TEXTO,
        MARGEN_DER,
        MARGEN_INF,
        MARGEN_IZQ,
        MARGEN_SUP,
        agregar_acta_capacitacion_personal,
        agregar_formulario_firmas_autorizadas_iso,
        agregar_matriz_distribucion_copias,
        agregar_portada_iso_upel,
        agregar_tarjeta_referencia_rapida,
        crear_canvas_iso_upel,
        obtener_estilos_iso_upel,
    )


def agregar_ficha_boton(
    story: list,
    est: dict,
    nombre_boton: str,
    icono_str: str,
    modulo: str,
    proposito_funcional: str,
    datos_modificados: str,
    pasos_procedimiento: list[str],
    resultado_obtenido: str,
    validaciones_advertencias: str = "",
) -> None:
    """Inserta una ficha estandarizada de procedimiento y uso por botón."""
    celda_titulo = Paragraph(
        f"<b>{escape(icono_str)} BOTÓN: <font color='#D32F2F'>{escape(nombre_boton.upper())}</font></b>",
        est["h2"],
    )
    celda_modulo = Paragraph(
        f"<b>Sección / Módulo:</b><br/><i>{escape(modulo)}</i>",
        est["meta_bold"],
    )

    celda_proposito = Paragraph(
        f"<b>1. ¿Qué hace y funcionalidad?</b><br/>{proposito_funcional}",
        est["body"],
    )
    celda_modifica = Paragraph(
        f"<b>2. Registros y archivos que modifica:</b><br/>{datos_modificados}",
        est["body"],
    )

    pasos_html = "<b>3. Procedimiento operativo paso a paso:</b><br/>"
    for i, p in enumerate(pasos_procedimiento, 1):
        pasos_html += f"<b>{i}.</b> {p}<br/>"
    celda_pasos = Paragraph(pasos_html.rstrip("<br/>"), est["body"])

    res_html = f"<b>4. Resultado obtenido / Comprobante:</b><br/>{resultado_obtenido}"
    if validaciones_advertencias:
        res_html += f"<br/><br/><b>5. Reglas y Advertencias:</b><br/>{validaciones_advertencias}"
    celda_resultado = Paragraph(res_html, est["body"])

    tabla_datos = [
        [celda_titulo, celda_modulo],
        [celda_proposito, celda_modifica],
        [celda_pasos, celda_resultado],
    ]

    t = Table(tabla_datos, colWidths=[9.0 * 28.3465, 6.5 * 28.3465])
    t.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
            ("LINEBELOW", (0, 0), (-1, 0), 1.2, COLOR_SECUNDARIO),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
    )
    story.append(KeepTogether([t]))
    story.append(Spacer(1, 6))


# =============================================================================
# 1. MANUAL ROL OPERADOR (BOTÓN POR BOTÓN)
# =============================================================================
def construir_manual_operador(ruta_destino: Path) -> Path:
    """Genera el Manual de Procedimiento y Uso Botón por Botón para el Rol Operador."""
    ruta_destino.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(ruta_destino),
        pagesize=A4,
        leftMargin=MARGEN_IZQ,
        rightMargin=MARGEN_DER,
        topMargin=MARGEN_SUP,
        bottomMargin=MARGEN_INF,
    )
    est = obtener_estilos_iso_upel()
    story = []

    codigo_doc = "MAN-PROC-OPE-2026"
    titulo_doc = "Manual de Procedimiento y Uso de Botones (Rol Operador)"

    agregar_portada_iso_upel(
        story, est, codigo_doc, titulo_doc,
        "Rol Operador (Preparación de Pedidos, Escaneo, Despachos y Cierre de Jornada)",
        "Guía técnica y operativa botón por botón: funcionalidad detallada, flujo paso a paso, "
        "modificación de bases de datos, generación de rótulos térmicos QR y emisión de hojas de ruta de despacho.",
        version="3.0.0",
    )

    story.append(Paragraph("1. Alcance, Rol y Flujo Diario del Operador", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))
    story.append(Paragraph(
        "El presente manual describe de forma exhaustiva y procedimental cada uno de los comandos y botones "
        "visibles en la interfaz gráfica para el perfil <b>Operador</b>. El operario de depósito es el responsable exclusivo "
        "de recepcionar remitos, preparar bultos, escanear existencias en vivo, procesar ventas de Mercado Libre y "
        "ejecutar el <b>Cierre de Jornada</b> diario con la generación de las Hojas de Ruta para transportistas.",
        est["body_sangria"],
    ))
    story.append(Spacer(1, 4))

    # CAPÍTULO 2: PEDIDOS EN TIEMPO REAL
    story.append(Paragraph("2. Módulo: PEDIDOS EN TIEMPO REAL (Botón por Botón)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    agregar_ficha_boton(
        story, est,
        nombre_boton="Ingreso de Fábrica",
        icono_str="[📥]",
        modulo="CONTROL DE DEPÓSITO",
        proposito_funcional="Recepción y registro ágil de mercadería entrante de fábrica mediante lector de código de barras o SKU, con soporte de bultos por lotes múltiplos de 12 y ajustes unitarios (+ / -).",
        datos_modificados="Incremento atómico de existencias en 'productos.sqlite3' y sincronización automática en 'Productos.xlsx'. Asiento en el historial 'stock_movements' (tipo 'ingreso_fabrica') y registro en la auditoría con trazabilidad del operario.",
        pasos_procedimiento=[
            "Pulsar <b>'Ingreso de Fábrica'</b> en la sección CONTROL DE DEPÓSITO.",
            "Configurar la cantidad por bulto/lectura: pulsar los botones rápidos de múltiplos de 12 (<b>[ 12 ]</b>, <b>[ 24 ]</b>, <b>[ 36 ]</b>, <b>[ 48 ]</b>, <b>[ 60 ]</b>, <b>[ 120 ]</b>) o usar los botones de ajuste fino <b>'+'</b> y <b>'−'</b> si entran unidades sueltas no múltiplos de 12 (ej. 13 o 14 un.).",
            "Posicionar la pistola lectora sobre el código de barras o escribir el código/SKU y presionar Enter (o el botón 'Ingresar').",
            "El sistema emite un bip de confirmación sonoro y muestra en pantalla el producto, el stock actual en depósito y el nuevo stock proyectado con el ingreso.",
            "Revisar la lista de productos escaneados: cada fila cuenta con controles rápidos para sumar o restar bultos completos (<b>[-12]</b> / <b>[+12]</b>) o unidades (<b>[-1]</b> / <b>[+1]</b>), y botón para descartar ítems.",
            "Pulsar <b>'Confirmar Ingreso a Depósito'</b> para impactar de inmediato el nuevo saldo en el inventario maestro.",
        ],
        resultado_obtenido="Mercadería ingresada y asentada de forma inmediata en las existencias digitales del depósito, lista para despachar o armar pedidos.",
        validaciones_advertencias="El rol Operador únicamente suma ingresos de mercadería (la opción de sobrescribir stock queda bloqueada por seguridad para prevenir alteraciones accidentales del inventario global). Si el código escaneado no existe, sonará un tono acústico de error.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Cargar / Armar Pedido",
        icono_str="[➕]",
        modulo="PEDIDOS EN TIEMPO REAL",
        proposito_funcional="Permite cargar un comprobante de pedido comercial (Remito en PDF o Planilla de Canje en Excel) para descontar el stock de los artículos y asentar el pedido en la jornada de depósito.",
        datos_modificados="Inserta un registro en la tabla <code>pedidos</code> con estado 'Preparado' y <code>cierre_id = NULL</code>. Decrementa las cantidades físicas en SQLite y guarda el archivo en <code>data/pedidos_archivos/</code>.",
        pasos_procedimiento=[
            "Pulsar el botón <b>'Cargar / Armar Pedido'</b> en el panel lateral.",
            "En la ventana emergente, presionar <b>'Seleccionar archivo'</b> y adjuntar el remito .pdf o planilla .xlsx.",
            "Verificar que el sistema detecte automáticamente el cliente y número de comprobante.",
            "Ajustar la cantidad de bultos físicos empaquetados mediante los pulsadores <b>[-]</b> y <b>[+]</b>.",
            "Seleccionar obligatoriamente el transporte o logística en la lista desplegable.",
            "Confirmar la fecha de retiro de la mercadería.",
            "Pulsar <b>'Cargar y Descontar'</b>. El sistema emitirá un sonido de 880 Hz confirmando la operación.",
        ],
        resultado_obtenido="Pedido registrado con éxito, actualización del stock en tiempo real, suma al contador de pedidos del turno y generación de opción para imprimir rótulos QR.",
        validaciones_advertencias="El sistema verifica el hash criptográfico SHA-256 del comprobante: si el remito ya fue procesado anteriormente, se bloqueará la carga duplicada para evitar doble descuento.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Gestión de Clientes",
        icono_str="[👤]",
        modulo="PEDIDOS EN TIEMPO REAL",
        proposito_funcional="Abre el directorio integral de clientes para consultar fichas comerciales, direcciones de entrega, transportes habituales o dar de alta un nuevo cliente.",
        datos_modificados="Tabla <code>clientes</code> (inserción y actualización de razón social, CUIT, teléfono, dirección y logística preferida).",
        pasos_procedimiento=[
            "Hacer clic en <b>'Gestión de Clientes'</b>.",
            "Utilizar la barra de búsqueda superior para localizar un cliente por nombre o código.",
            "Para un cliente nuevo: presionar <b>'Nuevo Cliente'</b>, completar los campos obligatorios y pulsar <b>'Guardar Cliente'</b>.",
            "Para modificar: seleccionar el cliente de la lista y editar los datos de contacto o transporte.",
        ],
        resultado_obtenido="Directorio de clientes actualizado y sincronizado para autocompletado en la carga de pedidos.",
        validaciones_advertencias="No se permite registrar dos clientes con la misma razón social exacta.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Descontar Mercado Libre",
        icono_str="[🏪]",
        modulo="PEDIDOS EN TIEMPO REAL",
        proposito_funcional="Gestiona la salida y despacho de mercadería de Mercado Libre bajo dos modalidades: armado de paquetes en vivo ítem por ítem con pistola lectora de códigos de barra (EAN-13 o SKU) con feedback auditivo, o mediante la carga tradicional de comprobantes (.docx).",
        datos_modificados="Deducción atómica inmediata en SQLite ('productos.sqlite3') y en la planilla maestra 'Productos.xlsx'. Creación del pedido con tipo 'docx' en la base de datos de órdenes y generación del documento de respaldo con hash SHA-256.",
        pasos_procedimiento=[
            "Pulsar el botón <b>'Descontar Mercado Libre'</b> en la barra lateral.",
            "<b>Modo Escáner en Vivo (Predeterminado):</b> Posicionar el lector óptico sobre el código de barras (EAN-13) o tipear el SKU y presionar Enter. Cada lectura emite un pitido de confirmación y suma la unidad al paquete.",
            "Revisar la lista en pantalla: si se escaneó un código incorrecto por error, pulsar el botón <b>'Deshacer Último'</b> para revertir inmediatamente la última lectura, o ajustar cantidades con los botones '+' y '-'.",
            "Opcionalmente escanear o escribir el N° de Envío / Guía de Mercado Libre y el nombre del destinatario.",
            "Presionar <b>'Confirmar y Descontar'</b>. El sistema descontará el stock en vivo y ofrecerá la impresión con 1 clic de los rótulos térmicos o A4.",
            "<b>Modo Archivo DOCX:</b> Cambiar a la pestaña 'Cargar Archivo (.docx)', seleccionar el comprobante recibido de Mercado Libre y confirmar la deducción en lote.",
        ],
        resultado_obtenido="Stock descontado con exactitud unitaria, comprobante oficial guardado en 'data/pedidos_archivos/' y pedido sumado al panel en vivo del turno para el Cierre de Jornada.",
        validaciones_advertencias="Si el producto escaneado no existe en el catálogo, sonará una señal acústica de error y la lista no se modificará. Si el saldo restante queda en quiebre (<= 0), el sistema advertirá en color ámbar.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Deshacer Último Escaneo (Undo)",
        icono_str="[↩️]",
        modulo="PEDIDOS EN TIEMPO REAL",
        proposito_funcional="Permite al operario revertir de forma inmediata la última unidad escaneada en el módulo de Mercado Libre sin desarmar la preparación en curso ni perder el lote ya pistoleado.",
        datos_modificados="Buffer temporal de escaneo en memoria. Resta 1 unidad al contador del artículo o remueve la línea si la cantidad llega a cero.",
        pasos_procedimiento=[
            "Durante la ronda de pistoleo de paquetes de Mercado Libre, si se escanea por error un producto incorrecto o repetido, pulsar el botón <b>'[ ↩️ Deshacer Último ]'</b>.",
            "El sistema resta automáticamente la última unidad cargada y actualiza el contador de unidades.",
            "Se emite un tono acústico de confirmación de reversión.",
            "Continuar con el escaneo normal de los artículos correctos.",
        ],
        resultado_obtenido="Corrección instantánea de lecturas fallidas sin fricción ni tiempos muertos en la línea de empaque.",
        validaciones_advertencias="Solo se puede deshacer antes de presionar 'Confirmar y Descontar'. Si el carrito está vacío, el botón permanece inactivo.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Descontar Mercado Full",
        icono_str="[🚚]",
        modulo="PEDIDOS EN TIEMPO REAL",
        proposito_funcional="Procesa transferencias de stock en bloque destinadas al centro de almacenamiento y distribución de Mercado Libre Full.",
        datos_modificados="Descuento masivo de stock en depósito central. Asiento en la tabla de pedidos con logística 'Mercado Libre Full'.",
        pasos_procedimiento=[
            "Pulsar <b>'Descontar Mercado Full'</b>.",
            "Cargar la planilla oficial de envío a bodega Full (.xlsx).",
            "Verificar las unidades totales y los bultos calculados para la carga del camión.",
            "Presionar <b>'Procesar Envío Full'</b>.",
        ],
        resultado_obtenido="Documento consolidado de descuento y rótulos de bulto para el transporte a bodega Full.",
        validaciones_advertencias="Verificar que el saldo en depósito central cubra la totalidad de las unidades solicitadas por Full antes de confirmar.",
    )


    agregar_ficha_boton(
        story, est,
        nombre_boton="Historial de Pedidos",
        icono_str="[🧾]",
        modulo="PEDIDOS EN TIEMPO REAL",
        proposito_funcional="Permite supervisar, buscar, reimprimir comprobantes y rótulos, cambiar transportes o anular pedidos preparados en la jornada.",
        datos_modificados="Tabla <code>pedidos</code> (modificación de bultos, chofer, fecha de retiro, estado de despacho 'Preparado / Despachado' o anulación).",
        pasos_procedimiento=[
            "Pulsar <b>'Historial de Pedidos'</b>.",
            "Usar la barra de búsqueda por cliente, remito o logística, o usar los botones de filtro rápido.",
            "En cada tarjeta de pedido se dispone de acciones:",
            "  • <b>Ver Detalle</b>: Abre la ficha completa del pedido y sus ítems.",
            "  • <b>Rótulos QR</b>: Imprime las etiquetas adhesivas de despacho para pegar en cada caja.",
            "  • <b>Editar</b>: Modifica bultos, transporte o cliente (facultad exclusiva del operador).",
            "  • <b>Anular / Desarmar</b>: Si el pedido se cancela, se restituye el stock atómicamente a las existencias.",
        ],
        resultado_obtenido="Reimpresión instantánea de comprobantes y rótulos térmicos QR individuales o por lote.",
        validaciones_advertencias="Solo se pueden anular o editar pedidos que no hayan sido incluidos en un Cierre de Jornada definitivo.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Imprimir Descuento",
        icono_str="[🖨️]",
        modulo="PEDIDOS EN TIEMPO REAL",
        proposito_funcional="Acceso directo a la reimpresión del informe de descuento de cualquier comprobante procesado en el turno.",
        datos_modificados="Ninguno (operación de solo lectura y visualización documental).",
        pasos_procedimiento=[
            "Pulsar <b>'Imprimir Descuento'</b>.",
            "Seleccionar el pedido deseado en el listado desplegado.",
            "Hacer clic en el icono de impresora para enviar al visor PDF predeterminado.",
        ],
        resultado_obtenido="Apertura del comprobante oficial de descuento de stock en PDF.",
        validaciones_advertencias="El comprobante debe existir en el almacenamiento local del servidor.",
    )

    # CAPÍTULO 3: CONTROL DE DEPÓSITO
    story.append(PageBreak())
    story.append(Paragraph("3. Módulo: CONTROL DE DEPÓSITO (Botón por Botón)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    agregar_ficha_boton(
        story, est,
        nombre_boton="Inventario en Vivo (Escáner)",
        icono_str="[📷]",
        modulo="CONTROL DE DEPÓSITO",
        proposito_funcional="Habilita el modo de conteo físico rápido de inventario mediante la cámara del teléfono celular o un lector óptico USB de códigos de barras (EAN-13 o SKU).",
        datos_modificados="Registra recuentos en la sesión de inventario en vivo para comparativa de existencias.",
        pasos_procedimiento=[
            "Pulsar <b>'Inventario en Vivo (Escáner)'</b>.",
            "Apuntar la cámara o pistola láser hacia el código de barras del producto.",
            "Al detectar el código, el sistema reproduce un bip de confirmación e incrementa el contador de unidades.",
            "Es posible graduar la cantidad manualmente si se cuenta una caja completa (ej. +12 o +24).",
            "Pulsar <b>'Guardar Conteo'</b> al finalizar la ronda de escaneo en la estantería.",
        ],
        resultado_obtenido="Auditoría física de existencias en tiempo real sin planillas impresas.",
        validaciones_advertencias="Si el código no está registrado en el catálogo maestro, el sistema emitirá un sonido grave de advertencia y solicitará darlo de alta.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Cierre de Jornada",
        icono_str="[✅]",
        modulo="CONTROL DE DEPÓSITO",
        proposito_funcional="Función central del Operador. El botón en la barra lateral exhibe en tiempo real el contador dinámico de pedidos pendientes entre paréntesis: 'Cierre de Jornada (N)'. Consolida todos los pedidos preparados pendientes, realiza el descuento consolidado de stock en Productos.xlsx, genera el informe de cierre y emite la Hoja de Ruta de Despacho para los choferes.",
        datos_modificados="Crea un registro en <code>cierres_jornada</code>, actualiza todos los pedidos pendientes asignándoles el <code>cierre_id</code>, vuelca existencias a Productos.xlsx y genera los archivos <code>Cierre_#ID.pdf</code> y <code>Hoja_Ruta_#ID.pdf</code>.",
        pasos_procedimiento=[
            "Al finalizar el turno o jornada de preparación, pulsar <b>'Cierre de Jornada'</b>.",
            "En la pestaña <b>'Pendientes'</b>, revisar el listado de pedidos listos y el total de artículos consolidados.",
            "(Opcional) Ingresar un correo electrónico si se desea enviar copia automática del cierre a administración.",
            "Hacer clic en el botón principal <b>'Ejecutar Cierre de Jornada'</b>.",
            "El sistema procesará el cierre, reiniciará los contadores y desplegará las opciones de Hoja de Ruta.",
            "Seleccionar si se imprime la <b>Hoja de Ruta General</b> o segmentada por chofer/transporte específico.",
            "En la pestaña <b>'Historial de Cierres'</b> se puede consultar o reimprimir cualquier cierre anterior.",
        ],
        resultado_obtenido="Emisión de Hoja de Ruta de Despacho en PDF, informe consolidado de cierre en PDF/Excel y bandeja de pedidos lista para el siguiente turno.",
        validaciones_advertencias="No se puede ejecutar el cierre si no hay pedidos preparados pendientes. Una vez cerrado, los pedidos no pueden ser modificados por el operador.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Barra de Navegación Móvil (Thumb Zone)",
        icono_str="[📱]",
        modulo="ERGONOMÍA MÓVIL Y DEPÓSITO",
        proposito_funcional="Barra inferior ergonómica adaptada a la zona natural del pulgar (Thumb Zone) en teléfonos celulares y colectores de datos Android, brindando acceso a un toque a los 5 destinos neurálgicos de la bodega.",
        datos_modificados="Navegación reactiva de la interfaz de usuario Flet.",
        pasos_procedimiento=[
            "Al acceder desde un teléfono celular o colector portátil, la interfaz activa automáticamente la barra inferior.",
            "Navegar con una sola mano entre los 5 accesos directos: 1) Pedidos (carga y remitos), 2) Escanear ML (despacho Mercado Libre en vivo), 3) Fábrica (recepción ágil), 4) Cierre (consolidación de turno), y 5) Chat (comunicación con equipo y asistente IA).",
            "El ítem seleccionado se resalta con iluminación de acento corporativo.",
        ],
        resultado_obtenido="Operación fluida a una sola mano en depósitos sin necesidad de alcanzar menús superiores.",
        validaciones_advertencias="Se activa automáticamente en pantallas con ancho menor a 768 píxeles.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Semáforo de Red y Resiliencia Offline",
        icono_str="[📡]",
        modulo="CONECTIVIDAD Y COMUNICACIONES",
        proposito_funcional="Supervisión en vivo de la calidad de señal Wi-Fi/LAN mediante semáforo de latencia y almacenamiento temporal en búfer local para escaneos realizados en zonas muertas de depósito.",
        datos_modificados="Buffer local 'colaOffline' en cliente móvil Flutter. Al sincronizar, invoca el endpoint batch '/api/v1/despacho/escanear-lote'.",
        pasos_procedimiento=[
            "Observar el indicador LED en la cabecera: Verde (<50 ms), Amarillo (50-200 ms) o Rojo (desconectado).",
            "Si el operario ingresa a un pasillo sin cobertura Wi-Fi, la app móvil retiene los escaneos localmente emitiendo vibración háptica de resguardo.",
            "Al retornar a una zona con cobertura, aparece el banner 'Modo Offline: N escaneos pendientes' con el botón '[ SINCRONIZAR ]'.",
            "Pulsar 'SINCRONIZAR' para procesar el lote completo de forma atómica en el servidor central.",
        ],
        resultado_obtenido="Cero pérdida de datos y continuidad ininterrumpida de preparación de despachos en galpones extensos.",
        validaciones_advertencias="El lote offline se valida criptográficamente en el servidor para evitar discrepancias de inventario.",
    )

    # CAPÍTULO 4: INFORMES Y COMUNICACIONES
    story.append(Paragraph("4. Módulo: INFORMES Y COMUNICACIONES", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    agregar_ficha_boton(
        story, est,
        nombre_boton="Abrir informe",
        icono_str="[↗️]",
        modulo="INFORMES",
        proposito_funcional="Abre directamente en el visor de documentos del sistema el último informe de descuento o cierre generado.",
        datos_modificados="Ninguno.",
        pasos_procedimiento=[
            "Hacer clic en <b>'Abrir informe'</b>.",
            "El sistema localiza el archivo más reciente en la carpeta de descuentos y lo lanza en pantalla.",
        ],
        resultado_obtenido="Visualización inmediata del documento PDF o planilla Excel.",
        validaciones_advertencias="Requiere haber procesado al menos un remito o cierre durante la sesión.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Compartir por correo",
        icono_str="[✉️]",
        modulo="INFORMES",
        proposito_funcional="Despliega el formulario de envío rápido para remitir por email los comprobantes a clientes o jefaturas.",
        datos_modificados="Asienta el evento de envío en la bitácora de auditoría.",
        pasos_procedimiento=[
            "Pulsar <b>'Compartir por correo'</b>.",
            "Indicar el correo de destino (o seleccionar uno predeterminado).",
            "Pulsar <b>'Enviar Correo'</b>.",
        ],
        resultado_obtenido="Envío por protocolo SMTP con el documento PDF adjunto.",
        validaciones_advertencias="Requiere que la configuración SMTP del sistema esté activa.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="WhatsApp Web",
        icono_str="[💬]",
        modulo="INFORMES",
        proposito_funcional="Abre una pestaña en el navegador con WhatsApp Web y un mensaje prediseñado con el detalle de despacho para enviar al cliente o transportista.",
        datos_modificados="Ninguno.",
        pasos_procedimiento=[
            "Pulsar <b>'WhatsApp Web'</b>.",
            "El navegador abrirá la conversación con el texto del despacho listo para enviar.",
        ],
        resultado_obtenido="Comunicación instantánea con el cliente notificando su entrega.",
        validaciones_advertencias="Requiere conexión a Internet y sesión activa en WhatsApp Web.",
    )

    # CAPÍTULO 5: TECLADO Y ATAJOS
    story.append(Spacer(1, 6))
    agregar_tarjeta_referencia_rapida(story, est)
    story.append(PageBreak())
    agregar_formulario_firmas_autorizadas_iso(story, est, 2)
    agregar_matriz_distribucion_copias(story, est, 3)
    agregar_acta_capacitacion_personal(story, est, 4)

    doc.build(story, canvasmaker=crear_canvas_iso_upel(codigo_doc, titulo_doc, "3.0.0"))
    return ruta_destino


# =============================================================================
# 2. MANUAL ROL ADMINISTRADOR (BOTÓN POR BOTÓN)
# =============================================================================
def construir_manual_administrador(ruta_destino: Path) -> Path:
    """Genera el Manual de Procedimiento y Uso Botón por Botón para el Rol Administrador."""
    ruta_destino.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(ruta_destino),
        pagesize=A4,
        leftMargin=MARGEN_IZQ,
        rightMargin=MARGEN_DER,
        topMargin=MARGEN_SUP,
        bottomMargin=MARGEN_INF,
    )
    est = obtener_estilos_iso_upel()
    story = []

    codigo_doc = "MAN-PROC-ADM-2026"
    titulo_doc = "Manual de Procedimiento y Uso de Botones (Rol Administrador)"

    agregar_portada_iso_upel(
        story, est, codigo_doc, titulo_doc,
        "Rol Administrador (Jefatura de Depósito, Compras, Catálogo y Supervisión)",
        "Guía técnica y operativa botón por botón: administración del catálogo maestro, entradas de fábrica, "
        "auditoría de cierres de operarios en orden descendente, radar de anomalías, métricas de picking y gestión de usuarios.",
        version="3.0.0",
    )

    story.append(Paragraph("1. Responsabilidades y Alcance del Rol Administrador", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))
    story.append(Paragraph(
        "El Administrador ejerce la supervisión integral de las existencias, compras y desempeño operativo de la bodega. "
        "Este manual describe el funcionamiento de los <b>22 comandos</b> disponibles para este rol, organizados en sus "
        "secciones clave: Catálogo y Stock, Ventas y Despachos (incluyendo la <b>nueva función de auditoría de cierres de operarios</b>), "
        "Analítica y Picking, Resguardo y Administración de Cuentas.",
        est["body_sangria"],
    ))
    story.append(Spacer(1, 4))

    # SECCIÓN 1: STOCK Y CATÁLOGO
    story.append(Paragraph("2. Módulo: STOCK Y CATÁLOGO (Botón por Botón)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    agregar_ficha_boton(
        story, est,
        nombre_boton="Gestionar productos",
        icono_str="[📦]",
        modulo="STOCK Y CATÁLOGO",
        proposito_funcional="Administración del catálogo maestro de productos: altas, bajas, modificaciones de descripciones, códigos SKU, códigos de barra EAN-13, precios de referencia, stock de seguridad y ubicación física en estanterías de depósito.",
        datos_modificados="Tabla <code>productos</code> en SQLite y sincronización hacia <code>Productos.xlsx</code>. Registro de auditoría por cada modificación.",
        pasos_procedimiento=[
            "Pulsar <b>'Gestionar productos'</b> en el panel lateral.",
            "Para un nuevo artículo: pulsar <b>'Nuevo Producto'</b>, rellenar SKU, descripción, código de barras, stock mínimo y máximo.",
            "Asignar la ubicación física en depósito (Rack, Módulo, Nivel) para facilitar el recorrido de picking.",
            "Para editar: buscar el producto en el listado, hacer clic en <b>'Editar'</b> y modificar los parámetros requeridos.",
            "Pulsar <b>'Guardar'</b> para asentar los cambios.",
        ],
        resultado_obtenido="Ficha técnica de producto actualizada en tiempo real y disponible para todos los operadores.",
        validaciones_advertencias="No se permiten códigos SKU duplicados. El stock mínimo debe ser mayor o igual a cero.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Ajustar stock / Fábrica",
        icono_str="[📥]",
        modulo="STOCK Y CATÁLOGO",
        proposito_funcional="Gestión integral de ingresos de fábrica y ajustes de inventario: admite escaneo rápido con pistola lectora de códigos de barra (lotes x12 y steppers unitarios +/-), procesamiento en lote de archivos de remito (.xlsx, .xls, .pdf) y corrección manual con opción de sobrescritura de stock.",
        datos_modificados="Incremento, decremento o fijación exacta de existencias en 'productos.sqlite3' y 'Productos.xlsx'. Trazabilidad completa en 'stock_movements' y auditoría.",
        pasos_procedimiento=[
            "Pulsar <b>'Ajustar stock / Fábrica'</b> en el panel lateral.",
            "<b>Pestaña Escáner / Carga Rápida:</b> Usar la pistola lectora o SKU, preconfigurando la botonera de lotes de 12 ([ 12 ], [ 24 ], [ 36 ], etc.) o los botones +/- para cantidades libres.",
            "<b>Pestaña Por Archivo (Fábrica):</b> Procesar de forma automática comprobantes Excel o PDF colocados en la carpeta 'Descuentos/Fabrica'.",
            "<b>Opción 'Sobrescribir stock' (Exclusivo Administrador):</b> Permite forzar el inventario al valor exacto ingresado en lugar de sumar, para regularizaciones o arqueos extraordinarios.",
            "Presionar <b>'Aplicar a stock'</b> o <b>'Confirmar Ingreso a Depósito'</b> para persistir los cambios.",
        ],
        resultado_obtenido="Actualización inmediata y segura del catálogo de productos y existencias físicas en depósito.",
        validaciones_advertencias="La opción de sobrescribir stock altera el saldo total; utilizar con precaución únicamente en conciliaciones respaldadas por inventario físico.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Comparativa stock físico",
        icono_str="[🔄]",
        modulo="STOCK Y CATÁLOGO",
        proposito_funcional="Herramienta de auditoría de inventario: compara planillas de conteos físicos reales contra las existencias registradas en el sistema, clasificando las diferencias en COINCIDE, FALTANTE o SOBRANTE.",
        datos_modificados="Genera informes comparativos en PDF y Excel sin alterar el stock de forma automática hasta que el administrador lo apruebe.",
        pasos_procedimiento=[
            "Pulsar <b>'Comparativa stock físico'</b>.",
            "Adjuntar la planilla Excel con los conteos físicos realizados por los operarios en los racks.",
            "Pulsar <b>'Ejecutar Comparativa'</b>.",
            "Revisar el semáforo de resultados: verde (coincidencias), rojo (faltantes) y azul (sobrantes).",
            "Exportar el informe oficial en PDF o Excel para la gerencia de operaciones.",
        ],
        resultado_obtenido="Reporte formal de auditoría de inventario con balance de discrepancias.",
        validaciones_advertencias="Permite detectar mermas no registradas o errores de conteo antes del balance mensual.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Sincronizar con Excel",
        icono_str="[🔁]",
        modulo="STOCK Y CATÁLOGO",
        proposito_funcional="Fuerza la sincronización bidireccional entre la base de datos transaccional SQLite y la planilla maestra <code>Productos.xlsx</code>, creando una copia de seguridad previa.",
        datos_modificados="Actualiza las celdas de stock, precios y descripciones en <code>Productos.xlsx</code> y genera <code>Productos_backup.xlsx</code>.",
        pasos_procedimiento=[
            "Pulsar <b>'Sincronizar con Excel'</b>.",
            "Confirmar la advertencia de sincronización en el diálogo emergente.",
            "El sistema bloqueará temporalmente las escrituras, creará el backup y volcará los datos.",
        ],
        resultado_obtenido="Planilla Excel alineada al 100% con los datos en memoria del servidor.",
        validaciones_advertencias="Se recomienda no tener el archivo Excel abierto en Microsoft Excel durante la sincronización para evitar bloqueos de archivo en Windows.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Generar pedido fábrica (Excel)",
        icono_str="[📋]",
        modulo="STOCK Y CATÁLOGO",
        proposito_funcional="Analiza automáticamente los productos cuyo stock actual es inferior al stock mínimo de seguridad y calcula la cantidad sugerida de compra, exportando una orden de pedido a fábrica en Excel.",
        datos_modificados="Genera un archivo Excel en la carpeta de documentos con la orden de compra lista para enviar al proveedor.",
        pasos_procedimiento=[
            "Hacer clic en <b>'Generar pedido fábrica (Excel)'</b>.",
            "El sistema analiza todos los SKUs y presenta la lista de artículos bajo quiebre o cercanos al punto de reorden.",
            "Graduar las cantidades a ordenar si se requiere solicitar más unidades que el lote estándar.",
            "Pulsar <b>'Descargar Planilla de Pedido'</b>.",
        ],
        resultado_obtenido="Planilla Excel formateada con códigos de proveedor, descripción y unidades requeridas.",
        validaciones_advertencias="Solo se incluyen artículos con stock inferior al stock mínimo configurado en su ficha.",
    )

    # SECCIÓN 2: VENTAS Y DESPACHOS
    story.append(PageBreak())
    story.append(Paragraph("3. Módulo: VENTAS Y DESPACHOS (Botón por Botón)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    agregar_ficha_boton(
        story, est,
        nombre_boton="Historial de Pedidos",
        icono_str="[🧾]",
        modulo="VENTAS Y DESPACHOS",
        proposito_funcional="Supervisión global de todos los pedidos preparados en depósito: consulta de remitos, clientes, bultos, estados de despacho, reimpresión de comprobantes y rótulos térmicos en lote (formato A4 o rollo térmico). Incorpora paginación en servidor de alta velocidad y protección de soft-locking colaborativo.",
        datos_modificados="Permite cambiar el estado de despacho (Despachado / Entregado) e imprimir lotes masivos de rótulos QR.",
        pasos_procedimiento=[
            "Pulsar <b>'Historial de Pedidos'</b>.",
            "Filtrar por fecha, cliente o transporte.",
            "Para impresión de rótulos en lote: seleccionar las casillas de los pedidos y presionar <b>'Imprimir Lote Rótulos A4'</b>.",
            "Para consultar el comprobante original: presionar el icono de PDF o Excel en la fila del pedido.",
        ],
        resultado_obtenido="Hoja A4 con 8 rótulos por carilla lista para impresora láser o térmica.",
        validaciones_advertencias="Los administradores tienen acceso a la totalidad de pedidos del sistema. Incorpora paginación en servidor (10, 25, 50, 100 pedidos por página) con respuesta en microsegundos y protección de Soft-Locking con concesión temporal (Lease TTL de 5 minutos) contra sobreescrituras simultáneas.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Cierres de Operarios",
        icono_str="[📋]",
        modulo="VENTAS Y DESPACHOS",
        proposito_funcional="¡NUEVA FUNCIONALIDAD EXCLUSIVA DE ADMINISTRADOR! Permite visualizar en orden estrictamente descendente (más recientes primero) todos los cierres de jornada finalizados por los operarios de depósito, con auditoría detallada de pedidos y comprobantes.",
        datos_modificados="Consulta la tabla <code>cierres_jornada</code> y permite emitir/reimprimir Hojas de Ruta y reportes consolidados.",
        pasos_procedimiento=[
            "Pulsar el botón <b>'Cierres de Operarios'</b> en el panel lateral.",
            "En la ventana modal se visualizan los cierres ordenados de forma descendente (Cierre #ID más alto arriba).",
            "En la cabecera se observan los contadores: Total Cierres, Pedidos Consolidados y Unidades Descontadas.",
            "Usar el buscador en tiempo real para filtrar por nombre de operario (ej. 'juan'), número de cierre o fecha.",
            "En cada tarjeta de cierre se dispone de los siguientes botones de acción:",
            "  • <b>Ver Pedidos</b>: Abre una sub-ventana con el detalle de todos los remitos incluidos en ese cierre.",
            "  • <b>Hoja de Ruta (🚚)</b>: Abre o regenera la Hoja de Ruta de despacho (general o por transporte).",
            "  • <b>PDF (📄)</b>: Abre el informe oficial de cierre en PDF.",
            "  • <b>Excel (📊)</b>: Abre la planilla de consolidación en Excel.",
            "  • <b>Correo (✉️)</b>: Reenvía los archivos del cierre por email a clientes o gerencia.",
        ],
        resultado_obtenido="Auditoría forense completa de la labor diaria de los operarios y trazabilidad de despachos.",
        validaciones_advertencias="Función restringida exclusivamente a los roles Administrador y Master. Presenta los registros de manera inmutable para control interno.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Gestión de Clientes",
        icono_str="[👥]",
        modulo="VENTAS Y DESPACHOS",
        proposito_funcional="Administración integral de la base de clientes comerciales, transportes habituales, teléfonos, CUIT y condiciones de despacho.",
        datos_modificados="Tabla <code>clientes</code> (altas, modificaciones y desactivaciones).",
        pasos_procedimiento=[
            "Pulsar <b>'Gestión de Clientes'</b>.",
            "Buscar por nombre o número de cliente.",
            "Completar o actualizar los datos y guardar.",
        ],
        resultado_obtenido="Padrón de clientes actualizado.",
        validaciones_advertencias="Se valida el formato de CUIT y la obligatoriedad de razón social.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Descontar Mercado Libre / Full / API",
        icono_str="[🏪]",
        modulo="VENTAS Y DESPACHOS",
        proposito_funcional="Supervisión y ejecución de descuentos de canales de venta electrónicos: Mercado Libre con pistola de códigos de barras ítem por ítem o archivos DOCX, envíos a centros Mercado Full y enlace desatendido con la API oficial.",
        datos_modificados="Decrementos atómicos de stock en SQLite y Productos.xlsx, trazabilidad en auditoría forense y asientos contables de pedidos.",
        pasos_procedimiento=[
            "Seleccionar el canal deseado: 'Descontar Mercado Libre' (Pistoleo / DOCX), 'Descontar Mercado Full' o 'Sincronizar Mercado Libre (API)'.",
            "Para Mercado Libre: armar el paquete escaneando los artículos en vivo o seleccionar un archivo .docx recibido.",
            "Para Mercado Full: procesar la planilla oficial de bodega central.",
            "Para API: descargar órdenes desatendidas y descontar en bloque con un clic.",
            "Confirmar la operación y verificar la deducción inmediata en el inventario maestro.",
        ],
        resultado_obtenido="Actualización en tiempo real del stock, generación de comprobantes oficiales y registro de métricas de la jornada.",
        validaciones_advertencias="Garantiza que las ventas web no generen sobreventas de stock en depósito físico y previene duplicaciones mediante hashes criptográficos.",
    )

    # SECCIÓN 3: ANALÍTICA Y PICKING
    story.append(PageBreak())
    story.append(Paragraph("4. Módulo: ANALÍTICA Y PICKING (Botón por Botón)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    agregar_ficha_boton(
        story, est,
        nombre_boton="Métricas y Rendimiento",
        icono_str="[📈]",
        modulo="ANALÍTICA Y PICKING",
        proposito_funcional="Dashboard ejecutivo con indicadores clave de desempeño (KPIs): volumen de unidades despachadas, bultos acumulados por transporte, pedidos armados por hora y rotación de inventario.",
        datos_modificados="Ninguno (lectura analítica agregada).",
        pasos_procedimiento=[
            "Pulsar <b>'Métricas y Rendimiento'</b>.",
            "Seleccionar el rango de análisis (jornada actual, últimos 7 días o mes en curso).",
            "Analizar los gráficos de barras y tarjetas de rendimiento del personal de depósito.",
        ],
        resultado_obtenido="Visión global de productividad del almacén para toma de decisiones.",
        validaciones_advertencias="Los datos se refrescan de forma automática en cada cierre de jornada.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Estadísticas de salida",
        icono_str="[📊]",
        modulo="ANALÍTICA Y PICKING",
        proposito_funcional="Presenta el ranking de productos más vendidos (Top Salidas), porcentaje de participación sobre el total de ventas y curvas de estacionalidad.",
        datos_modificados="Ninguno.",
        pasos_procedimiento=[
            "Hacer clic en <b>'Estadísticas de salida'</b>.",
            "Visualizar el gráfico comparativo de los productos de mayor rotación.",
            "Exportar la tabla estadística para el departamento de compras.",
        ],
        resultado_obtenido="Información estratégica para la planificación de compras.",
        validaciones_advertencias="Permite categorizar los productos bajo clasificación ABC.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Radar de anomalías",
        icono_str="[⚡]",
        modulo="ANALÍTICA Y PICKING",
        proposito_funcional="Algoritmo de detección inteligente que alerta al administrador sobre patrones de consumo inusuales, pedidos con cantidades atípicas o riesgos inminentes de rotura de stock.",
        datos_modificados="Genera alertas en el centro de notificaciones superior.",
        pasos_procedimiento=[
            "Pulsar <b>'Radar de anomalías'</b>.",
            "Revisar los artículos listados con nivel de riesgo (Alto, Medio, Bajo).",
            "Pulsar sobre una anomalía para ver qué pedido causó la desviación.",
        ],
        resultado_obtenido="Detección temprana de errores de carga o desabastecimiento.",
        validaciones_advertencias="Monitorea desviaciones de más del 200% respecto al consumo promedio histórico.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Heatmap y Picking",
        icono_str="[🗺️]",
        modulo="ANALÍTICA Y PICKING",
        proposito_funcional="Visualización del plano de depósito con mapa de calor (Heatmap) que muestra los racks con mayor afluencia de recolección y sugiere rutas óptimas de picking para reducir tiempos de caminata.",
        datos_modificados="Calcula coordenadas y actualiza recomendaciones de slotting (reubicación de artículos).",
        pasos_procedimiento=[
            "Pulsar <b>'Heatmap y Picking'</b>.",
            "Observar los sectores en rojo (alta rotación) y azul (baja rotación).",
            "Verificar las sugerencias de mover artículos de alta rotación a los niveles inferiores y cercanos a la cabecera.",
        ],
        resultado_obtenido="Optimización física del almacén y reducción de tiempos de preparación.",
        validaciones_advertencias="Requiere que los productos tengan asignadas sus ubicaciones en estantería.",
    )

    # SECCIÓN 4: RESGUARDO Y USUARIOS
    story.append(Spacer(1, 4))
    story.append(Paragraph("5. Módulos: RESGUARDO, SISTEMA Y USUARIOS", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    agregar_ficha_boton(
        story, est,
        nombre_boton="Copia de Seguridad",
        icono_str="[💾]",
        modulo="SISTEMA Y RESGUARDO",
        proposito_funcional="Genera una copia de seguridad integral e instantánea (.zip) con la base de datos SQLite, planillas de catálogo, historial de pedidos y archivos adjuntos, con opción de réplica en directorio de red.",
        datos_modificados="Crea un archivo comprimido fechado en <code>data/backups/Backup_StockAgent_YYYYMMDD_HHMMSS.zip</code>.",
        pasos_procedimiento=[
            "Hacer clic en <b>'Copia de Seguridad'</b>.",
            "Verificar el espacio disponible en disco y la ruta de destino.",
            "Pulsar <b>'Generar Respaldo Ahora'</b>.",
            "El sistema emite confirmación y registra el evento en auditoría.",
        ],
        resultado_obtenido="Archivo .ZIP cifrable para resguardo seguro y contingencias.",
        validaciones_advertencias="Se recomienda realizar copias al inicio y final de cada semana operativa.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Gestionar usuarios",
        icono_str="[👥]",
        modulo="ADMINISTRACIÓN DE USUARIOS",
        proposito_funcional="Permite dar de alta cuentas de operarios y personal de consulta, modificar contraseñas temporales y forzar el cambio de clave en el primer inicio de sesión.",
        datos_modificados="Tabla <code>users</code> en SQLite. Guarda las contraseñas con hash criptográfico irreversible.",
        pasos_procedimiento=[
            "Pulsar <b>'Gestionar usuarios'</b>.",
            "Para un nuevo usuario: pulsar <b>'Crear Usuario'</b>, ingresar username, clave y rol (Operador o Consulta).",
            "Para resetear clave: seleccionar el usuario, presionar <b>'Reset Clave'</b> e indicar nueva contraseña provisional.",
        ],
        resultado_obtenido="Control de acceso y credenciales corporativas seguras.",
        validaciones_advertencias="Un administrador no puede crear otros administradores ni modificar cuentas Master (principio SoD de menor privilegio).",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Docking Adaptativo del Menú (5 Posiciones)",
        icono_str="[📐]",
        modulo="CONFIGURACIÓN DE INTERFAZ",
        proposito_funcional="Permite reposicionar dinámicamente el panel de navegación lateral en 5 orientaciones distintas para adaptarse a monitores ultra-wide, terminales táctiles, tablets o pantallas completas.",
        datos_modificados="Preferencia de visualización del usuario en sesión activa.",
        pasos_procedimiento=[
            "Hacer clic en el selector de posición de menú en la barra de herramientas o encabezado.",
            "Elegir entre las 5 opciones disponibles: 'Izquierda' (clásica), 'Derecha' (ergonomía para diestros en pantallas táctiles), 'Arriba' (estilo barra Ribbon horizontal), 'Abajo' (acceso inferior) u 'Oculto' (modo pantalla completa para maximizar visibilidad de tablas).",
            "La interfaz reacomoda todos los componentes de forma reactiva instantánea.",
        ],
        resultado_obtenido="Entorno de trabajo personalizado según la ergonomía del puesto y el dispositivo utilizado.",
        validaciones_advertencias="La posición seleccionada se preserva durante toda la sesión del usuario.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Paleta de Comandos Rápida (F2 / Ctrl + K)",
        icono_str="[⚡]",
        modulo="CABECERA Y COMANDOS",
        proposito_funcional="Lanzador universal de comandos y buscador instantáneo que mapea todas las pantallas, formularios y funciones autorizadas para el rol del usuario autenticado.",
        datos_modificados="Ninguno (acelerador de navegación).",
        pasos_procedimiento=[
            "Pulsar la tecla F2 o la combinación Ctrl + K en cualquier momento.",
            "Escribir el nombre del módulo deseado (ej. 'productos', 'clientes', 'cierre', 'usuarios', 'fábrica').",
            "Utilizar las flechas Arriba/Abajo para navegar la lista filtrada en tiempo real.",
            "Presionar Enter para ejecutar y abrir inmediatamente la función seleccionada.",
        ],
        resultado_obtenido="Navegación 100% por teclado sin despegar las manos del escáner o teclado numérico.",
        validaciones_advertencias="Solo lista las opciones permitidas según los privilegios del perfil conectado.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Semáforo de Conectividad LAN",
        icono_str="[📡]",
        modulo="INFRAESTRUCTURA Y TELEMETRÍA",
        proposito_funcional="Monitor en tiempo real de la calidad de conexión entre la terminal del administrador y el servidor central, con cálculo de latencia de red (RTT) y alerta temprana.",
        datos_modificados="Ninguno en base de datos. Actualización de indicador visual en encabezado.",
        pasos_procedimiento=[
            "Verificar el icono de estado de red ubicado en el extremo superior derecho del encabezado.",
            "Interpretar los colores del indicador: Verde (<50 ms, latencia óptima), Amarillo (50-200 ms, tráfico elevado en Wi-Fi) o Rojo (>200 ms / Sin conexión).",
            "Al posar el cursor sobre el indicador, se despliega la latencia exacta calculada por el último ciclo de sondeo.",
        ],
        resultado_obtenido="Tranquilidad operativa y diagnóstico instantáneo del estado de la red local.",
        validaciones_advertencias="Si el semáforo cambia a rojo, el sistema advierte con un mensaje emergente para evitar operaciones pesadas hasta restablecer la señal.",
    )

    story.append(Spacer(1, 6))
    agregar_tarjeta_referencia_rapida(story, est)
    story.append(PageBreak())
    agregar_formulario_firmas_autorizadas_iso(story, est, 2)
    agregar_matriz_distribucion_copias(story, est, 3)
    agregar_acta_capacitacion_personal(story, est, 4)

    doc.build(story, canvasmaker=crear_canvas_iso_upel(codigo_doc, titulo_doc, "3.0.0"))
    return ruta_destino


# =============================================================================
# 3. MANUAL ROL MASTER (BOTÓN POR BOTÓN)
# =============================================================================
def construir_manual_master(ruta_destino: Path) -> Path:
    """Genera el Manual de Procedimiento y Uso Botón por Botón para el Rol Master."""
    ruta_destino.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(ruta_destino),
        pagesize=A4,
        leftMargin=MARGEN_IZQ,
        rightMargin=MARGEN_DER,
        topMargin=MARGEN_SUP,
        bottomMargin=MARGEN_INF,
    )
    est = obtener_estilos_iso_upel()
    story = []

    codigo_doc = "MAN-PROC-MST-2026"
    titulo_doc = "Manual de Procedimiento y Uso de Botones (Rol Master)"

    agregar_portada_iso_upel(
        story, est, codigo_doc, titulo_doc,
        "Rol Master (Seguridad de la Información, Auditoría Forense y Resguardo Técnico)",
        "Guía técnica y procedimental botón por botón: auditoría inmutable, restauración de documentos, "
        "archivado histórico, configuración SMTP de correos, bot de alertas Telegram y gestión de credenciales API.",
        version="3.0.0",
    )

    story.append(Paragraph("1. Principios de Seguridad y Segregación SoD (Rol Master)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))
    story.append(Paragraph(
        "El rol <b>Master</b> (`Desarrollo / Superadministrador`) es la máxima autoridad técnica del sistema. "
        "Bajo el principio SoD de la Norma ISO/IEC 27001, no realiza tareas de negocio diarias (preparar pedidos) para mantener "
        "su total imparcialidad técnica. Sus atribuciones comprenden la trazabilidad forense, restauración en desastres, "
        "archivado histórico y configuración de servidores de comunicación.",
        est["body_sangria"],
    ))
    story.append(Spacer(1, 4))

    # SECCIÓN 1: AUDITORÍA Y TRAZABILIDAD
    story.append(Paragraph("2. Módulos: AUDITORÍA Y RESGUARDO (Botón por Botón)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    agregar_ficha_boton(
        story, est,
        nombre_boton="Registro de Auditoría",
        icono_str="[🛡️]",
        modulo="AUDITORÍA Y TRAZABILIDAD",
        proposito_funcional="Visualización e inspección de la bitácora inmutable de eventos de seguridad y transaccionales del sistema: inicios de sesión, cambios de stock, anulaciones, exportaciones y modificaciones de permisos.",
        datos_modificados="Ninguno (lectura forense de la tabla inmutable <code>logs_auditoria</code>).",
        pasos_procedimiento=[
            "Pulsar <b>'Registro de Auditoría'</b>.",
            "Filtrar por usuario, acción (ej. CIERRE_JORNADA, LOGIN_FALLIDO) o rango de fechas.",
            "Examinar el detalle técnico con dirección IP, timestamp exacto y resultado de la transacción.",
            "Exportar la bitácora a archivo para cumplimiento de normas de auditoría.",
        ],
        resultado_obtenido="Pista de auditoría legalmente válida con integridad criptográfica.",
        validaciones_advertencias="Los registros de auditoría no pueden ser eliminados ni modificados por ningún usuario.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Copia de Seguridad",
        icono_str="[💾]",
        modulo="RESGUARDO Y CONTINUIDAD",
        proposito_funcional="Ejecución de respaldos completos del sistema con verificación de integridad de archivos y almacenamiento en espejo de red local o en la nube.",
        datos_modificados="Crea archivos .ZIP de rescate y asienta el hash de verificación en auditoría.",
        pasos_procedimiento=[
            "Pulsar <b>'Copia de Seguridad'</b>.",
            "Configurar el directorio de réplica automática en red si corresponde.",
            "Hacer clic en <b>'Generar Respaldo Ahora'</b>.",
        ],
        resultado_obtenido="Archivo comprimido de respaldo verificado.",
        validaciones_advertencias="El sistema verifica que no existan transacciones incompletas durante la compresión.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Restaurar documentos",
        icono_str="[⏮️]",
        modulo="RESGUARDO Y CONTINUIDAD",
        proposito_funcional="POTESTAD EXCLUSIVA MASTER: Permite restituir a su estado activo pedidos o remitos que hayan sido cancelados, desarmados o archivados por error operacional.",
        datos_modificados="Actualiza el estado de pedidos en la base de datos y recalcula el inventario asociado.",
        pasos_procedimiento=[
            "Pulsar <b>'Restaurar documentos'</b>.",
            "Localizar el pedido por número de remito o identificador único.",
            "Verificar el motivo de la anulación original.",
            "Pulsar <b>'Confirmar Restauración'</b>.",
        ],
        resultado_obtenido="Pedido reactivado en la base de datos activa y stock reajustado.",
        validaciones_advertencias="Se registra un evento de máxima prioridad en la auditoría forense con el usuario Master que autorizó la reversión.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Archivado Histórico",
        icono_str="[🗑️]",
        modulo="RESGUARDO Y CONTINUIDAD",
        proposito_funcional="POTESTAD EXCLUSIVA MASTER: Mueve registros de pedidos, cierres y remitos de ejercicios anteriores a tablas históricas desacopladas para mantener la base de datos operativa ágil y compacta.",
        datos_modificados="Mueve registros de <code>pedidos</code> y <code>cierres_jornada</code> hacia la base histórica <code>historico.sqlite3</code>.",
        pasos_procedimiento=[
            "Pulsar <b>'Archivado Histórico'</b>.",
            "Definir la fecha de corte (ej. anterior a 180 días).",
            "Pulsar <b>'Ejecutar Archivado'</b>.",
            "El sistema emite un informe con la cantidad de registros migrados y compacta la base activa mediante VACUUM.",
        ],
        resultado_obtenido="Reducción del tamaño de la base operativa y aumento de velocidad de consulta.",
        validaciones_advertencias="Los datos archivados continúan disponibles para consultas y reportes históricos.",
    )

    # SECCIÓN 2: SISTEMA E INTEGRACIONES
    story.append(PageBreak())
    story.append(Paragraph("3. Módulos: SISTEMA, INTEGRACIONES Y SEGURIDAD", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    agregar_ficha_boton(
        story, est,
        nombre_boton="Configuración SMTP",
        icono_str="[⚙️]",
        modulo="SISTEMA",
        proposito_funcional="Configuración de los parámetros del servidor de correo electrónico saliente institucional para el envío automático de informes de cierre y notificaciones.",
        datos_modificados="Archivo de configuración y almacenamiento de credenciales seguras de correo.",
        pasos_procedimiento=[
            "Hacer clic en <b>'Configuración SMTP'</b>.",
            "Ingresar Servidor (Host), Puerto (ej. 587 o 465), Usuario, Contraseña y tipo de cifrado (TLS/SSL).",
            "Pulsar <b>'Enviar Correo de Prueba'</b> para verificar la conexión.",
            "Presionar <b>'Guardar Configuración'</b>.",
        ],
        resultado_obtenido="Servicio de correo institucional habilitado para todo el sistema.",
        validaciones_advertencias="Las contraseñas de correo se almacenan cifradas.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Alertas Telegram",
        icono_str="[✈️]",
        modulo="SISTEMA",
        proposito_funcional="Vinculación del sistema con un Bot de Telegram para el envío proactivo de notificaciones instantáneas ante quiebres de stock, cierres de jornada o eventos de seguridad.",
        datos_modificados="Almacena el Token del Bot de Telegram y el Chat ID del canal de supervisión.",
        pasos_procedimiento=[
            "Pulsar <b>'Alertas Telegram'</b>.",
            "Introducir el Bot Token proporcionado por BotFather y el Chat ID del grupo de supervisores.",
            "Pulsar <b>'Probar Envío'</b> para certificar la recepción del mensaje de prueba en el móvil.",
            "Guardar la configuración activa.",
        ],
        resultado_obtenido="Alertas en tiempo real directo a los celulares de la gerencia.",
        validaciones_advertencias="Requiere conexión a Internet en el servidor anfitrión.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Mercado Libre API (Credenciales)",
        icono_str="[☁️]",
        modulo="SISTEMA",
        proposito_funcional="Gestión técnica de las llaves de acceso a la API oficial de Mercado Libre (App ID, Secret Key, Token y Refresh Token).",
        datos_modificados="Credenciales de autenticación OAuth 2.0 en el almacenamiento seguro de la aplicación.",
        pasos_procedimiento=[
            "Pulsar <b>'Mercado Libre API (Credenciales)'</b>.",
            "Ingresar las claves de la aplicación obtenidas en el portal de desarrolladores de Mercado Libre.",
            "Presionar <b>'Autorizar y Obtener Token'</b>.",
        ],
        resultado_obtenido="Enlace seguro autenticado para sincronización de ventas y stock.",
        validaciones_advertencias="Los tokens vencidos se renuevan automáticamente mediante el Refresh Token.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Gestionar usuarios",
        icono_str="[🔐]",
        modulo="SEGURIDAD Y ACCESOS",
        proposito_funcional="Administración integral de identidades (IAM): creación, modificación, asignación de roles privilegiados (Administrador, Operador, Consulta), desactivación de cuentas y desbloqueo de usuarios.",
        datos_modificados="Tabla <code>users</code> en SQLite con hash de contraseñas.",
        pasos_procedimiento=[
            "Hacer clic en <b>'Gestionar usuarios'</b>.",
            "Crear cuentas asignando el rol correspondiente.",
            "Establecer la política de cambio forzoso de contraseña en el primer ingreso.",
        ],
        resultado_obtenido="Gestión centralizada de accesos y cumplimiento de directrices de seguridad.",
        validaciones_advertencias="La cuenta Master original posee protección permanente contra desactivación o eliminación.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Gestor de Concurrencia, Soft-Locks e Idempotencia",
        icono_str="[🔒]",
        modulo="SEGURIDAD Y CONCURRENCIA",
        proposito_funcional="Mecanismo de alta disponibilidad y consistencia transaccional: administra la tabla 'pedidos_bloqueos' con concesiones temporales (Leases TTL de 5 minutos) y la tabla 'transacciones_procesadas' con hashes criptográficos SHA-256 para prevenir doble descuento ante reintentos o desconexiones.",
        datos_modificados="Tablas <code>pedidos_bloqueos</code> y <code>transacciones_procesadas</code> en 'pedidos.sqlite3'.",
        pasos_procedimiento=[
            "El usuario Master puede auditar desde el panel técnico las concesiones activas y las claves de idempotencia registradas.",
            "En caso de una sesión caída o desconexión anómala, los bloqueos temporales expiran automáticamente a los 5 minutos sin intervención técnica.",
            "Si una terminal reenvía un comprobante por un micro-corte de red, el middleware de idempotencia devuelve la respuesta original sin alterar los saldos de inventario maestro.",
        ],
        resultado_obtenido="Cero condiciones de carrera, cero pedidos duplicados y resiliencia absoluta en entornos multi-terminal.",
        validaciones_advertencias="Los registros de transacciones procesadas son inmutables para garantizar el no repudio bajo ISO/IEC 27001.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Demonio Heartbeat y Latencia de Red",
        icono_str="[📡]",
        modulo="INFRAESTRUCTURA Y TELEMETRÍA",
        proposito_funcional="Servicio en segundo plano que sondea la conectividad de la base de datos y la red LAN cada 12 segundos, computando la latencia en milisegundos y despachando eventos colaborativos.",
        datos_modificados="Registros de latencia en logs de diagnóstico.",
        pasos_procedimiento=[
            "El demonio se inicializa automáticamente al arrancar la interfaz web.",
            "Cada 12 segundos ejecuta una consulta ligera de validación a SQLite y mide el tiempo de respuesta RTT.",
            "Actualiza dinámicamente el semáforo LED de estado en la cabecera (Verde/Amarillo/Rojo).",
            "Si la latencia supera el umbral crítico (>200 ms o falla de enlace), notifica a los clientes mediante SnackBar colaborativo.",
        ],
        resultado_obtenido="Telemetría proactiva de infraestructura y prevención temprana de cuellos de botella en la red del depósito.",
        validaciones_advertencias="Opera de forma asíncrona segura sin degradar el rendimiento del hilo principal de usuario.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Docking Dinámico y Paleta Master (F2)",
        icono_str="[⚡]",
        modulo="CONFIGURACIÓN Y ACCESOS RÁPIDOS",
        proposito_funcional="Control integral del layout de interfaz (5 orientaciones de docking) y acceso instantáneo mediante la tecla F2 a la totalidad de comandos, parsers, logs forenses y utilidades técnicas del rol Master.",
        datos_modificados="Preferencia de visualización del usuario.",
        pasos_procedimiento=[
            "Pulsar la tecla F2 en cualquier pantalla para abrir la Paleta de Comandos Master.",
            "Filtrar por términos técnicos como 'auditoría', 'restaurar', 'smtp', 'archivado', 'bloqueos'.",
            "Presionar Enter para lanzar la consola o diálogo correspondiente sin navegar menús.",
            "Ajustar la barra de herramientas (Izquierda, Derecha, Arriba, Abajo u Oculta) según el número de pantallas activas.",
        ],
        resultado_obtenido="Máxima velocidad de administración técnica y monitoreo del sistema en producción.",
        validaciones_advertencias="La paleta en rol Master despliega el 100% de los módulos sin restricciones.",
    )

    story.append(Spacer(1, 6))
    agregar_tarjeta_referencia_rapida(story, est)
    story.append(PageBreak())
    agregar_formulario_firmas_autorizadas_iso(story, est, 2)
    agregar_matriz_distribucion_copias(story, est, 3)

    doc.build(story, canvasmaker=crear_canvas_iso_upel(codigo_doc, titulo_doc, "3.0.0"))
    return ruta_destino


# =============================================================================
# 4. MANUAL ROL CONSULTA (BOTÓN POR BOTÓN)
# =============================================================================
def construir_manual_consulta(ruta_destino: Path) -> Path:
    """Genera el Manual de Procedimiento y Uso Botón por Botón para el Rol Consulta."""
    ruta_destino.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(ruta_destino),
        pagesize=A4,
        leftMargin=MARGEN_IZQ,
        rightMargin=MARGEN_DER,
        topMargin=MARGEN_SUP,
        bottomMargin=MARGEN_INF,
    )
    est = obtener_estilos_iso_upel()
    story = []

    codigo_doc = "MAN-PROC-CON-2026"
    titulo_doc = "Manual de Procedimiento y Uso de Botones (Rol Consulta)"

    agregar_portada_iso_upel(
        story, est, codigo_doc, titulo_doc,
        "Rol Consulta (Auditores, Clientes Corporativos y Personal de Solo Lectura)",
        "Guía operativa botón por botón: visualización segura de existencias, apertura de informes oficiales, "
        "distribución de comprobantes por correo electrónico y enlace de despachos vía WhatsApp Web.",
        version="3.0.0",
    )

    story.append(Paragraph("1. Ámbito de Aplicación y Permisos de Solo Lectura", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))
    story.append(Paragraph(
        "El perfil <b>Consulta</b> está diseñado para auditores externos, personal administrativo de apoyo o clientes "
        "que requieren verificar existencias y despachos sin poseer facultades de alteración de stock ni de creación de pedidos. "
        "Su interfaz está simplificada para garantizar una experiencia ágil, segura y libre de riesgos operativos.",
        est["body_sangria"],
    ))
    story.append(Spacer(1, 4))

    # BOTONES DEL ROL CONSULTA
    story.append(Paragraph("2. Módulos e Instrucciones Botón por Botón", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    agregar_ficha_boton(
        story, est,
        nombre_boton="Abrir informe",
        icono_str="[↗️]",
        modulo="INFORMES",
        proposito_funcional="Permite visualizar y descargar en formato PDF el último informe de stock o balance de despacho generado en el sistema.",
        datos_modificados="Ninguno (modo de lectura segura).",
        pasos_procedimiento=[
            "Hacer clic en el botón <b>'Abrir informe'</b> en el panel lateral.",
            "El sistema abrirá automáticamente el visor de documentos de su equipo con el PDF oficial.",
            "Es posible imprimirlo o guardarlo localmente.",
        ],
        resultado_obtenido="Descarga o visualización del informe vigente.",
        validaciones_advertencias="No requiere permisos de escritura.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Compartir por correo",
        icono_str="[✉️]",
        modulo="INFORMES",
        proposito_funcional="Permite reenviar el informe oficial activo por correo electrónico a casillas autorizadas.",
        datos_modificados="Ninguno en la base de existencias.",
        pasos_procedimiento=[
            "Pulsar <b>'Compartir por correo'</b>.",
            "Ingresar la dirección de correo electrónico del destinatario.",
            "Hacer clic en <b>'Enviar'</b>.",
        ],
        resultado_obtenido="Comprobante remitido al buzón del destinatario.",
        validaciones_advertencias="El correo ingresado debe cumplir con la estructura estándar (ej: usuario@empresa.com).",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="WhatsApp Web",
        icono_str="[💬]",
        modulo="INFORMES",
        proposito_funcional="Genera un enlace instantáneo con un mensaje prediseñado que resume los despachos y existencias para compartir rápidamente vía mensajería.",
        datos_modificados="Ninguno.",
        pasos_procedimiento=[
            "Hacer clic en <b>'WhatsApp Web'</b>.",
            "Se abrirá la aplicación web de WhatsApp para seleccionar el contacto al cual enviar el resumen.",
        ],
        resultado_obtenido="Compartición rápida de información logística.",
        validaciones_advertencias="Requiere que el navegador cuente con WhatsApp Web iniciado.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Búsqueda Rápida Global (Ctrl + K / F2)",
        icono_str="[🔍]",
        modulo="CABECERA Y COMANDOS",
        proposito_funcional="Paleta de búsqueda universal para consultar rápidamente el stock de cualquier artículo escribiendo su nombre, SKU o código de barras.",
        datos_modificados="Ninguno.",
        pasos_procedimiento=[
            "Presionar las teclas <b>Ctrl + K</b> o la tecla <b>F2</b> (o pulsar el icono de lupa en el encabezado).",
            "Escribir las primeras letras del producto.",
            "El sistema desplegará de inmediato la descripción y el stock disponible actual.",
        ],
        resultado_obtenido="Consulta ultrarrápida de existencias en menos de un segundo.",
        validaciones_advertencias="Ideal para atención rápida a clientes por mostrador o teléfono.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Docking Adaptativo de Barra (5 Posiciones)",
        icono_str="[📐]",
        modulo="PERSONALIZACIÓN DE VISTA",
        proposito_funcional="Permite a los usuarios de solo lectura acomodar el menú de navegación en la posición más cómoda según la pantalla utilizada: izquierda, derecha, arriba, abajo u oculto a pantalla completa.",
        datos_modificados="Ninguno en datos de stock. Ajusta la vista en la sesión activa.",
        pasos_procedimiento=[
            "Hacer clic en el selector de posición en la barra lateral o encabezado.",
            "Seleccionar la posición deseada (ej. 'Arriba' para vista horizontal o 'Derecha' para tablets).",
            "La pantalla se reacomoda al instante para una lectura cómoda de informes.",
        ],
        resultado_obtenido="Visualización ergonómica y adaptable para auditorías o terminales de consulta.",
        validaciones_advertencias="No afecta a otros usuarios que compartan la misma red LAN.",
    )

    agregar_ficha_boton(
        story, est,
        nombre_boton="Semáforo de Conectividad y Servidor",
        icono_str="[📡]",
        modulo="CONEXIÓN Y ESTADO",
        proposito_funcional="Indica el estado del enlace con el servidor de existencias en tiempo real mediante semáforo LED de latencia.",
        datos_modificados="Ninguno.",
        pasos_procedimiento=[
            "Verificar el indicador circular en la esquina superior derecha.",
            "Verde: enlace óptimo en tiempo real. Amarillo: latencia moderada. Rojo: desconectado.",
            "Si el indicador está verde, los datos de inventario consultados están 100% al día.",
        ],
        resultado_obtenido="Certeza de estar consultando saldos en tiempo real sin desfase de datos.",
        validaciones_advertencias="Si pierde conexión (rojo), espere a que el semáforo retorne a verde para revalidar el stock.",
    )

    story.append(Spacer(1, 6))
    agregar_tarjeta_referencia_rapida(story, est)
    story.append(PageBreak())
    agregar_formulario_firmas_autorizadas_iso(story, est, 2)

    doc.build(story, canvasmaker=crear_canvas_iso_upel(codigo_doc, titulo_doc, "3.0.0"))
    return ruta_destino


# =============================================================================
# 5. GENERADOR MAESTRO Y GENERAL
# =============================================================================
def construir_manual_general(ruta_destino: Path) -> Path:
    """Genera el manual general consolidado con todos los roles."""
    return construir_manual_administrador(ruta_destino)


def construir_manual_maestro_imprimible(ruta_destino: Path) -> Path:
    """Genera el manual maestro imprimible."""
    return construir_manual_administrador(ruta_destino)


def generar_todos_los_manuales(directorio_destino: Path | str | None = None) -> dict[str, Path]:
    """Genera todos los manuales de procedimiento y uso botón por botón en formato PDF."""
    base_dir = Path(directorio_destino) if directorio_destino else Path("Documentacion")
    base_dir.mkdir(parents=True, exist_ok=True)

    rutas = {
        "operador": base_dir / "Manual_Operador.pdf",
        "administrador": base_dir / "Manual_Administrador.pdf",
        "master": base_dir / "Manual_Master.pdf",
        "consulta": base_dir / "Manual_Consulta.pdf",
        "general": base_dir / "Manual_General.pdf",
        "maestro": base_dir / "Manual_Maestro_Imprimible.pdf",
    }

    construir_manual_operador(rutas["operador"])
    construir_manual_administrador(rutas["administrador"])
    construir_manual_master(rutas["master"])
    construir_manual_consulta(rutas["consulta"])
    construir_manual_general(rutas["general"])
    construir_manual_maestro_imprimible(rutas["maestro"])

    # Compatibilidad con ruta legacy
    ruta_legacy = base_dir / "Manual_de_Uso_StockAgent.pdf"
    construir_manual_general(ruta_legacy)

    return rutas


if __name__ == "__main__":
    print("Compilando todos los manuales de procedimiento y uso botón por botón en PDF...")
    res = generar_todos_los_manuales()
    print("=== MANUALES GENERADOS EXITOSAMENTE ===")
    for k, v in res.items():
        print(f"[{k.upper():13}] -> {v.name:28} ({v.stat().st_size} bytes)")
