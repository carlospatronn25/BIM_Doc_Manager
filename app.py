from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

import core
from ui_theme import ThemeController

# Propuestas de codificación del Manual buildingSMART Spain v1.1, pp. 11-12.
# Las numeraciones son ejemplos: el proyecto define qué zonas y niveles existen.
VOLUMEN_OPCIONES = [
    "Z01 — Zona 1", "Z02 — Zona 2", "Z03 — Zona 3",
    "E01 — Edificio 1", "E02 — Edificio 2", "E03 — Edificio 3",
    "FC1 — Fase constructiva 1", "FC2 — Fase constructiva 2",
    "CN — Construcción nueva", "CE — Construcción existente",
    "PE — Proyecto ejecución", "PC — Proyecto construcción",
    "T01 — Tramo 1", "T02 — Tramo 2", "T03 — Tramo 3",
    "XX — No aplica", "XXX — No aplica",
    "YY — Varios volúmenes", "YYY — Varios volúmenes",
    "ZZ — Todos los volúmenes", "ZZZ — Todos los volúmenes",
]

NIVEL_OPCIONES = [
    "P00 — Nivel sobre rasante 0", "P01 — Nivel sobre rasante 1",
    "P02 — Nivel sobre rasante 2", "P03 — Nivel sobre rasante 3",
    "S01 — Nivel bajo rasante 1", "S02 — Nivel bajo rasante 2",
    "S03 — Nivel bajo rasante 3", "Z01 — Zona 1", "Z02 — Zona 2",
    "T01 — Tramo 1", "T02 — Tramo 2", "T03 — Tramo 3",
    "XXX — No aplica", "YYY — Varios niveles", "ZZZ — Todos los niveles",
]


def extract_code(text: str) -> str:
    """De 'Z01 — Zona 1' toma 'Z01'; deja un código escrito a mano intacto."""
    return str(text or "").split(" — ", 1)[0].strip().upper()


