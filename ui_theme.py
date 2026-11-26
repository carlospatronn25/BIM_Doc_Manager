"""Tema claro / negro mate de BIM DOC MANAGER (sin librerías externas).

Se colorean tanto los widgets ttk como los widgets clásicos de Tkinter,
para que la ventana principal y los formularios tengan el mismo aspecto.
"""
from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk
from pathlib import Path


THEMES = {
    "claro": {
        "background": "#f3f5f8",
        "panel": "#f3f5f8",
        "field": "#ffffff",
        "text": "#263449",
        "muted": "#526477",
        "border": "#b9c6d2",
        "header": "#102a43",
        "header_text": "#ffffff",
        "header_muted": "#d5e2ef",
        "heading": "#e5edf5",
        "button": "#e8edf2",
        "button_active": "#d6e3ee",
        "accent": "#174a75",
        "accent_active": "#103957",
        "select": "#2b628f",
        "success": "#176b45",
        "warning": "#9a6815",
        "error": "#ad3030",
        "scrollbar": "#c4ced8",
    },
    "oscuro": {
        "background": "#17191c",
        "panel": "#202328",
        "field": "#292d32",
        "text": "#e9edf1",
        "muted": "#acb6c1",
        "border": "#444a52",
        "header": "#111316",
        "header_text": "#f1f3f5",
        "header_muted": "#b8c3cd",
        "heading": "#30353b",
        "button": "#30353b",
        "button_active": "#3b424a",
        "accent": "#356a91",
        "accent_active": "#447ca6",
        "select": "#355b7b",
        "success": "#86d8a9",
        "warning": "#ecc37b",
        "error": "#ff9999",
        "scrollbar": "#464d55",
    },
}


