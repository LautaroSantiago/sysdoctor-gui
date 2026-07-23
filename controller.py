"""
controller.py — pega window.py (GTK) con scanner.py (ejecución). Corre el
escaneo en un hilo de fondo y usa GLib.idle_add para tocar la UI siempre
desde el hilo principal.
"""
import threading
from datetime import datetime

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

import commands_db
from commands_db import CATEGORIES, CATEGORY_LABELS
from models import Status
from scanner import Scanner, ToolInstaller, RECOMMENDED_PACKAGES


def _build_report_markdown(findings) -> str:
    lines = [
        "# Reporte de diagnóstico — sysdoctor-gui",
        "",
        f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]
    errors = [f for f in findings if f.status == Status.ERROR]
    warns = [f for f in findings if f.status == Status.WARN]
    lines.append(f"**Resumen:** {len(errors)} error(es), {len(warns)} advertencia(s) "
                 f"sobre {len(findings)} chequeos corridos.")
    lines.append("")

    if errors or warns:
        lines.append("## Errores y advertencias encontrados")
        lines.append("")
        for f in errors + warns:
            cat = CATEGORY_LABELS.get(f.category, f.category)
            lines.append(f"### [{f.status.label}] {f.title}  _(({cat}))_")
            lines.append(f.summary)
            if f.detail:
                lines.append("")
                lines.append("```")
                lines.append(f.detail[:4000])
                lines.append("```")
            if f.suggested_fix:
                lines.append(f"\n**Sugerencia:** `{f.suggested_fix}`")
            lines.append("")

    lines.append("## Todos los chequeos corridos")
    lines.append("")
    for cid, label in CATEGORIES:
        cat_findings = [f for f in findings if f.category == cid]
        if not cat_findings:
            continue
        lines.append(f"### {label}")
        for f in cat_findings:
            lines.append(f"- **[{f.status.label}]** {f.title}: {f.summary}")
        lines.append("")

    return "\n".join(lines)


class Controller:
    def __init__(self, window):
        self.window = window
        self.scanner: Scanner = None
        self.scan_thread: threading.Thread = None
        self.last_findings = []

        window.scan_btn.connect("clicked", self.on_scan_clicked)
        window.install_btn.connect("clicked", self.on_install_clicked)
        window.save_btn.connect("clicked", self.on_save_clicked)

    # ─────────────────────────────── escaneo ───────────────────────────────

    def on_scan_clicked(self, _btn):
        if self.scan_thread and self.scan_thread.is_alive():
            return
        include_deep = self.window.get_include_deep()
        self.window.clear_results()
        self.last_findings = []
        self.window.set_scanning(True)
        self.scanner = Scanner(commands_db.COMMANDS)
        self.scan_thread = threading.Thread(
            target=self._run_scan_thread, args=(include_deep,), daemon=True)
        self.scan_thread.start()

    def _run_scan_thread(self, include_deep):
        def progress_cb(p):
            GLib.idle_add(self.window.set_progress, p.done, p.total, p.current_title)

        def finding_cb(f):
            self.last_findings.append(f)
            GLib.idle_add(self.window.add_finding, f)

        error_box = {}
        try:
            self.scanner.run_scan(include_deep, progress_cb, finding_cb)
        except Exception as e:
            error_box["e"] = e
        finally:
            GLib.idle_add(self._on_scan_finished, error_box.get("e"))

    def _on_scan_finished(self, exc):
        self.window.set_scanning(False)
        if exc is not None:
            self.window.show_message("Error inesperado durante el análisis", str(exc), True)
            return
        priv_skips = [f for f in self.last_findings
                      if f.status == Status.SKIP and "privilegios" in f.summary]
        if priv_skips and self.scanner and self.scanner.channel.error:
            self.window.show_message(
                "Algunos chequeos se omitieron",
                f"{len(priv_skips)} chequeo(s) necesitaban acceso privilegiado y no se "
                f"obtuvo:\n{self.scanner.channel.error}\n\n"
                "El resto del análisis se completó igual.",
            )

    # ───────────────────────── instalar herramientas ─────────────────────────

    def on_install_clicked(self, _btn):
        dialog = Gtk.Dialog(title="Instalar herramientas recomendadas", transient_for=self.window,
                             modal=True)
        dialog.set_default_size(560, 420)
        dialog.add_button("Cerrar", Gtk.ResponseType.CLOSE)

        box = dialog.get_content_area()
        box.set_spacing(8)
        box.set_border_width(12)

        info = Gtk.Label(
            label=f"Se van a intentar instalar {len(RECOMMENDED_PACKAGES)} paquetes vía apt "
                  "(uno por uno; los que no existan en tus repositorios simplemente se "
                  "informan como no encontrados, sin frenar al resto). Se te va a pedir "
                  "la contraseña de administrador una sola vez.")
        info.set_line_wrap(True)
        info.set_xalign(0)
        box.pack_start(info, False, False, 0)

        progress = Gtk.ProgressBar()
        box.pack_start(progress, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        textview = Gtk.TextView()
        textview.set_editable(False)
        textview.set_monospace(True)
        buf = textview.get_buffer()
        scroll.add(textview)
        box.pack_start(scroll, True, True, 0)

        dialog.show_all()

        installer = ToolInstaller()

        def progress_cb(p):
            frac = (p.done / p.total) if p.total else 0.0
            GLib.idle_add(progress.set_fraction, min(1.0, frac))
            GLib.idle_add(progress.set_text, p.current_title)
            GLib.idle_add(progress.set_show_text, True)

        def log_cb(pkg, ok):
            def append():
                end = buf.get_end_iter()
                buf.insert(end, f"{'OK  ' if ok else 'X   '} {pkg}\n")
                textview.scroll_to_iter(buf.get_end_iter(), 0, False, 0, 0)
            GLib.idle_add(append)

        def run():
            installer.run(log_cb, progress_cb)
            GLib.idle_add(lambda: buf.insert(buf.get_end_iter(), "\n— Listo —\n"))

        threading.Thread(target=run, daemon=True).start()
        dialog.run()
        dialog.destroy()

    # ─────────────────────────────── reporte ───────────────────────────────

    def on_save_clicked(self, _btn):
        if not self.last_findings:
            self.window.show_message("Todavía no hay nada para guardar",
                                      "Corré un análisis primero.")
            return
        dialog = Gtk.FileChooserNative.new(
            "Guardar reporte", self.window, Gtk.FileChooserAction.SAVE,
            "Guardar", "Cancelar")
        default_name = f"sysdoctor-reporte-{datetime.now().strftime('%Y%m%d-%H%M')}.md"
        dialog.set_current_name(default_name)
        dialog.set_current_folder(GLib.get_home_dir())
        response = dialog.run()
        if response == Gtk.ResponseType.ACCEPT:
            path = dialog.get_filename()
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(_build_report_markdown(self.last_findings))
            except Exception as e:
                self.window.show_message("No se pudo guardar el reporte", str(e), True)
        dialog.destroy()