class BIMDocManager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("BIM DOC MANAGER | Normalización de nombres BIM")
        self.geometry("1500x820")
        self.minsize(1100, 650)
        self.configure(bg="#f3f5f8")
        self.theme_controller = ThemeController()
        self._splash = None
        self._splash_loading_var = tk.StringVar(value="Cargando")
        self._splash_after_id = None
        self._splash_anim_step = 0

        # Se pueden combinar archivos sueltos y carpetas completas.
        self.input_sources: list[Path] = []
        self.source_summary = tk.StringVar(value="Aún no has seleccionado archivos ni carpetas.")
        self.output_dir = tk.StringVar()
        self.summary = tk.StringVar(value="Agrega archivos y/o carpetas para comenzar.")
        self.catalog = core.load_catalog()
        self.records: list[core.DocumentRecord] = []
        self._configure_style()
        self._build_ui()
        self._apply_theme()

        # Pantalla de inicio
        self.withdraw()
        self.after(120, self._show_startup_screen)

    def _configure_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

    def _apply_theme(self):
        """Aplica el tema a la ventana principal y los formularios abiertos."""
        self.theme_controller.configure_ttk(self)
        self.theme_controller.recolor(self)
        c = self.theme_controller.colors
        self.header.configure(bg=c["header"])
        self.header_title.configure(bg=c["header"], fg=c["header_text"])
        self.header_subtitle.configure(bg=c["header"], fg=c["header_muted"])
        self.theme_button.configure(
            text="☀  Modo claro" if self.theme_controller.mode == "oscuro" else "☾  Modo oscuro",
            bg=c["button"], fg=c["text"], activebackground=c["button_active"],
            activeforeground=c["text"], relief="flat", bd=0,
        )
        for status, color in (
            ("LISTO PARA GENERAR", c["success"]),
            ("GENERADO", c["success"]),
            ("PENDIENTE", c["warning"]),
            ("BLOQUEADO", c["error"]),
            ("ERROR DE COPIA", c["error"]),
        ):
            self.table.tag_configure(status, foreground=color)

    def _toggle_theme(self):
        self.theme_controller.toggle()
        self._apply_theme()

    def _show_startup_screen(self):
        splash = tk.Toplevel(self)
        splash.overrideredirect(True)
        splash.configure(bg="#141414")
        splash.attributes("-topmost", True)
        self._splash = splash

        width, height = 760, 420
        screen_w = splash.winfo_screenwidth()
        screen_h = splash.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        splash.geometry(f"{width}x{height}+{x}+{y}")

        outer = tk.Frame(splash, bg="#141414", highlightbackground="#2b2b2b", highlightthickness=1)
        outer.pack(fill="both", expand=True)

        tk.Frame(outer, bg="#1f1f1f", height=6).pack(fill="x", side="top")

        center = tk.Frame(outer, bg="#141414")
        center.pack(expand=True)

        tk.Label(
            center, text="BIM DOC MANAGER 7.0", bg="#141414", fg="#f2f2f2",
            font=("Segoe UI", 28, "bold")
        ).pack(pady=(20, 8))
        tk.Label(
            center, text="Normalización de nombres BIM", bg="#141414", fg="#bfc7d1",
            font=("Segoe UI", 12)
        ).pack()
        tk.Label(
            center, textvariable=self._splash_loading_var, bg="#141414", fg="#7ec8ff",
            font=("Segoe UI", 13, "bold")
        ).pack(pady=(30, 0))

        footer = tk.Frame(outer, bg="#141414", padx=24, pady=18)
        footer.pack(fill="x", side="bottom")
        credits = tk.Frame(footer, bg="#141414")
        credits.pack(anchor="w")
        tk.Label(
            credits, text="By 7-0 team", bg="#141414", fg="#f0f0f0",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w")
        for name in (
            "Duvan David Gonzalez Feria",
            "Carlos Mario Patron Ochoa",
            "Carlos Gabriel Zuñiga Hoyos",
        ):
            tk.Label(
                credits, text=name, bg="#141414", fg="#c8c8c8",
                font=("Segoe UI", 10)
            ).pack(anchor="w", pady=1)

        self._animate_splash_loading()
        splash.after(2200, self._close_startup_screen)

    def _animate_splash_loading(self):
        if self._splash is None or not self._splash.winfo_exists():
            return
        dots = "." * (self._splash_anim_step % 4)
        self._splash_loading_var.set(f"Cargando{dots}")
        self._splash_anim_step += 1
        self._splash_after_id = self.after(350, self._animate_splash_loading)

    def _close_startup_screen(self):
        if self._splash_after_id is not None:
            try:
                self.after_cancel(self._splash_after_id)
            except tk.TclError:
                pass
            self._splash_after_id = None

        if self._splash is not None and self._splash.winfo_exists():
            self._splash.destroy()
        self._splash = None
        self.deiconify()
        self.lift()
        self.focus_force()

    def _build_ui(self):
        header = tk.Frame(self, bg="#102a43", padx=22, pady=15)
        header.pack(fill="x")
        self.header = header
        self.theme_button = tk.Button(
            header, text="☾  Modo oscuro", command=self._toggle_theme,
            font=("Segoe UI Symbol", 10), padx=12, pady=6,
            relief="flat", bd=0, cursor="hand2", highlightthickness=0,
        )
        self.theme_button.pack(side="right", anchor="n", padx=(18, 0), pady=(5, 0))
        self.header_title = tk.Label(
            header, text="BIM DOC MANAGER", bg="#102a43", fg="white",
            font=("Segoe UI", 19, "bold"),
        )
        self.header_title.pack(anchor="w")
        self.header_subtitle = tk.Label(
            header, text="De nombres informales a nomenclatura BIM normalizada",
            bg="#102a43", fg="#d5e2ef", font=("Segoe UI", 10),
        )
        self.header_subtitle.pack(anchor="w", pady=(3, 0))

        body = tk.Frame(self, bg="#f3f5f8", padx=18, pady=14)
        body.pack(fill="both", expand=True)

        paths = tk.LabelFrame(body, text="  1. Documentos y carpeta de salida  ", bg="#f3f5f8", fg="#263449", font=("Segoe UI", 10, "bold"), padx=10, pady=9)
        paths.pack(fill="x")
        self._source_row(paths)
        self._path_row(paths, "Carpeta de salida", self.output_dir, self._pick_output)
        tk.Label(
            paths,
            text="Puedes seleccionar varios archivos, una carpeta completa o combinar ambas opciones. "
                 "Los archivos repetidos se cargarán una sola vez.",
            bg="#f3f5f8", fg="#526477", font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(4, 0))

        toolbar = tk.Frame(body, bg="#f3f5f8")
        toolbar.pack(fill="x", pady=10)
        ttk.Button(toolbar, text="Cargar documentos", style="Primary.TButton", command=self.load_documents).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Editar documento seleccionado", command=self.edit_selected).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Aplicar datos comunes", command=self.apply_common).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Importar metadatos CSV", command=self.import_metadata).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Validar nomenclatura", command=self.validate_all).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Generar copias válidas", command=self.generate).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Exportar bitácora", command=self.export_report).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Plantilla CSV", command=self.export_template).pack(side="left", padx=6)

        summary_frame = tk.Frame(body, bg="#f3f5f8")
        summary_frame.pack(fill="x", pady=(0, 8))
        tk.Label(summary_frame, textvariable=self.summary, bg="#f3f5f8", fg="#30465b", font=("Segoe UI", 10, "bold")).pack(anchor="w")

        table_box = tk.LabelFrame(body, text="  2. Tabla de documentos: doble clic en una fila para completar o modificar sus campos  ", bg="#f3f5f8", fg="#263449", font=("Segoe UI", 10, "bold"), padx=7, pady=7)
        table_box.pack(fill="both", expand=True)
        columns = (
            "archivo", "proyecto", "creador", "volumen", "nivel", "tipo", "disciplina",
            "numero", "descripcion", "estado", "revision", "propuesto", "resultado", "detalle",
        )
        self.table = ttk.Treeview(table_box, columns=columns, show="headings", selectmode="extended")
        titles = {
            "archivo": ("Nombre original", 190), "proyecto": ("Proyecto", 85), "creador": ("Creador", 80),
            "volumen": ("Vol./Sist.", 75), "nivel": ("Nivel/Loc.", 75), "tipo": ("Tipo", 65),
            "disciplina": ("Disciplina", 78), "numero": ("N.º", 55), "descripcion": ("Descripción", 155),
            "estado": ("Estado", 55), "revision": ("Revisión", 65),
            "propuesto": ("Nombre normalizado propuesto", 440), "resultado": ("Resultado", 135),
            "detalle": ("Observación", 340),
        }
        for col in columns:
            title, width = titles[col]
            self.table.heading(col, text=title)
            self.table.column(col, width=width, minwidth=55, anchor="w", stretch=False)
        self.table.tag_configure("LISTO PARA GENERAR", foreground="#176b45")
        self.table.tag_configure("GENERADO", foreground="#176b45")
        self.table.tag_configure("PENDIENTE", foreground="#9a6815")
        self.table.tag_configure("BLOQUEADO", foreground="#ad3030")
        self.table.tag_configure("ERROR DE COPIA", foreground="#ad3030")

        yscroll = ttk.Scrollbar(table_box, orient="vertical", command=self.table.yview)
        xscroll = ttk.Scrollbar(table_box, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.table.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        table_box.rowconfigure(0, weight=1)
        table_box.columnconfigure(0, weight=1)
        self.table.bind("<Double-1>", lambda _event: self.edit_selected())

        bottom = tk.Frame(body, bg="#f3f5f8")
        bottom.pack(fill="x", pady=(8, 0))
        tk.Label(
            bottom,
            text="La aplicación normaliza el nombre; no interpreta el contenido técnico del documento ni inventa metadatos. Los originales se conservan.",
            bg="#f3f5f8", fg="#657486", font=("Segoe UI", 8),
        ).pack(anchor="w")

    def _path_row(self, parent, label, variable, command):
        row = tk.Frame(parent, bg="#f3f5f8")
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, width=24, anchor="w", bg="#f3f5f8", fg="#35465a", font=("Segoe UI", 9)).pack(side="left")
        tk.Entry(row, textvariable=variable, relief="solid", bd=1, font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row, text="Examinar…", command=command).pack(side="right")

    def _source_row(self, parent):
        """Controles separados porque Tkinter no dispone de un selector nativo mixto."""
        row = tk.Frame(parent, bg="#f3f5f8")
        row.pack(fill="x", pady=3)
        tk.Label(row, text="Archivos y/o carpetas", width=24, anchor="w",
                 bg="#f3f5f8", fg="#35465a", font=("Segoe UI", 9)).pack(side="left")
        tk.Entry(row, textvariable=self.source_summary, relief="solid", bd=1,
                 font=("Segoe UI", 9), state="readonly").pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row, text="Seleccionar archivos…", command=self._pick_files).pack(side="left", padx=(0, 4))
        ttk.Button(row, text="Seleccionar carpeta…", command=self._pick_input).pack(side="left", padx=(0, 4))
        ttk.Button(row, text="Limpiar", command=self._clear_sources).pack(side="left")

    def _add_sources(self, candidates):
        """Acumula fuentes, evitando que la misma ruta se agregue dos veces."""
        existing = {str(p).casefold() for p in self.input_sources}
        for candidate in candidates:
            path = Path(candidate).expanduser().resolve()
            if not (path.is_file() or path.is_dir()):
                continue
            key = str(path).casefold()
            if key not in existing:
                self.input_sources.append(path)
                existing.add(key)

        folders = sum(p.is_dir() for p in self.input_sources)
        files = sum(p.is_file() for p in self.input_sources)
        if self.input_sources:
            preview = "; ".join(p.name for p in self.input_sources[:3])
            if len(self.input_sources) > 3:
                preview += "; ..."
            self.source_summary.set(f"{files} archivo(s), {folders} carpeta(s) | {preview}")
            if not self.output_dir.get().strip():
                first = self.input_sources[0]
                self.output_dir.set(str((first if first.is_dir() else first.parent) / "renombrados_BIM"))
        else:
            self.source_summary.set("Aún no has seleccionado archivos ni carpetas.")

    def _pick_files(self):
        paths = filedialog.askopenfilenames(
            title="Seleccionar uno o varios documentos informales",
            filetypes=[("Todos los archivos", "*.*"), ("PDF", "*.pdf"),
                       ("DWG", "*.dwg"), ("IFC", "*.ifc")],
        )
        if paths:
            self._add_sources(paths)

    def _pick_input(self):
        selected = filedialog.askdirectory(title="Seleccionar carpeta con documentos informales")
        if selected:
            self._add_sources([selected])

    def _clear_sources(self):
        if self.input_sources and not messagebox.askyesno(
            "Limpiar selección", "¿Quitar todas las fuentes de entrada seleccionadas? "
            "Los archivos originales no se modificarán.",
        ):
            return
        self.input_sources.clear()
        self.source_summary.set("Aún no has seleccionado archivos ni carpetas.")
        self.records = []
        self.refresh_table()
        self.update_summary()

    def _pick_output(self):
        selected = filedialog.askdirectory(title="Seleccionar carpeta donde se guardarán las copias")
        if selected:
            self.output_dir.set(selected)

    def load_documents(self):
        if not self.input_sources:
            messagebox.showwarning("Faltan documentos", "Selecciona archivos y/o carpetas de entrada.")
            return
        if not self.output_dir.get().strip():
            first = self.input_sources[0]
            self.output_dir.set(str((first if first.is_dir() else first.parent) / "renombrados_BIM"))
        try:
            self.records = core.scan_sources(self.input_sources, Path(self.output_dir.get()))
            self.refresh_table()
            self.update_summary()
            if not self.records:
                messagebox.showinfo("Sin documentos", "No se encontraron documentos para procesar en la selección.")
        except (OSError, ValueError) as exc:
            messagebox.showerror("No se pudieron cargar los documentos", str(exc))

    def refresh_table(self):
        for item in self.table.get_children():
            self.table.delete(item)
        for index, record in enumerate(self.records):
            values = (
                record.archivo, record.proyecto, record.creador, record.volumen, record.nivel,
                record.tipo, record.disciplina, record.numero, record.descripcion, record.estado,
                record.revision, record.nombre_propuesto, record.resultado, record.detalle,
            )
            self.table.insert("", "end", iid=str(index), values=values, tags=(record.resultado,))

    def update_summary(self):
        total = len(self.records)
        ready = sum(r.resultado == "LISTO PARA GENERAR" for r in self.records)
        generated = sum(r.resultado == "GENERADO" for r in self.records)
        pending = sum(r.resultado == "PENDIENTE" for r in self.records)
        blocked = sum(r.resultado in {"BLOQUEADO", "ERROR DE COPIA"} for r in self.records)
        self.summary.set(f"Documentos: {total}   |   Listos: {ready}   |   Generados: {generated}   |   Pendientes: {pending}   |   Bloqueados/errores: {blocked}")

    def _selected_indices(self) -> list[int]:
        return sorted(int(iid) for iid in self.table.selection())

    def edit_selected(self):
        indices = self._selected_indices()
        if not indices:
            messagebox.showinfo("Selecciona un documento", "Selecciona una fila y pulsa Editar, o haz doble clic sobre ella.")
            return
        if len(indices) > 1:
            messagebox.showinfo("Una fila a la vez", "Para editar todos los campos, selecciona un solo documento. Para varios, usa Aplicar datos comunes.")
            return
        self._edit_record(indices[0])

    def _edit_record(self, index: int):
        """Formulario completo: los desplegables no interrumpen los demás campos."""
        record = self.records[index]
        dialog = tk.Toplevel(self)
        dialog.title(f"Completar nomenclatura — {record.archivo}")
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("750x760")
        dialog.minsize(690, 690)

        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Documento original", font=("Segoe UI", 9, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 3)
        )
        ttk.Label(frame, text=record.archivo, wraplength=660).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )

        fields = [
            ("Proyecto", "proyecto"),
            ("Creador", "creador"),
            ("Volumen / Sistema", "volumen"),
            ("Nivel / Localización", "nivel"),
            ("Tipo de documento", "tipo"),
            ("Disciplina", "disciplina"),
            ("Número (001–999)", "numero"),
            ("Descripción (opcional)", "descripcion"),
            ("Estado (opcional)", "estado"),
            ("Revisión (opcional, 4 dígitos)", "revision"),
        ]
        values = {label: tk.StringVar(value=str(getattr(record, attr) or "")) for label, attr in fields}
        type_values = [f"{code} — {desc}" for code, desc in sorted(self.catalog["tipos_documento"].items())]
        discipline_values = [f"{code} — {desc}" for code, desc in sorted(self.catalog["disciplinas"].items())]
        state_values = [""] + self.catalog["estados"]
        widgets = {}

        for row, (label, attribute) in enumerate(fields, start=2):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=5)

            if attribute == "volumen":
                options = VOLUMEN_OPCIONES
                state = "normal"  # admite códigos adicionales del propio proyecto
            elif attribute == "nivel":
                options = NIVEL_OPCIONES
                state = "normal"
            elif attribute == "tipo":
                options = type_values
                state = "readonly"
            elif attribute == "disciplina":
                options = discipline_values
                state = "readonly"
            elif attribute == "estado":
                options = state_values
                state = "readonly"
            else:
                options = None
                state = None

            if options is not None:
                widget = ttk.Combobox(
                    frame, textvariable=values[label], values=options, state=state, width=54
                )
                original = str(getattr(record, attribute) or "").strip().upper()
                if original and attribute in ("volumen", "nivel", "tipo", "disciplina"):
                    matching = next((opt for opt in options if extract_code(opt) == original), None)
                    widget.set(matching if matching else original)
            else:
                widget = ttk.Entry(frame, textvariable=values[label], width=57)

            widget.grid(row=row, column=1, sticky="ew", pady=5)
            widgets[attribute] = widget

        frame.columnconfigure(1, weight=1)
        hint = (
            "Obligatorios: Proyecto (2–12), Creador (3–6), Volumen (2–3), Nivel (3), "
            "Tipo, Disciplina y Número (001–999). Descripción, Estado y Revisión son opcionales."
        )
        ttk.Label(frame, text=hint, wraplength=675, style="Muted.TLabel").grid(
            row=12, column=0, columnspan=2, sticky="w", pady=(12, 6)
        )
        ttk.Label(
            frame,
            text="Las listas de Volumen y Nivel contienen ejemplos del manual. "
                 "También se admiten códigos de proyecto que cumplan las longitudes indicadas.",
            wraplength=675, style="Muted.TLabel",
        ).grid(row=13, column=0, columnspan=2, sticky="w", pady=4)

        def save():
            proposed = {
                attr: extract_code(values[label].get()) if attr in ("volumen", "nivel", "tipo", "disciplina")
                else values[label].get().strip()
                for label, attr in fields
            }
            errores = core.validar_campos_nomenclatura(proposed, self.catalog)
            if errores:
                messagebox.showerror(
                    "Error de nomenclatura",
                    "Corrige las siguientes reglas:\n\n" + "\n\n".join("• " + e for e in errores),
                    parent=dialog,
                )
                return
            for attr, valor in proposed.items():
                setattr(record, attr, valor)
            record.resultado = "SIN VALIDAR"
            record.nombre_propuesto = ""
            record.detalle = "Campos guardados; pulsa Validar nomenclatura."
            self.refresh_table()
            self.update_summary()
            dialog.destroy()

        buttons = ttk.Frame(frame)
        buttons.grid(row=14, column=0, columnspan=2, sticky="e", pady=(15, 0))
        ttk.Button(buttons, text="Cancelar", command=dialog.destroy).pack(side="right", padx=5)
        ttk.Button(buttons, text="Guardar campos", style="Primary.TButton", command=save).pack(side="right", padx=5)
        self.theme_controller.recolor(dialog)

    def apply_common(self):
        """Aplica campos a varios documentos usando los mismos menús desplegables."""
        indices = self._selected_indices()
        if not indices:
            messagebox.showinfo("Selecciona documentos", "Selecciona una o varias filas. Los campos vacíos no se modificarán.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Aplicar datos comunes a documentos seleccionados")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=f"Se aplicará a {len(indices)} documento(s). Deja en blanco lo que no quieras cambiar.",
                  wraplength=460).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        common_fields = [
            ("Proyecto", "proyecto"), ("Creador", "creador"),
            ("Volumen / Sistema", "volumen"), ("Nivel / Localización", "nivel"),
        ]
        variables = {}
        for row, (label, attribute) in enumerate(common_fields, start=1):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=5)
            variables[attribute] = tk.StringVar()
            if attribute in ("volumen", "nivel"):
                options = VOLUMEN_OPCIONES if attribute == "volumen" else NIVEL_OPCIONES
                widget = ttk.Combobox(frame, textvariable=variables[attribute],
                                      values=[""] + options, state="normal", width=48)
            else:
                widget = ttk.Entry(frame, textvariable=variables[attribute], width=50)
            widget.grid(row=row, column=1, sticky="ew", pady=5)

        def apply():
            updates = {
                field: extract_code(var.get()) if field in ("volumen", "nivel") else var.get().strip()
                for field, var in variables.items() if var.get().strip()
            }
            if not updates:
                messagebox.showinfo("Sin cambios", "No ingresaste ningún valor.", parent=dialog)
                return
            errores = core.validar_campos_nomenclatura(updates, self.catalog, parcial=True)
            if errores:
                messagebox.showerror("Error de nomenclatura", "\n\n".join(errores), parent=dialog)
                return
            for i in indices:
                for field, value in updates.items():
                    setattr(self.records[i], field, value)
                self.records[i].resultado = "SIN VALIDAR"
                self.records[i].nombre_propuesto = ""
                self.records[i].detalle = "Datos comunes modificados; vuelve a validar."
            self.refresh_table()
            self.update_summary()
            dialog.destroy()

        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Cancelar", command=dialog.destroy).pack(side="right", padx=5)
        ttk.Button(buttons, text="Aplicar", command=apply).pack(side="right", padx=5)
        self.theme_controller.recolor(dialog)

    def validate_all(self):
        if not self.records:
            messagebox.showinfo("Sin documentos", "Primero carga archivos y/o carpetas.")
            return
        if not self.output_dir.get().strip():
            messagebox.showwarning("Falta carpeta de salida", "Selecciona una carpeta de salida.")
            return
        output = Path(self.output_dir.get().strip())
        try:
            core.validate_records(self.records, self.catalog, output)
            self.refresh_table()
            self.update_summary()
        except Exception as exc:
            messagebox.showerror("Error de validación", str(exc))

    def generate(self):
        ready = [r for r in self.records if r.resultado == "LISTO PARA GENERAR"]
        if not ready:
            messagebox.showinfo("No hay documentos listos", "Valida los datos y corrige los registros pendientes o bloqueados antes de generar.")
            return
        output_text = self.output_dir.get().strip()
        if not output_text:
            messagebox.showwarning("Falta carpeta de salida", "Selecciona una carpeta de salida.")
            return
        output = Path(output_text)
        ok = messagebox.askyesno(
            "Confirmar generación",
            f"Se crearán {len(ready)} copia(s) con la nomenclatura propuesta en:\n{output}\n\nLos originales no se modificarán. ¿Continuar?",
        )
        if not ok:
            return
        try:
            count, errors = core.copy_ready(self.records, output)
            self.refresh_table()
            self.update_summary()
            message = f"Copias generadas: {count}\nCarpeta: {output}"
            if errors:
                message += "\n\nObservaciones:\n" + "\n".join(errors)
            messagebox.showinfo("Proceso terminado", message)
        except OSError as exc:
            messagebox.showerror("No se pudieron generar las copias", str(exc))

    def export_report(self):
        if not self.records:
            messagebox.showinfo("Sin datos", "Primero carga los documentos.")
            return
        path = filedialog.asksaveasfilename(
            title="Guardar bitácora", defaultextension=".csv", initialfile="bitacora_BIM.csv",
            filetypes=[("Archivo CSV", "*.csv")],
        )
        if not path:
            return
        try:
            core.export_csv(self.records, Path(path))
            messagebox.showinfo("Bitácora exportada", f"Se guardó la bitácora en:\n{path}")
        except OSError as exc:
            messagebox.showerror("Error al exportar", str(exc))

    def export_template(self):
        if not self.records:
            messagebox.showinfo("Sin documentos", "Carga primero archivos y/o carpetas.")
            return
        path = filedialog.asksaveasfilename(
            title="Guardar plantilla de metadatos", defaultextension=".csv", initialfile="plantilla_metadatos_BIM.csv",
            filetypes=[("Archivo CSV", "*.csv")],
        )
        if not path:
            return
        try:
            core.export_template(self.records, Path(path))
            messagebox.showinfo("Plantilla exportada", f"Abre el CSV en Excel, completa los campos y luego usa 'Importar metadatos CSV'.\n\n{path}")
        except OSError as exc:
            messagebox.showerror("Error al crear plantilla", str(exc))

    def import_metadata(self):
        if not self.records:
            messagebox.showinfo("Sin documentos", "Carga primero la carpeta de documentos.")
            return
        path = filedialog.askopenfilename(title="Seleccionar CSV de metadatos", filetypes=[("Archivo CSV", "*.csv")])
        if not path:
            return
        try:
            count, messages = core.import_csv(self.records, Path(path))
            self.refresh_table()
            self.update_summary()
            message = f"Registros importados: {count}"
            if messages:
                message += "\n\nObservaciones:\n" + "\n".join(messages[:15])
            messagebox.showinfo("Importación terminada", message)
        except (OSError, ValueError) as exc:
            messagebox.showerror("No se pudo importar", str(exc))


if __name__ == "__main__":
    app = BIMDocManager()
    app.mainloop()
