# Agente de control de stock y remitos

Aplicación para controlar el stock a partir de remitos mayoristas en PDF, solicitudes de canje en Excel y pedidos de Mercado Libre en Word. Consolida las cantidades por código, genera informes de descuentos y actualiza un catálogo local de Excel.

> **Plataforma principal:** Windows · **Lenguaje:** Python 3.10+

## Contenido

- [Funciones](#funciones)
- [Requisitos e instaladores](#requisitos-e-instaladores)
- [Instalación](#instalación)
- [Configuración](#configuración)
- [Preparar los archivos](#preparar-los-archivos)
- [Uso](#uso)
- [Flujo de procesamiento](#flujo-de-procesamiento)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Notas operativas](#notas-operativas)

## Funciones

- Lee remitos mayoristas en PDF, planillas de canje `.xlsx` y pedidos de Mercado Libre en `.docx`.
- Consolida productos repetidos por código y suma sus cantidades.
- Compara el total de unidades extraídas de un remito con el total declarado y muestra discrepancias.
- Genera un informe de descuentos listo para presentar, con indicadores, detalle de stock y resumen de pedidos.
- Señala en el informe los productos que no están en el catálogo.
- Compara las líneas numeradas de Mercado Libre con el catálogo y descuenta la cantidad indicada solo si encuentra una coincidencia clara.
- En una ejecución real, actualiza el stock del catálogo y archiva los documentos procesados.
- Ofrece una interfaz gráfica de escritorio con selección de fuentes, tema oscuro/claro, actividad en segundo plano e historial de informes.
- Permite abrir y compartir el informe seleccionado por correo o WhatsApp Web; el usuario adjunta el archivo y confirma el envío.
- Incluye ejecución automática, simulación y un menú interactivo de consola para procesar fuentes por separado, consultar el historial y restaurar documentos.
- Protege con credenciales administrativas el alta de productos en el catálogo.
- Incluye un chat opcional con Google Gemini para consultas, consulta local del estado e informes y simulaciones de solo lectura.

## Requisitos e instaladores

| Herramienta                                  | Uso                                                  | Descarga                                                                                                                            |
| -------------------------------------------- | ---------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Python 3.10 o posterior                      | Ejecutar la aplicación                              | [Descargas oficiales de Python para Windows](https://www.python.org/downloads/windows/)                                              |
| Git for Windows *(opcional)*               | Clonar y actualizar el repositorio desde la terminal | [Descarga oficial de Git](https://git-scm.com/download/win)                                                                          |
| Visual Studio Code *(opcional)*            | Editar el código y abrir la terminal integrada      | [Descarga oficial de VS Code](https://code.visualstudio.com/Download)                                                                |
| Microsoft Excel o LibreOffice *(opcional)* | Revisar los archivos `.xls` y `.xlsx`              | [Microsoft 365](https://www.microsoft.com/microsoft-365) · [LibreOffice](https://www.libreoffice.org/download/download-libreoffice/) |

La instalación de Python incluye `pip`, que se usa para instalar las dependencias del proyecto. Al instalar Python en Windows, activa la opción **Add python.exe to PATH** si aparece en el instalador.

Las dependencias de la aplicación están enumeradas en [`requirements.txt`](requirements.txt). `gspread` y `google-auth` se usan para la integración con Google Sheets; la aplicación opera con el catálogo local de Excel. La interfaz gráfica utiliza Tkinter, incluido en las instalaciones estándar de Python para Windows.

## Instalación

### 1. Obtener el proyecto

Si tienes Git instalado:

```powershell
git clone https://github.com/Kniball4726/Agentes.git
cd Agentes
```

También puedes descargar el repositorio como ZIP desde [GitHub](https://github.com/Kniball4726/Agentes) y extraerlo en una carpeta local.

### 2. Comprobar Python

Abre PowerShell en la carpeta del proyecto y ejecuta:

```powershell
py --version
```

Debe mostrar Python 3.10 o posterior. Si `py` no está disponible, instala Python desde [python.org](https://www.python.org/downloads/windows/) y vuelve a abrir PowerShell.

### 3. Crear el entorno e instalar dependencias

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Si PowerShell impide activar el entorno por la política de ejecución, puedes ejecutar la aplicación con el Python del entorno sin activarlo:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## Configuración

Crea un archivo llamado `.env` en la carpeta raíz del proyecto —junto a `main.py`— con las credenciales que quieras asignar a la función administrativa:

```dotenv
_ADMIN_USUARIO=tu_usuario
_ADMIN_CLAVE=tu_contraseña
```

Estas credenciales se solicitan al elegir **Agregar producto** en la interfaz gráfica. Se permiten hasta tres intentos; si falta cualquiera de las dos variables, la opción deniega el acceso y muestra un aviso. Tras validar las credenciales, se puede insertar un producto debajo de otro código del catálogo, con stock inicial opcional. Al guardar el alta, también se actualiza `Productos_backup.xlsx`.

Para habilitar el chat con Gemini, agrega también una clave de Google AI Studio:

```dotenv
GEMINI_API_KEY=tu_clave_de_gemini
```

La clave es opcional para el resto de la aplicación. Los mensajes y el historial de conversación se envían a Google Gemini para responder; la aplicación no adjunta automáticamente el catálogo ni los documentos. La API se invoca con `store=false` y el historial se conserva solo en memoria mientras la aplicación está abierta. Los comandos `/estado` y `/informes` se resuelven localmente; `/simular` ejecuta el modo de solo lectura y no guarda informes, modifica el catálogo ni mueve documentos. El chat no puede iniciar un procesamiento real. El archivo `.env` está excluido de Git. No publiques credenciales reales ni las incluyas en capturas o archivos compartidos.

En la pestaña **Chat con Gemini** puedes escribir una consulta libre o usar `/estado`, `/informes` y `/simular`. Los resultados detallados de las simulaciones aparecen en la pestaña **Actividad**.

## Preparar los archivos

Antes de ejecutar, crea en la raíz del proyecto la carpeta `Descuentos/` y coloca dentro el catálogo `Productos.xlsx`; el programa no crea ni inicializa ese archivo y se detendrá si falta. La estructura que usa el agente es:

```text
Descuentos/
├── Productos.xlsx        # Obligatorio: catálogo y stock base
├── Mayoristas/           # Remitos PDF pendientes
├── Canjes/               # Canjes Excel pendientes
├── MercadoLibre/         # Pedidos Word pendientes
├── descuentos/           # Informes generados
└── descontados/          # Documentos procesados
    ├── Mayoristas/
    ├── Canjes/
    └── MercadoLibre/
```

Solo `Productos.xlsx` es obligatorio crear manualmente. Al iniciar, el agente crea las carpetas de entrada y de informes si no existen; las subcarpetas de `descontados/` se crean al procesar documentos. El archivo `Productos_backup.xlsx` se genera al guardar cambios en el catálogo. No se reemplaza un catálogo existente ni se inicializa desde plantillas.

Coloca los archivos pendientes en:

| Carpeta                      | Contenido                                                           |
| ---------------------------- | ------------------------------------------------------------------- |
| `Descuentos/Mayoristas/`   | Remitos mayoristas `.pdf`                                         |
| `Descuentos/Canjes/`       | Planillas de canje `.xlsx`                                        |
| `Descuentos/MercadoLibre/` | Documentos Word `.docx`, con una descripción por párrafo o fila |

El catálogo de productos debe estar en `Descuentos/Productos.xlsx`. El gestor detecta las columnas por sus encabezados y usa la hoja `Stock` cuando existe; si no, usa la hoja activa. En el catálogo incorporado, la hoja es `Hoja1`: código en A, producto en C y datos de stock en D (`Stock Inicial`), E (`Descuento`) y F (`Stock Final`), con productos desde la fila 4. Los stocks vacíos se interpretan como cero. Después de un descuento, el saldo final queda en F y se usa como stock actual en la siguiente corrida. También se mantiene compatibilidad con catálogos anteriores que usan código, descripción y stock en A, B y C desde la fila 3.

El archivo agregado estaba guardado como XLS binario pese a tener extensión `.xlsx`; ya se convirtió a XLSX real y se conservó el original como `Productos_original.xls`. No renombres ese respaldo como `Productos.xlsx`.

Para leer un canje, el programa busca los encabezados `PEDIDO` y `CODIGO` en las primeras 14 filas y espera la descripción en la columna siguiente a `CODIGO`. Los PDF deben contener texto extraíble y respetar el formato reconocido por el parser. No se incluye OCR para documentos escaneados como imagen.

En los documentos de Mercado Libre, solo se procesan las líneas de producto que comienzan con un número seguido de su descripción (por ejemplo, `2 Creatina 300 g UT`); el número inicial indica cuántas unidades descontar. Se ignoran las líneas sin ese formato, como nombres de clientes y notas. La búsqueda normaliza mayúsculas, acentos, puntuación y abreviaturas habituales; si no hay coincidencia exacta, permite una aproximada solo cuando supera un umbral conservador, mantiene el mismo término inicial y no contradice las cantidades del nombre. Si dos productos quedan demasiado parecidos, no descuenta y deja la línea pendiente para revisión.

## Uso

### Interfaz gráfica

```powershell
python main.py
```

Se abrirá la interfaz de escritorio de Tkinter. Desde allí puedes:

- Seleccionar una o más fuentes: remitos mayoristas, canjes o pedidos de Mercado Libre.
- La interfaz se abre en modo oscuro; puedes cambiar al modo claro desmarcando **Modo oscuro**.
- Simular el procesamiento sin guardar cambios ni mover documentos.
- Ejecutar el procesamiento real, que actualiza el catálogo y archiva los documentos después de pedir confirmación.
- Consultar el estado de los archivos y abrir informes generados.
- Ver los informes del más reciente al más antiguo; selecciona uno y pulsa **Abrir informe seleccionado** o haz doble clic para abrirlo.
- Abrir un borrador de correo o WhatsApp Web para compartir el informe seleccionado (el más reciente se usa si no cambias la selección). El archivo se deja seleccionado en el Explorador para adjuntarlo; debes confirmar el envío en la aplicación.
- Restaurar documentos archivados a las carpetas de entrada para pruebas.
- Validar primero las credenciales administrativas de `.env` y, solo si son correctas, abrir el formulario para agregar un producto.

El procesamiento se ejecuta en segundo plano para que la ventana siga respondiendo. También puedes iniciar la interfaz haciendo doble clic en `ejecutar.bat`.

### Menú interactivo de consola

Para abrir el menú de consola en lugar de la interfaz gráfica:

```powershell
python -m src.menu
```

El menú permite ejecutar todas las fuentes juntas o procesar solo remitos mayoristas, canjes o pedidos de Mercado Libre; también ofrece simulación, consulta del historial, restauración de documentos archivados y alta administrativa de productos. La restauración copia los archivos a las carpetas pendientes y conserva los originales archivados.

### Ejecución automática

Procesa todos los documentos pendientes, incluidos los pedidos de Mercado Libre, sin abrir la interfaz gráfica:

```powershell
python main.py --auto
```

`--all` es un alias de `--auto`.

### Simulación

```powershell
python main.py --dry-run
```

`--simulacion` es un alias de `--dry-run`. La simulación calcula y muestra el informe en la consola, pero no guarda la planilla, no actualiza `Productos.xlsx` y no mueve los documentos.

## Flujo de procesamiento

En una ejecución real, el agente:

1. Lee los documentos seleccionados de las carpetas de entrada.
2. Extrae metadatos e ítems y muestra los resultados de las verificaciones.
3. Consolida las cantidades por código de producto.
4. Genera `Descuentos/descuentos/DescuentoDD-MM-AAAA_HH-MM-SS.xls` en formato Excel 97–2003, con portada, indicadores, fondos claros, movimientos resaltados, secciones de pedidos y pendientes, panel superior inmovilizado y diseño de impresión apaisado. El detalle conserva las columnas `CÓDIGO`, `PRODUCTOS`, `STOCK INICIAL`, `DESCUENTO` y `STOCK FINAL`.
5. Actualiza en `Productos.xlsx` el stock inicial, el descuento y el stock final de los productos afectados, y guarda también `Productos_backup.xlsx`. Los códigos repetidos se descuentan una sola vez y sus filas quedan sincronizadas.
6. Mueve los remitos PDF a `Descuentos/descontados/Mayoristas/`, los canjes Excel a `Descuentos/descontados/Canjes/` y los documentos Word a `Descuentos/descontados/MercadoLibre/`.

Los descuentos aparecen como valores negativos. Los códigos que no están en el catálogo se incluyen al final del informe, pero no se agregan automáticamente a `Productos.xlsx`. Las descripciones de Mercado Libre que no se pudieron asociar se registran como pendientes de revisión en una sección aparte del informe.

Cada archivo de salida incluye la fecha y la hora de ejecución (`HH-MM-SS`) en su nombre, para distinguir los informes de varias ejecuciones en un mismo día. Los informes nuevos usan el formato `.xls` de Excel 97–2003, cuyo límite es de 65.536 filas; la interfaz también sigue mostrando informes `.xlsx` anteriores.

## Estructura del proyecto

```text
Agentes/
├── ejecutar.bat              # Lanzador para Windows
├── main.py                   # Punto de entrada y modos de ejecución
├── requirements.txt          # Dependencias de Python
├── src/                       # Código fuente y módulos internos
│   ├── __init__.py
│   ├── agent.py               # Orquestación de lectura, consolidación y descuentos
│   ├── canjes_parser.py       # Lectura de planillas de canje
│   ├── consolidator.py        # Agrupación de productos por código
│   ├── mercado_libre_parser.py # Lectura y asociación de pedidos DOCX al catálogo
│   ├── menu.py                # Menú, autenticación y archivado
│   ├── remito_parser.py       # Lectura y verificación de remitos PDF
│   ├── sheets_manager.py      # Integración de stock con Google Sheets
│   └── stock_manager.py       # Catálogo Excel e informes de descuentos
└── Descuentos/
    ├── Productos.xlsx        # Catálogo y stock base
    ├── Productos_original.xls # Respaldo del archivo binario original (tras la conversión)
    ├── Mayoristas/           # Creada al iniciar; remitos PDF pendientes
    ├── Canjes/               # Creada al iniciar; canjes Excel pendientes
    ├── MercadoLibre/         # Creada al iniciar; pedidos Word pendientes
    ├── descuentos/           # Creada al iniciar; informes de descuentos generados
    └── descontados/          # Documentos procesados
        ├── Mayoristas/       # Creadas al procesar documentos
        ├── Canjes/
        └── MercadoLibre/
```

`main.py`, `ejecutar.bat`, `requirements.txt`, `.env` y `Descuentos/` permanecen en la raíz del proyecto. El resto de los módulos Python se encuentra dentro de `src/`.

## Notas operativas

- Ejecuta primero una simulación para revisar los cálculos antes de procesar documentos reales.
- Una discrepancia entre las unidades declaradas y extraídas se informa, pero no detiene por sí sola el procesamiento. Revisa el documento antes de una ejecución real.
- La ejecución real modifica el catálogo y mueve los documentos. Mantén copias de seguridad antes de procesar información importante.
- La opción de restauración **copia** los documentos archivados a las carpetas pendientes; no elimina los originales archivados.
- La autenticación mediante `.env` está pensada para uso local; no es un sistema de autenticación para una aplicación expuesta a usuarios remotos.
