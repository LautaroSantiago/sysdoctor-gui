"""
app.py — Gtk.Application. Usa un application_id propio para que GTK
maneje la instancia única de forma nativa (evita pedir la contraseña
de sudo dos veces si el usuario abre el programa por duplicado).
"""
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio

from theme import apply_theme
from window import MainWindow
from controller import Controller

APP_ID = "org.lautaro.SysdoctorGui"


class SysDoctorApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                          flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.window = None

    def do_activate(self):
        if self.window is None:
            apply_theme()
            self.window = MainWindow(self)
            self.window.controller = Controller(self.window)
        self.window.present()
