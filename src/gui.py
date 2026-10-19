"""Interfaz gráfica de escritorio para el agente de control de stock."""

import contextlib
import os
import queue
import subprocess
import threading
import traceback
import tkinter as tk
import urllib.parse
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable, TextIO

from .internal_chat import detectar_intencion
from .menu import MenuAgente
from .stock_manager import StockManager


class _QueueWriter(TextIO):
    def __init__(self, eventos: queue.Queue[tuple[str, str]]):
        self.eventos = eventos

    def write(self, texto: str) -> int:
        if texto:
            self.eventos.put(("log", texto))
        return len(texto)

    def flush(self) -> None:
        pass


class InterfazGrafica:
    def __init__(self):
        self.menu = MenuAgente()
        self.root = tk.Tk()
        self.root.title("Agente de control de stock y remitos")
        self.root.geometry("900x700")
        self.root.minsize(760, 560)

        self.eventos: queue.Queue[tuple[str, str]] = queue.Queue()
        self.ocupado = False
        self.incluir_mayoristas = tk.BooleanVar(value=True)
        self.incluir_canjes = tk.BooleanVar(value=True)
        self.incluir_mercado_libre = tk.BooleanVar(value=True)
        self.modo_oscuro = tk.BooleanVar(value=True)
        self.estilo = ttk.Style(self.root)
        self.estilo.theme_use("clam")
        self._botones_tarea: list[ttk.Button] = []
        self._rutas_informes: list[Path] = []
        self._crear_interfaz()
        self._aplicar_tema()
        self._actualizar_estado()
        self.root.after(100, self._procesar_eventos)

    def _crear_interfaz(self) -> None:
        contenedor = ttk.Frame(self.root, padding=16)
        contenedor.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            contenedor,
            text="Agente de control de stock y remitos",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            contenedor,
            text="Selecciona las fuentes que quieres procesar.",
        ).pack(anchor=tk.W, pady=(2, 12))
        ttk.Checkbutton(
            contenedor,
            text="Modo oscuro",
            variable=self.modo_oscuro,
            command=self._aplicar_tema,
        ).pack(anchor=tk.E, pady=(0, 8))

        estado = ttk.LabelFrame(contenedor, text="Estado de archivos", padding=10)
        estado.pack(fill=tk.X)
        self.etiqueta_estado = ttk.Label(estado, text="")
        self.etiqueta_estado.pack(anchor=tk.W)
        ttk.Button(
            estado, text="Actualizar estado", command=self._actualizar_estado
        ).pack(anchor=tk.E, pady=(5, 0))

        fuentes = ttk.LabelFrame(contenedor, text="Fuentes pendientes", padding=10)
        fuentes.pack(fill=tk.X, pady=(10, 0))
        ttk.Checkbutton(
            fuentes, text="Mayoristas (PDF)", variable=self.incluir_mayoristas
        ).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Checkbutton(
            fuentes, text="Canjes (Excel)", variable=self.incluir_canjes
        ).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Checkbutton(
            fuentes, text="Mercado Libre (DOCX)", variable=self.incluir_mercado_libre
        ).pack(side=tk.LEFT)

        acciones = ttk.Frame(contenedor)
        acciones.pack(fill=tk.X, pady=10)
        boton_procesar = ttk.Button(
            acciones,
            text="Procesar y actualizar stock",
            command=lambda: self._procesar(simulacion=False),
        )
        boton_procesar.pack(side=tk.LEFT, padx=(0, 8))
        boton_simular = ttk.Button(
            acciones,
            text="Simular (sin guardar)",
            command=lambda: self._procesar(simulacion=True),
        )
        boton_simular.pack(side=tk.LEFT, padx=(0, 8))
        self._botones_tarea.extend((boton_procesar, boton_simular))

        herramientas = ttk.LabelFrame(contenedor, text="Herramientas", padding=10)
        herramientas.pack(fill=tk.X)
        boton_abrir = ttk.Button(
            herramientas, text="Abrir informe seleccionado", command=self._abrir_informe
        )
        boton_abrir.pack(side=tk.LEFT, padx=(0, 8))
        boton_restaurar = ttk.Button(
            herramientas,
            text="Restaurar documentos archivados",
            command=self._restaurar,
        )
        boton_restaurar.pack(side=tk.LEFT, padx=(0, 8))
        boton_agregar = ttk.Button(
            herramientas, text="Agregar producto", command=self._mostrar_formulario_producto
        )
        boton_agregar.pack(side=tk.LEFT)
        self._botones_tarea.extend((boton_restaurar, boton_agregar))

        compartir = ttk.LabelFrame(contenedor, text="Compartir informe seleccionado", padding=10)
        compartir.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(
            compartir,
            text="Enviar por correo",
            command=self._compartir_por_correo,
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            compartir,
            text="Enviar por WhatsApp",
            command=self._compartir_por_whatsapp,
        ).pack(side=tk.LEFT)

        contenido = ttk.Frame(contenedor)
        contenido.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        informes = ttk.LabelFrame(contenido, text="Informes generados", padding=8)
        informes.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self.lista_informes = tk.Listbox(informes, width=34, height=12)
        self.lista_informes.pack(side=tk.LEFT, fill=tk.Y, expand=True)
        self.lista_informes.bind("<Double-Button-1>", self._abrir_informe_evento)
        self.lista_informes.bind("<Return>", self._abrir_informe_evento)
        scroll_informes = ttk.Scrollbar(
            informes, orient=tk.VERTICAL, command=self.lista_informes.yview
        )
        scroll_informes.pack(side=tk.RIGHT, fill=tk.Y)
        self.lista_informes.configure(yscrollcommand=scroll_informes.set)

        self.paneles = ttk.Notebook(contenido)
        self.paneles.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        salida = ttk.Frame(self.paneles, padding=8)
        self.paneles.add(salida, text="Actividad")
        self.consola = tk.Text(salida, wrap=tk.WORD, height=16, state=tk.DISABLED)
        self.consola.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_salida = ttk.Scrollbar(salida, orient=tk.VERTICAL, command=self.consola.yview)
        scroll_salida.pack(side=tk.RIGHT, fill=tk.Y)
        self.consola.configure(yscrollcommand=scroll_salida.set)

        chat = ttk.Frame(self.paneles, padding=8)
        self.paneles.add(chat, text="Chat con agente")
        ttk.Label(
            chat,
            text=(
                "Chat local: tus mensajes no salen de este equipo. Pregunta "
                "por el estado, los informes, pide ayuda o solicita una simulación."
            ),
            wraplength=500,
        ).pack(anchor=tk.W, pady=(0, 8))
        self.etiqueta_estado_chat = ttk.Label(
            chat, text="Agente interno listo. Comandos: /estado, /informes, /simular."
        )
        self.etiqueta_estado_chat.pack(side=tk.BOTTOM, anchor=tk.W, pady=(5, 0))

        entrada_chat = ttk.Frame(chat)
        entrada_chat.pack(side=tk.BOTTOM, fill=tk.X, pady=(8, 0))
        self.boton_enviar_chat = ttk.Button(
            entrada_chat, text="Enviar", command=self._enviar_mensaje_chat
        )
        self.boton_enviar_chat.pack(side=tk.RIGHT, anchor=tk.S)
        self.entrada_chat = tk.Text(entrada_chat, wrap=tk.WORD, height=3)
        self.entrada_chat.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self.entrada_chat.bind("<Control-Return>", self._enviar_mensaje_chat_evento)

        conversacion = ttk.Frame(chat)
        conversacion.pack(fill=tk.BOTH, expand=True)
        self.transcripcion_chat = tk.Text(
            conversacion, wrap=tk.WORD, height=12, state=tk.DISABLED
        )
        scroll_chat = ttk.Scrollbar(
            conversacion, orient=tk.VERTICAL, command=self.transcripcion_chat.yview
        )
        scroll_chat.pack(side=tk.RIGHT, fill=tk.Y)
        self.transcripcion_chat.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.transcripcion_chat.configure(yscrollcommand=scroll_chat.set)

        self.etiqueta_estado_tarea = ttk.Label(contenedor, text="Listo")
        self.etiqueta_estado_tarea.pack(anchor=tk.W, pady=(8, 0))

    def _aplicar_tema(self) -> None:
        if self.modo_oscuro.get():
            colores = {
                "fondo": "#202124",
                "superficie": "#2b2d31",
                "texto": "#e8eaed",
                "secundario": "#bdc1c6",
                "borde": "#484a4e",
                "seleccion": "#365f91",
                "boton": "#3c4043",
                "activo": "#4a4f55",
            }
        else:
            colores = {
                "fondo": "#f3f4f6",
                "superficie": "#ffffff",
                "texto": "#202124",
                "secundario": "#5f6368",
                "borde": "#c7c9cc",
                "seleccion": "#cfe2f3",
                "boton": "#e8eaed",
                "activo": "#dadce0",
            }

        self.root.configure(background=colores["fondo"])
        self.estilo.configure(".", background=colores["fondo"], foreground=colores["texto"])
        self.estilo.configure(
            "TFrame",
            background=colores["fondo"],
        )
        self.estilo.configure(
            "TLabel",
            background=colores["fondo"],
            foreground=colores["texto"],
        )
        self.estilo.configure(
            "TLabelframe",
            background=colores["fondo"],
            bordercolor=colores["borde"],
        )
        self.estilo.configure(
            "TLabelframe.Label",
            background=colores["fondo"],
            foreground=colores["texto"],
        )
        self.estilo.configure(
            "TButton",
            background=colores["boton"],
            foreground=colores["texto"],
            bordercolor=colores["borde"],
            focuscolor=colores["seleccion"],
        )
        self.estilo.map(
            "TButton",
            background=[
                ("disabled", colores["fondo"]),
                ("pressed", colores["seleccion"]),
                ("active", colores["activo"]),
            ],
            foreground=[("disabled", colores["secundario"])],
        )
        self.estilo.configure(
            "TCheckbutton",
            background=colores["fondo"],
            foreground=colores["texto"],
        )
        self.estilo.map(
            "TCheckbutton",
            background=[("active", colores["fondo"])],
            foreground=[("disabled", colores["secundario"])],
        )
        self.estilo.configure(
            "TEntry",
            fieldbackground=colores["superficie"],
            foreground=colores["texto"],
            insertcolor=colores["texto"],
            bordercolor=colores["borde"],
        )
        self.estilo.configure(
            "Vertical.TScrollbar",
            background=colores["boton"],
            troughcolor=colores["fondo"],
            bordercolor=colores["fondo"],
            arrowcolor=colores["texto"],
        )

        def aplicar_a_hijos(widget: tk.Misc) -> None:
            if isinstance(widget, (tk.Tk, tk.Toplevel)):
                widget.configure(background=colores["fondo"])
            elif widget.winfo_class() in ("Text", "Entry"):
                widget.configure(
                    background=colores["superficie"],
                    foreground=colores["texto"],
                    insertbackground=colores["texto"],
                    selectbackground=colores["seleccion"],
                    selectforeground=colores["texto"],
                    highlightbackground=colores["borde"],
                    highlightcolor=colores["seleccion"],
                )
            elif isinstance(widget, tk.Listbox):
                widget.configure(
                    background=colores["superficie"],
                    foreground=colores["texto"],
                    selectbackground=colores["seleccion"],
                    selectforeground=colores["texto"],
                    highlightbackground=colores["borde"],
                    highlightcolor=colores["seleccion"],
                )
            for hijo in widget.winfo_children():
                aplicar_a_hijos(hijo)

        aplicar_a_hijos(self.root)

    def _centrar_sobre_ventana_principal(self, ventana: tk.Toplevel) -> None:
        self.root.update_idletasks()
        ventana.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - ventana.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - ventana.winfo_height()) // 2
        ventana.geometry(f"+{x}+{y}")

    def _actualizar_estado(self) -> None:
        mayoristas, canjes, mercado_libre = self.menu._obtener_pendientes()
        archivados = self.menu._obtener_archivados()
        total_archivados = sum(len(grupo) for grupo in archivados)
        informes = self.menu._obtener_generados()
        self.etiqueta_estado.configure(
            text=(
                f"Pendientes: {len(mayoristas)} PDF · {len(canjes)} Excel · "
                f"{len(mercado_libre)} DOCX     |     "
                f"Archivados: {total_archivados}     |     "
                f"Informes: {len(informes)}"
            )
        )
        self._rutas_informes = sorted(
            informes,
            key=lambda ruta: (ruta.stat().st_mtime_ns, ruta.name.casefold()),
            reverse=True,
        )
        self.lista_informes.delete(0, tk.END)
        for ruta in self._rutas_informes:
            self.lista_informes.insert(tk.END, ruta.name)
        if self._rutas_informes:
            self.lista_informes.selection_set(0)
            self.lista_informes.activate(0)

    def _escribir_salida(self, texto: str) -> None:
        self.consola.configure(state=tk.NORMAL)
        self.consola.insert(tk.END, texto)
        self.consola.see(tk.END)
        self.consola.configure(state=tk.DISABLED)

    def _escribir_chat(self, emisor: str, texto: str) -> None:
        self.transcripcion_chat.configure(state=tk.NORMAL)
        self.transcripcion_chat.insert(tk.END, f"{emisor}:\n{texto}\n\n")
        self.transcripcion_chat.see(tk.END)
        self.transcripcion_chat.configure(state=tk.DISABLED)

    def _enviar_mensaje_chat_evento(self, _evento: tk.Event) -> str:
        self._enviar_mensaje_chat()
        return "break"

    def _enviar_mensaje_chat(self) -> None:
        mensaje = self.entrada_chat.get("1.0", tk.END).strip()
        if not mensaje:
            return

        self.entrada_chat.delete("1.0", tk.END)
        self._escribir_chat("Tú", mensaje)
        intencion = detectar_intencion(mensaje)
        if intencion == "estado":
            self._escribir_chat("Agente", self._resumen_estado())
        elif intencion == "informes":
            self._escribir_chat("Agente", self._resumen_informes())
        elif intencion == "simular":
            self._simular_desde_chat()
        elif intencion == "saludo":
            self._escribir_chat(
                "Agente",
                "¡Hola! Puedo consultar el estado y los informes, explicar cómo "
                "usar la aplicación o iniciar una simulación de solo lectura. "
                "Escribe /ayuda para ver los comandos.",
            )
        elif intencion == "ayuda":
            self._escribir_chat(
                "Agente",
                "Puedo consultar archivos pendientes y archivados (/estado), "
                "listar informes (/informes) o simular el procesamiento "
                "seleccionado (/simular). La simulación no guarda cambios ni "
                "mueve documentos. El chat no puede iniciar un procesamiento real.",
            )
        else:
            self._escribir_chat(
                "Agente",
                "Soy el agente local y solo entiendo consultas sobre el estado, "
                "los informes, ayuda y simulaciones. Prueba /ayuda. No envío "
                "mensajes a servicios externos.",
            )
        self.etiqueta_estado_chat.configure(text="Respuesta del agente interno.")

    def _resumen_estado(self) -> str:
        mayoristas, canjes, mercado_libre = self.menu._obtener_pendientes()
        archivados = self.menu._obtener_archivados()
        informes = self.menu._obtener_generados()
        return (
            f"Pendientes: {len(mayoristas)} PDF mayoristas, {len(canjes)} Excel "
            f"de canjes y {len(mercado_libre)} DOCX de Mercado Libre. "
            f"Archivados: {sum(map(len, archivados))}. "
            f"Informes disponibles: {len(informes)}."
        )

    def _resumen_informes(self) -> str:
        informes = self.menu._obtener_generados()
        if not informes:
            return "Todavía no hay informes generados."
        nombres = [ruta.name for ruta in informes[-20:]]
        listado = "\n".join(f"• {nombre}" for nombre in nombres)
        return f"Informes disponibles ({len(informes)}):\n{listado}"

    def _simular_desde_chat(self) -> None:
        if self.ocupado:
            self._escribir_chat(
                "Agente",
                "No puedo iniciar la simulación mientras otra tarea está en curso.",
            )
            return
        fuentes = (
            self.incluir_mayoristas.get(),
            self.incluir_canjes.get(),
            self.incluir_mercado_libre.get(),
        )
        if not any(fuentes):
            self._escribir_chat(
                "Agente",
                "Selecciona al menos una fuente en la ventana principal antes de simular.",
            )
            return

        self._escribir_chat(
            "Agente",
            "Inicié una simulación de solo lectura. Revisa sus resultados en la pestaña Actividad.",
        )
        self._iniciar_tarea(
            "Simulación solicitada desde el chat",
            lambda: self.menu.procesar(
                incluir_mayoristas=fuentes[0],
                incluir_canjes=fuentes[1],
                incluir_mercado_libre=fuentes[2],
                simulacion=True,
            ),
        )

    def _iniciar_tarea(self, nombre: str, accion: Callable[[], None]) -> None:
        if self.ocupado:
            return
        self.ocupado = True
        self.etiqueta_estado_tarea.configure(text=f"En curso: {nombre}")
        for boton in self._botones_tarea:
            boton.configure(state=tk.DISABLED)

        def ejecutar() -> None:
            escritor = _QueueWriter(self.eventos)
            try:
                with contextlib.redirect_stdout(escritor), contextlib.redirect_stderr(
                    escritor
                ):
                    accion()
            except Exception:
                self.eventos.put(("error", traceback.format_exc()))
            else:
                self.eventos.put(("done", ""))

        threading.Thread(target=ejecutar, daemon=True).start()

    def _procesar(self, simulacion: bool) -> None:
        incluir_mayoristas = self.incluir_mayoristas.get()
        incluir_canjes = self.incluir_canjes.get()
        incluir_mercado_libre = self.incluir_mercado_libre.get()
        if not any((incluir_mayoristas, incluir_canjes, incluir_mercado_libre)):
            messagebox.showwarning(
                "Sin fuentes seleccionadas",
                "Selecciona al menos una fuente para procesar.",
                parent=self.root,
            )
            return

        tipo = "Simulación" if simulacion else "Procesamiento real"
        if not simulacion and not messagebox.askyesno(
            "Confirmar procesamiento",
            "Esta operación actualizará el catálogo y moverá los documentos "
            "procesados a 'descontados'. ¿Quieres continuar?",
            parent=self.root,
        ):
            return

        self._iniciar_tarea(
            tipo,
            lambda: self.menu.procesar(
                incluir_mayoristas=incluir_mayoristas,
                incluir_canjes=incluir_canjes,
                incluir_mercado_libre=incluir_mercado_libre,
                simulacion=simulacion,
            ),
        )

    def _procesar_eventos(self) -> None:
        try:
            while True:
                tipo, contenido = self.eventos.get_nowait()
                if tipo == "log":
                    self._escribir_salida(contenido)
                elif tipo == "error":
                    self._escribir_salida(f"\n[ERROR]\n{contenido}\n")
                    self.ocupado = False
                    self.etiqueta_estado_tarea.configure(text="La operación terminó con un error.")
                    for boton in self._botones_tarea:
                        boton.configure(state=tk.NORMAL)
                    self._actualizar_estado()
                    messagebox.showerror(
                        "Error durante la operación",
                        "La operación no pudo completarse. Consulta el panel "
                        "Actividad para ver los detalles.",
                        parent=self.root,
                    )
                elif tipo == "done":
                    self.ocupado = False
                    self.etiqueta_estado_tarea.configure(text="Operación finalizada.")
                    for boton in self._botones_tarea:
                        boton.configure(state=tk.NORMAL)
                    self._actualizar_estado()
        except queue.Empty:
            pass
        self.root.after(100, self._procesar_eventos)

    def _abrir_informe(self) -> None:
        seleccion = self.lista_informes.curselection()
        if not seleccion:
            messagebox.showinfo(
                "Selecciona un informe",
                "Selecciona un informe de la lista para abrirlo.",
                parent=self.root,
            )
            return
        ruta = self._rutas_informes[seleccion[0]]
        try:
            os.startfile(ruta)  # type: ignore[attr-defined]
        except OSError as error:
            messagebox.showerror(
                "No se pudo abrir el informe", str(error), parent=self.root
            )

    def _abrir_informe_evento(self, _evento: tk.Event) -> str:
        self._abrir_informe()
        return "break"

    def _obtener_informe_seleccionado(self) -> Path | None:
        seleccion = self.lista_informes.curselection()
        if seleccion:
            return self._rutas_informes[seleccion[0]]
        if self._rutas_informes:
            return self._rutas_informes[0]
        messagebox.showinfo(
            "No hay informes",
            "Todavía no hay informes generados para compartir.",
            parent=self.root,
        )
        return None

    def _abrir_carpeta_con_informe(self, ruta: Path) -> None:
        subprocess.Popen(["explorer.exe", f"/select,{ruta}"])

    def _compartir_por_correo(self) -> None:
        ruta = self._obtener_informe_seleccionado()
        if ruta is None:
            return
        if not messagebox.askyesno(
            "Compartir por correo",
            f"Se abrirá tu aplicación de correo y el Explorador con este archivo "
            f"seleccionado:\n\n{ruta.name}\n\nAdjúntalo al mensaje y confirma "
            "el envío desde tu aplicación. ¿Continuar?",
            parent=self.root,
        ):
            return

        asunto = f"Informe de descuentos: {ruta.name}"
        cuerpo = f"Adjunto el informe de descuentos {ruta.name}."
        url = "mailto:?" + urllib.parse.urlencode(
            {"subject": asunto, "body": cuerpo}
        )
        try:
            self._abrir_carpeta_con_informe(ruta)
            os.startfile(url)  # type: ignore[attr-defined]
        except OSError as error:
            messagebox.showerror(
                "No se pudo abrir el correo",
                f"No se pudo abrir la aplicación de correo o el archivo:\n{error}",
                parent=self.root,
            )

    def _compartir_por_whatsapp(self) -> None:
        ruta = self._obtener_informe_seleccionado()
        if ruta is None:
            return
        if not messagebox.askyesno(
            "Compartir por WhatsApp",
            f"Se abrirá WhatsApp Web y el Explorador con este archivo "
            f"seleccionado:\n\n{ruta.name}\n\nElige el chat, adjunta el archivo "
            "desde el Explorador y confirma el envío en WhatsApp. ¿Continuar?",
            parent=self.root,
        ):
            return

        try:
            self._abrir_carpeta_con_informe(ruta)
            if not webbrowser.open("https://web.whatsapp.com/"):
                raise RuntimeError("No se pudo abrir WhatsApp Web en el navegador.")
        except (OSError, RuntimeError) as error:
            messagebox.showerror(
                "No se pudo abrir WhatsApp",
                f"No se pudo abrir WhatsApp Web o el archivo:\n{error}",
                parent=self.root,
            )

    def _restaurar(self) -> None:
        if not messagebox.askyesno(
            "Restaurar documentos",
            "Se copiarán todos los documentos archivados a sus carpetas "
            "pendientes. Si existe un archivo con el mismo nombre, puede "
            "sobrescribirse. ¿Continuar?",
            parent=self.root,
        ):
            return
        self._iniciar_tarea("Restauración de documentos", self.menu.restaurar_para_pruebas)

    def _mostrar_formulario_producto(self) -> None:
        usuario_admin = os.getenv("_ADMIN_USUARIO")
        clave_admin = os.getenv("_ADMIN_CLAVE")
        if not usuario_admin or not clave_admin:
            messagebox.showerror(
                "Credenciales no configuradas",
                "Define _ADMIN_USUARIO y _ADMIN_CLAVE en el archivo .env.",
                parent=self.root,
            )
            return

        acceso = tk.Toplevel(self.root)
        acceso.title("Validar acceso administrativo")
        acceso.transient(self.root)
        acceso.grab_set()
        acceso.resizable(False, False)

        ttk.Label(acceso, text="Usuario administrador").grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5
        )
        usuario = ttk.Entry(acceso, width=36)
        usuario.grid(row=0, column=1, padx=10, pady=5)
        ttk.Label(acceso, text="Contraseña").grid(
            row=1, column=0, sticky=tk.W, padx=10, pady=5
        )
        clave = ttk.Entry(acceso, show="*", width=36)
        clave.grid(row=1, column=1, padx=10, pady=5)
        intentos = 0

        def validar_acceso() -> None:
            nonlocal intentos
            if usuario.get() == usuario_admin and clave.get() == clave_admin:
                acceso.destroy()
                self._mostrar_datos_producto()
                return

            intentos += 1
            restantes = 3 - intentos
            if restantes:
                messagebox.showerror(
                    "Acceso denegado",
                    f"El usuario o la contraseña no son correctos. "
                    f"Intentos restantes: {restantes}.",
                    parent=acceso,
                )
                clave.delete(0, tk.END)
                clave.focus_set()
            else:
                messagebox.showerror(
                    "Acceso bloqueado",
                    "Se alcanzó el máximo de 3 intentos.",
                    parent=acceso,
                )
                acceso.destroy()

        ttk.Button(acceso, text="Validar acceso", command=validar_acceso).grid(
            row=2, column=0, padx=10, pady=10
        )
        ttk.Button(acceso, text="Cancelar", command=acceso.destroy).grid(
            row=2, column=1, sticky=tk.E, padx=10, pady=10
        )
        clave.bind("<Return>", lambda _evento: validar_acceso())
        self._aplicar_tema()
        self._centrar_sobre_ventana_principal(acceso)
        usuario.focus_set()

    def _mostrar_datos_producto(self) -> None:
        formulario = tk.Toplevel(self.root)
        formulario.title("Datos del nuevo producto")
        formulario.transient(self.root)
        formulario.grab_set()
        formulario.resizable(False, False)

        campos: dict[str, ttk.Entry] = {}
        etiquetas = (
            ("codigo", "Código del nuevo producto"),
            ("nombre", "Nombre del producto"),0
            ("referencia", "Código del producto anterior"),
            ("stock", "Stock inicial (opcional)"),
        )
        for fila, (clave, etiqueta) in enumerate(etiquetas):
            ttk.Label(formulario, text=etiqueta).grid(
                row=fila, column=0, sticky=tk.W, padx=10, pady=5
            )
            entrada = ttk.Entry(
                formulario,
                show="*" if clave == "clave" else "",
                width=36,
            )
            entrada.grid(row=fila, column=1, padx=10, pady=5)
            campos[clave] = entrada

        def guardar() -> None:
            codigo = campos["codigo"].get().strip()
            nombre = campos["nombre"].get().strip()
            referencia = campos["referencia"].get().strip()
            stock_texto = campos["stock"].get().strip()
            if not codigo or not nombre or not referencia:
                messagebox.showwarning(
                    "Datos incompletos",
                    "Completa el código, el nombre y el código de referencia.",
                    parent=formulario,
                )
                return
            try:
                stock = int(stock_texto) if stock_texto else None
            except ValueError:
                messagebox.showwarning(
                    "Stock inválido",
                    "El stock inicial debe ser un número entero o quedar vacío.",
                    parent=formulario,
                )
                return
            if not messagebox.askyesno(
                "Confirmar alta",
                f"¿Agregar '{nombre}' ({codigo}) debajo de {referencia}?",
                parent=formulario,
            ):
                return

            formulario.destroy()

            def insertar() -> None:
                stock_manager = StockManager(self.menu.ruta_excel_base)
                exito, mensaje, _ = stock_manager.agregar_producto_en_posicion(
                    codigo_nuevo=codigo,
                    nombre_nuevo=nombre,
                    codigo_arriba=referencia,
                    stock_inicial=stock,
                )
                if not exito:
                    raise ValueError(mensaje)
                print(f"[OK] {mensaje}")

            self._iniciar_tarea("Alta de producto", insertar)

        ttk.Button(formulario, text="Guardar", command=guardar).grid(
            row=len(etiquetas), column=0, padx=10, pady=10
        )
        ttk.Button(
            formulario, text="Cancelar", command=formulario.destroy
        ).grid(row=len(etiquetas), column=1, sticky=tk.E, padx=10, pady=10)
        self._aplicar_tema()
        self._centrar_sobre_ventana_principal(formulario)

    def iniciar(self) -> None:
        self.root.mainloop()
