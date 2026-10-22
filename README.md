# Agente de control de stock y remitos

Aplicación para controlar el stock a partir de remitos mayoristas en PDF, solicitudes de canje en Excel y pedidos de Mercado Libre en Word. Consolida las cantidades por código, genera informes de descuentos y utiliza SQLite como catálogo, manteniendo Excel como plantilla visual y formato de salida.

> **Plataforma principal:** Windows · **Lenguaje:** Python 3.10+

## Contenido

- [Funciones](#funciones)
- [Requisitos e instaladores](#requisitos-e-instaladores)
- [Instalación](#instalación)
- [Configuración](#configuración)
- [Preparar los archivos](#preparar-los-archivos)
- [Uso](#uso)
- [Flujo de procesamiento](#flujo-de-procesamiento)
- [Guía para desarrolladores](#guía-para-desarrolladores)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Notas operativas](#notas-operativas)

## Funciones

- Lee remitos mayoristas en PDF, planillas de canje `.xlsx` y pedidos de Mercado Libre en `.docx`.
- Consolida productos repetidos por código y suma sus cantidades.
- Compara el total de unidades extraídas de un remito con el total declarado y muestra discrepancias.
- Genera el informe de descuentos en Excel `.xls` y PDF A4 vertical, con márgenes de 2 cm, el formato visual de `Productos.xlsx`, el contador de productos descontados y sin columnas de stock inicial/final.
- Señala en el informe los productos que no están en el catálogo.
- Compara las líneas numeradas de Mercado Libre con el catálogo y descuenta la cantidad indicada solo si encuentra una coincidencia clara.
- Migra el catálogo de `Productos.xlsx` una sola vez a `data/productos.sqlite3`; genera los informes desde SQLite, conserva el orden y las filas repetidas de la plantilla, y sincroniza las altas y ediciones desde el panel administrador con una copia de seguridad previa.
- Ofrece una interfaz gráfica de escritorio con selección de fuentes, tema oscuro/claro, actividad en segundo plano e historial de informes.
- En Flet, protege el acceso con cuentas locales en SQLite y roles de administrador, operador y consulta.
- Permite abrir y compartir el informe seleccionado por correo o WhatsApp Web; el usuario adjunta el archivo y confirma el envío.
- Incluye ejecución automática, simulación y un menú interactivo de consola para procesar fuentes por separado, consultar el historial y restaurar documentos.
- Permite restaurar documentos archivados seleccionando la fecha de descuento registrada en los informes.
- Incluye un CRUD de productos para administradores: consulta y búsqueda, altas, edición de código/nombre/stock, y bajas lógicas con opción de reactivación. Las ediciones se sincronizan con SQLite y `Productos.xlsx`; los productos inactivos se conservan, pero se omiten en futuros informes.
- Incluye un chat local por intenciones para consultar el estado y los informes, recibir ayuda y ejecutar simulaciones de solo lectura, sin enviar mensajes a servicios externos.

## Requisitos e instaladores

| Herramienta                                  | Uso                                                  | Descarga                                                                                                                            |
| -------------------------------------------- | ---------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Python 3.10 o posterior                      | Ejecutar la aplicación                              | [Descargas oficiales de Python para Windows](https://www.python.org/downloads/windows/)                                              |
| Git for Windows *(opcional)*               | Clonar y actualizar el repositorio desde la terminal | [Descarga oficial de Git](https://git-scm.com/download/win)                                                                          |
| Visual Studio Code *(opcional)*            | Editar el código y abrir la terminal integrada      | [Descarga oficial de VS Code](https://code.visualstudio.com/Download)                                                                |
| Microsoft Excel o LibreOffice *(opcional)* | Revisar los archivos `.xls` y `.xlsx`            | [Microsoft 365](https://www.microsoft.com/microsoft-365) · [LibreOffice](https://www.libreoffice.org/download/download-libreoffice/) |

La instalación de Python incluye `pip`, que se usa para instalar las dependencias del proyecto. Al instalar Python en Windows, activa la opción **Add python.exe to PATH** si aparece en el instalador.

Las dependencias de la aplicación están enumeradas en [`requirements.txt`](requirements.txt). `gspread` y `google-auth` se usan para la integración con Google Sheets; la aplicación opera con el catálogo local de Excel. Tkinter está incluido en las instalaciones estándar de Python para Windows.

La interfaz Flet se inicia desde `ejecutar.bat` o con `python main.py`. Al iniciar por primera vez, crea la cuenta de administrador; en los siguientes inicios solicita usuario y contraseña. La interfaz Tkinter permanece disponible con `python main.py --tkinter`.

```powershell
python -m pip install -r requirements.txt
python main.py
```

Para generar un ejecutable independiente de Windows con el logo de la aplicación, instala también las dependencias de compilación y ejecuta `crear_exe.bat`:

```powershell
python -m pip install -r requirements-build.txt
.\crear_exe.bat
```

El ejecutable queda en `dist\StockAgent.exe`. Para usarlo o distribuirlo, conserva junto a él la carpeta `Descuentos` con `Productos.xlsx`; la compilación copia el catálogo actual automáticamente. Los documentos pendientes, informes y las bases SQLite de usuarios y productos se guardan junto al ejecutable; no se incluyen en el paquete y se crean en el primer inicio. La interfaz Flet usa la base de usuarios para las cuentas y no necesita `.env`. Este archivo solo se requiere para las funciones administrativas de la interfaz Tkinter antigua.

Las cuentas se guardan en `data/usuarios.sqlite3` y el catálogo en `data/productos.sqlite3`, bajo la carpeta del proyecto al ejecutarlo desde el código, o junto al ejecutable al abrir la versión empaquetada. La primera cuenta se crea como administrador. Desde **Gestionar usuarios**, un administrador puede crear usuarios, cambiar roles y activar o desactivar cuentas. Los roles son:

- **Administrador**: procesamiento, simulación, informes, restauración de documentos, alta de productos y gestión de usuarios.
- **Operador**: procesamiento, simulación e informes.
- **Consulta**: solo consulta del estado e informes.

Las contraseñas se almacenan con hash PBKDF2-HMAC-SHA256 y sal aleatoria; la aplicación nunca las guarda en texto plano. Protege el acceso a la carpeta `data/` y respalda la base SQLite periódicamente con la aplicación cerrada. La autenticación por roles se aplica a Flet; la interfaz Tkinter y los modos de consola antiguos continúan disponibles como rutas separadas.

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

La interfaz Flet crea la cuenta inicial de administrador en pantalla; no requiere configurar credenciales en `.env`. Si utilizas la interfaz Tkinter antigua, su función de alta administrativa aún usa estas variables:

```dotenv
_ADMIN_USUARIO=tu_usuario
_ADMIN_CLAVE=tu_contraseña
```

Estas credenciales solo se solicitan al elegir **Agregar producto** en la interfaz Tkinter antigua. Se permiten hasta tres intentos; si falta cualquiera de las dos variables, la opción deniega el acceso y muestra un aviso. En Flet, el administrador autenticado puede gestionar el catálogo desde **Gestionar productos**.

Flet carga el archivo `.env` si existe, pero no lo necesita para iniciar sesión ni para las funciones de administración de usuarios o de alta de productos. Estas cuentas y permisos se administran desde `data/usuarios.sqlite3`.

El chat de la pestaña **Chat con agente** funciona localmente, sin clave API ni servicios externos. Reconoce consultas sobre estado y archivos pendientes, informes, ayuda y solicitudes de simulación. También acepta los comandos `/estado`, `/informes`, `/ayuda` y `/simular`. La simulación es de solo lectura; no guarda informes, no modifica el catálogo ni mueve documentos. El chat no puede iniciar un procesamiento real. Los resultados de las simulaciones aparecen en la pestaña **Actividad**.

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

Solo `Productos.xlsx` es obligatorio crear manualmente. En la primera ejecución, el agente importa sus productos a `data/productos.sqlite3`; la importación conserva la posición y las filas repetidas por código. Desde entonces SQLite es la fuente de datos. Las altas nuevas se guardan también en el libro, debajo del producto de referencia. Antes de cada alta o edición se crea `Productos_backup.xlsx`. Las bajas administrativas son lógicas: conservan el producto en el catálogo y la plantilla, pero lo excluyen de futuros informes hasta reactivarlo. Al iniciar, el agente crea las carpetas de entrada y de informes si no existen; las subcarpetas de `descontados/` se crean al procesar documentos.

Coloca los archivos pendientes en:

| Carpeta                      | Contenido                                                           |
| ---------------------------- | ------------------------------------------------------------------- |
| `Descuentos/Mayoristas/`   | Remitos mayoristas `.pdf`                                         |
| `Descuentos/Canjes/`       | Planillas de canje `.xlsx`                                        |
| `Descuentos/MercadoLibre/` | Documentos Word `.docx`, con una descripción por párrafo o fila |

El catálogo de importación y plantilla visual debe estar en `Descuentos/Productos.xlsx`. El gestor detecta las columnas por sus encabezados y usa la hoja `Stock` cuando existe; si no, usa la hoja activa. En la plantilla incorporada, la hoja `Hoja1` ya no incluye la columna «UNIDADES»: el código está en A, el producto en B y los datos de stock en C (`Stock Inicial`), D (`Descuento`) y E (`Stock Final`), con productos desde la fila 4. Los stocks vacíos se interpretan como cero. La primera carga crea `data/productos.sqlite3`; las ejecuciones siguientes leen los productos y su orden desde SQLite. Las altas nuevas se insertan debajo del producto de referencia; las ediciones sincronizan el código, el nombre y el stock entre la base y todas las filas correspondientes en la plantilla, siempre con una copia previa en `Productos_backup.xlsx`. También se mantiene compatibilidad con catálogos anteriores que usan código, descripción y stock en A, B y C desde la fila 3.

El archivo agregado estaba guardado como XLS binario pese a tener extensión `.xlsx`; ya se convirtió a XLSX real y se conservó el original como `Productos_original.xls`. No renombres ese respaldo como `Productos.xlsx`.

Para leer un canje, el programa busca los encabezados `PEDIDO` y `CODIGO` en las primeras 14 filas y espera la descripción en la columna siguiente a `CODIGO`. Los PDF deben contener texto extraíble y respetar el formato reconocido por el parser. No se incluye OCR para documentos escaneados como imagen.

En los documentos de Mercado Libre, solo se procesan las líneas de producto que comienzan con un número seguido de su descripción (por ejemplo, `2 Creatina 300 g UT`); el número inicial indica cuántas unidades descontar. Se ignoran las líneas sin ese formato, como nombres de clientes y notas. La búsqueda normaliza mayúsculas, acentos, puntuación y abreviaturas habituales; si no hay coincidencia exacta, permite una aproximada solo cuando supera un umbral conservador, mantiene el mismo término inicial y no contradice las cantidades del nombre. Si dos productos quedan demasiado parecidos, no descuenta y deja la línea pendiente para revisión.

## Uso

### Interfaz gráfica

```powershell
python main.py
```

Se abrirá la interfaz de escritorio de Flet. Desde allí puedes:

- Seleccionar una o más fuentes: remitos mayoristas, canjes o pedidos de Mercado Libre.
- La interfaz se abre en modo oscuro; puedes cambiar al modo claro desmarcando **Modo oscuro**.
- Simular el procesamiento sin guardar cambios ni mover documentos.
- Ejecutar el procesamiento real, que genera el informe y archiva los documentos después de pedir confirmación; no modifica `Productos.xlsx`. La gestión de productos del administrador agrega y edita el catálogo tanto en SQLite como en la plantilla.
- Consultar el estado de los archivos y abrir informes generados.
- Ver los informes del más reciente al más antiguo; selecciona uno y pulsa **Abrir informe seleccionado** o haz doble clic para abrirlo.
- Abrir un borrador de correo o WhatsApp Web para compartir el informe seleccionado (el más reciente se usa si no cambias la selección). El archivo se deja seleccionado en el Explorador para adjuntarlo; debes confirmar el envío en la aplicación.
- Restaurar documentos archivados a las carpetas de entrada para pruebas.
- Abrir **Gestionar productos** para buscar, agregar, editar, desactivar y reactivar productos.

El procesamiento se ejecuta en segundo plano para que la ventana siga respondiendo. También puedes iniciar la interfaz haciendo doble clic en `ejecutar.bat` o usar `dist\StockAgent.exe` después de compilarlo. Para abrir la interfaz anterior de Tkinter, ejecuta `python main.py --tkinter`.

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
4. Genera `Descuentos/descuentos/DescuentoDD-MM-AAAA_HH-MM-SS.xls` en formato Excel 97–2003 y un informe PDF con el mismo nombre base. El PDF usa hoja A4 vertical con márgenes de 2 cm. Ambos informes usan el diseño visual de la plantilla y el orden del catálogo SQLite; conservan todos los productos y las filas repetidas por código, muestran únicamente código, producto y descuento en el detalle, y colocan la fecha de generación (`DD/MM/AA`) en el encabezado. Los totales de códigos y unidades descontados aparecen al terminar el detalle del catálogo, sin mostrar stock inicial ni final.
5. Mantiene `Productos.xlsx` sin cambios. Al final del informe incluye los pedidos con productos descontados y los productos o descripciones que no se descontaron por falta de coincidencia. Los códigos repetidos se descuentan una sola vez y los productos no encontrados no se agregan al catálogo SQLite.
6. Mueve los remitos PDF a `Descuentos/descontados/Mayoristas/`, los canjes Excel a `Descuentos/descontados/Canjes/` y los documentos Word a `Descuentos/descontados/MercadoLibre/`.

Los descuentos aparecen como valores negativos. Los códigos que no están en el catálogo se incluyen al final del informe, pero no se agregan a `Productos.xlsx`. Las descripciones de Mercado Libre que no se pudieron asociar se registran como pendientes de revisión durante el procesamiento.

Cada archivo de salida incluye la fecha y la hora de ejecución (`HH-MM-SS`) en su nombre, para distinguir los informes de varias ejecuciones en un mismo día. Los informes nuevos usan el formato `.xls` de Excel 97–2003, cuyo límite es de 65.536 filas; la interfaz también sigue mostrando informes `.xlsx` anteriores.

## Guía para desarrolladores

### Arquitectura y flujo

`main.py` selecciona la interfaz o el modo de ejecución. `src/menu.py` prepara las carpetas y coordina la ejecución; `src/agent.py` orquesta la lectura de documentos, consolidación y creación del informe. Los parsers convierten cada formato de entrada en objetos `ResultadoRemito` con sus ítems, y `src/consolidator.py` agrupa las cantidades por código. `src/product_store.py` importa una vez el catálogo desde Excel y administra los productos en SQLite; `src/stock_manager.py` consulta esa base y conserva la plantilla Excel para estilos y formato de informe.

La interfaz principal está implementada en `src/flet_gui.py`. `src/gui.py` conserva la interfaz Tkinter. La autenticación local de Flet se apoya en `src/user_store.py`; `src/internal_chat.py` implementa las consultas locales del chat y `src/paths.py` determina la raíz de datos para ejecución desde código o desde el ejecutable.

### Preparar el entorno de desarrollo

Se requiere Python 3.10 o posterior. Desde la raíz del repositorio, crea un entorno virtual e instala las dependencias:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Para iniciar la interfaz Flet durante el desarrollo:

```powershell
python main.py
```

Otros modos disponibles son:

```powershell
python main.py --tkinter
python main.py --dry-run
python -m src.menu
```

La aplicación requiere `Descuentos/Productos.xlsx` para iniciar; utiliza el archivo existente como catálogo de consulta y plantilla. No uses datos reales para las pruebas automatizadas: las pruebas crean archivos temporales.

### Pruebas

El proyecto usa `unittest`. Desde la raíz del repositorio ejecuta todas las pruebas con:

```powershell
python -m unittest discover -s tests -v
```

Para ejecutar un archivo de pruebas específico:

```powershell
python -m unittest discover -s tests -p test_stock_manager.py -v
```

Las pruebas están organizadas por área: `test_stock_manager.py` cubre catálogo e informes; `test_mercado_libre_parser.py`, el análisis de pedidos DOCX; `test_flet_gui.py`, la interfaz y roles; `test_user_store.py`, las cuentas locales; `test_internal_chat.py`, el chat; y `test_app_paths.py`, la resolución de rutas.

### Dependencias y ejecutable

Las dependencias de ejecución están en `requirements.txt`. Las necesarias para empaquetar se declaran en `requirements-build.txt`. Para compilar en Windows:

```powershell
python -m pip install -r requirements-build.txt
.\crear_exe.bat
```

El script crea `dist/StockAgent.exe` y copia `Descuentos/Productos.xlsx` a `dist/Descuentos/`. Para probar el paquete, conserva esa estructura junto al ejecutable. Los datos de ejecución y las cuentas se crean junto al ejecutable según las rutas definidas por `src/paths.py`.

## Estructura del proyecto

```text
Agentes/
├── ejecutar.bat              # Lanzador para Windows
├── crear_exe.bat             # Compilación del ejecutable para Windows
├── main.py                   # Punto de entrada y modos de ejecución
├── requirements.txt          # Dependencias de Python
├── requirements-build.txt    # Dependencias adicionales para crear el .exe
├── src/paths.py              # Resolución de la carpeta de datos en ejecución
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

`main.py`, `ejecutar.bat`, `crear_exe.bat`, los archivos de dependencias, `.env` y `Descuentos/` permanecen en la raíz del proyecto. El resto de los módulos Python se encuentra dentro de `src/`.

## Notas operativas

- Ejecuta primero una simulación para revisar los cálculos antes de procesar documentos reales.
- Una discrepancia entre las unidades declaradas y extraídas se informa, pero no detiene por sí sola el procesamiento. Revisa el documento antes de una ejecución real.
- El procesamiento real genera el informe y mueve los documentos, pero no modifica `Productos.xlsx`. Los productos se administran principalmente en `data/productos.sqlite3`; las altas y ediciones se reflejan en la plantilla y crean `Productos_backup.xlsx` antes de modificarla. Las bajas lógicas se conservan en SQLite y Excel y se excluyen de informes hasta reactivarlas. Conserva copias de seguridad de ambas fuentes antes de realizar mantenimiento manual.
- La opción de restauración **copia** los documentos archivados a las carpetas pendientes; no elimina los originales archivados.
- La autenticación mediante `.env` está pensada para uso local; no es un sistema de autenticación para una aplicación expuesta a usuarios remotos.