class ThemeController:
    """Aplica colores y recuerda el último modo elegido en el equipo."""

    def __init__(self):
        self.settings_path = Path.home() / ".bim_doc_manager_theme.json"
        self.mode = "claro"
        try:
            config = json.loads(self.settings_path.read_text(encoding="utf-8"))
            if config.get("tema") in THEMES:
                self.mode = config["tema"]
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    @property
    def colors(self) -> dict:
        return THEMES[self.mode]

    def toggle(self):
        self.mode = "oscuro" if self.mode == "claro" else "claro"
        try:
            self.settings_path.write_text(
                json.dumps({"tema": self.mode}, ensure_ascii=False), encoding="utf-8"
            )
        except OSError:
            # Si el directorio del usuario no permite escritura, el interruptor
            # sigue funcionando durante esta sesión.
            pass

    def configure_ttk(self, root: tk.Tk):
        """Colores comunes para tablas, entradas, botones y desplegables."""
        c = self.colors
        style = ttk.Style(root)
        # Se mantiene clam, el tema usado originalmente por la aplicación.
        style.configure(".", background=c["panel"], foreground=c["text"])
        style.configure("TFrame", background=c["panel"])
        style.configure("TLabel", background=c["panel"], foreground=c["text"])
        style.configure("Muted.TLabel", background=c["panel"], foreground=c["muted"])
        style.configure("TLabelframe", background=c["panel"], bordercolor=c["border"])
        style.configure("TLabelframe.Label", background=c["panel"], foreground=c["text"])

        style.configure(
            "TButton", font=("Segoe UI", 9, "bold"), padding=7,
            background=c["button"], foreground=c["text"],
            bordercolor=c["border"], lightcolor=c["button"],
            darkcolor=c["button"], relief="flat",
        )
        style.map(
            "TButton",
            background=[("pressed", c["button_active"]), ("active", c["button_active"])],
            foreground=[("disabled", c["muted"]), ("!disabled", c["text"])],
        )
        style.configure(
            "Primary.TButton", background=c["accent"], foreground="#ffffff",
            bordercolor=c["accent"], lightcolor=c["accent"], darkcolor=c["accent"],
        )
        style.map(
            "Primary.TButton",
            background=[("pressed", c["accent_active"]), ("active", c["accent_active"])],
            foreground=[("disabled", c["muted"]), ("!disabled", "#ffffff")],
        )
        style.configure(
            "TEntry", fieldbackground=c["field"], foreground=c["text"],
            insertcolor=c["text"], bordercolor=c["border"],
            lightcolor=c["border"], darkcolor=c["border"],
        )
        style.map(
            "TEntry", fieldbackground=[("readonly", c["field"]), ("!disabled", c["field"])],
            foreground=[("!disabled", c["text"])],
        )
        style.configure(
            "TCombobox", fieldbackground=c["field"], background=c["button"],
            foreground=c["text"], arrowcolor=c["text"],
            bordercolor=c["border"], lightcolor=c["border"],
            darkcolor=c["border"], selectbackground=c["field"],
            selectforeground=c["text"], padding=3,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", c["field"]), ("!disabled", c["field"])],
            foreground=[("readonly", c["text"]), ("!disabled", c["text"])],
            background=[("active", c["button_active"]), ("!disabled", c["button"])],
            arrowcolor=[("!disabled", c["text"])],
            selectbackground=[("readonly", c["field"])],
            selectforeground=[("readonly", c["text"])],
        )
        style.configure(
            "Treeview", rowheight=27, font=("Segoe UI", 9),
            background=c["field"], fieldbackground=c["field"],
            foreground=c["text"], bordercolor=c["border"],
            lightcolor=c["border"], darkcolor=c["border"],
        )
        style.map(
            "Treeview", background=[("selected", c["select"])],
            foreground=[("selected", "#ffffff")],
        )
        style.configure(
            "Treeview.Heading", font=("Segoe UI", 9, "bold"),
            background=c["heading"], foreground=c["text"],
            bordercolor=c["border"], relief="flat",
        )
        style.map("Treeview.Heading", background=[("active", c["button_active"])])
        style.configure(
            "TScrollbar", background=c["scrollbar"], troughcolor=c["panel"],
            arrowcolor=c["text"], bordercolor=c["border"],
        )
        style.map("TScrollbar", background=[("active", c["button_active"])])
        # Colorea también la lista desplegada; Tk la crea en un widget aparte.
        root.option_add("*TCombobox*Listbox.background", c["field"], 80)
        root.option_add("*TCombobox*Listbox.foreground", c["text"], 80)
        root.option_add("*TCombobox*Listbox.selectBackground", c["select"], 80)
        root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff", 80)

    def recolor(self, widget):
        """Colorea recursivamente widgets Tk; ttk toma colores de sus estilos."""
        c = self.colors
        if isinstance(widget, (tk.Tk, tk.Toplevel)):
            widget.configure(bg=c["background"])
        elif isinstance(widget, (tk.Frame, tk.LabelFrame)):
            widget.configure(bg=c["panel"])
            if isinstance(widget, tk.LabelFrame):
                widget.configure(fg=c["text"])
        elif isinstance(widget, tk.Label):
            widget.configure(bg=c["panel"], fg=c["text"])
        elif isinstance(widget, tk.Entry) and not isinstance(widget, ttk.Entry):
            widget.configure(
                bg=c["field"], fg=c["text"], readonlybackground=c["field"],
                insertbackground=c["text"], selectbackground=c["select"],
                selectforeground="#ffffff", highlightbackground=c["border"],
            )
        elif isinstance(widget, tk.Button):
            widget.configure(
                bg=c["button"], fg=c["text"], activebackground=c["button_active"],
                activeforeground=c["text"], highlightbackground=c["border"],
            )
        elif isinstance(widget, ttk.Combobox):
            # Algunos temas de Tk ya han creado la lista interna antes del cambio.
            try:
                pop = widget.tk.call("ttk::combobox::PopdownWindow", str(widget))
                listbox = f"{pop}.f.l"
                widget.tk.call(
                    listbox, "configure", "-background", c["field"],
                    "-foreground", c["text"], "-selectbackground", c["select"],
                    "-selectforeground", "#ffffff",
                )
            except tk.TclError:
                pass
        for child in widget.winfo_children():
            self.recolor(child)
