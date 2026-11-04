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
            "Revisar la lista en pantalla: ajustar cantidades con los botones '+' y '-' o descartar artículos si hubo una equivocación antes de confirmar.",
            "Opcionalmente escanear o escribir el N° de Envío / Guía de Mercado Libre y el nombre del destinatario.",
            "Presionar <b>'Confirmar y Descontar'</b>. El sistema descontará el stock en vivo y ofrecerá la impresión con 1 clic de los rótulos térmicos o A4.",
            "<b>Modo Archivo DOCX:</b> Cambiar a la pestaña 'Cargar Archivo (.docx)', seleccionar el comprobante recibido de Mercado Libre y confirmar la deducción en lote.",
        ],
        resultado_obtenido="Stock descontado con exactitud unitaria, comprobante oficial guardado en 'data/pedidos_archivos/' y pedido sumado al panel en vivo del turno para el Cierre de Jornada.",
        validaciones_advertencias="Si el producto escaneado no existe en el catálogo, sonará una señal acústica de error y la lista no se modificará. Si el saldo restante queda en quiebre (<= 0), el sistema advertirá en color ámbar.",
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
        nombre_boton="Sincronizar Mercado Libre (API)",
        icono_str="[☁️]",
        modulo="PEDIDOS EN TIEMPO REAL",
        proposito_funcional="Establece enlace directo con los servidores de Mercado Libre mediante API para descargar y descontar órdenes de venta recientes en línea.",
        datos_modificados="Descarga órdenes de venta y actualiza automáticamente los saldos de stock disponibles.",
        pasos_procedimiento=[
            "Pulsar <b>'Sincronizar Mercado Libre (API)'</b>.",
            "Pulsar <b>'Consultar Órdenes Recientes'</b> para solicitar a la API las ventas de las últimas 24 horas.",
            "Seleccionar las órdenes pendientes de procesamiento.",
            "Hacer clic en <b>'Descontar Seleccionadas'</b>.",
        ],
        resultado_obtenido="Sincronización en tiempo real sin necesidad de descargar planillas manuales.",
        validaciones_advertencias="Requiere que el usuario Master haya configurado previamente las credenciales API válidas (Token y Secret).",
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
        proposito_funcional="Función central del Operador. Consolida todos los pedidos preparados pendientes, realiza el descuento consolidado de stock en Productos.xlsx, genera el informe de cierre y emite la Hoja de Ruta de Despacho para los choferes.",
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
        proposito_funcional="Registra el ingreso de mercadería enviada desde proveedores o fábrica mediante planillas Excel o ajuste manual, y asienta mermas, roturas o devoluciones.",
        datos_modificados="Incrementa o decrementa la existencia física en <code>productos</code> y asienta el movimiento en <code>stock_movements</code>.",
        pasos_procedimiento=[
            "Pulsar <b>'Ajustar stock / Fábrica'</b>.",
            "Para ingreso por remito de fábrica: seleccionar la planilla .xlsx o .pdf enviada por el fabricante y presionar <b>'Importar Entrada'</b>.",
            "Para ajuste manual: seleccionar el producto, ingresar la cantidad (+ para ingreso, - para merma/rotura).",
            "Indicar obligatoriamente el motivo del ajuste en el campo de texto justificativo.",
            "Pulsar <b>'Aplicar Ajuste'</b>.",
        ],
        resultado_obtenido="Actualización inmediata de inventario y generación del comprobante de ajuste de stock.",
        validaciones_advertencias="Todo ajuste manual negativo requiere motivo justificado para fines de auditoría interna.",
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
        proposito_funcional="Supervisión global de todos los pedidos preparados en depósito: consulta de remitos, clientes, bultos, estados de despacho, reimpresión de comprobantes y rótulos térmicos en lote (formato A4 o etiqueta).",
        datos_modificados="Permite cambiar el estado de despacho (Despachado / Entregado) e imprimir lotes masivos de rótulos QR.",
        pasos_procedimiento=[
            "Pulsar <b>'Historial de Pedidos'</b>.",
            "Filtrar por fecha, cliente o transporte.",
            "Para impresión de rótulos en lote: seleccionar las casillas de los pedidos y presionar <b>'Imprimir Lote Rótulos A4'</b>.",
            "Para consultar el comprobante original: presionar el icono de PDF o Excel en la fila del pedido.",
        ],
        resultado_obtenido="Hoja A4 con 8 rótulos por carilla lista para impresora láser o térmica.",
        validaciones_advertencias="Los administradores tienen acceso a la totalidad de pedidos del sistema.",
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
