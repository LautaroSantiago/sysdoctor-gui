"""
window.py — toda la interfaz GTK3. No ejecuta comandos ni conoce pkexec:
sólo expone una API simple que controller.py usa para pintar resultados.
"""
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk, Pango

from commands_db import CATEGORIES, CATEGORY_LABELS
from models import Status
from theme import STATUS_CSS_CLASS, STATUS_DOT_CLASS

STATUS_ORDER_FOR_BADGE = [Status.ERROR, Status.WARN, Status.INFO, Status.OK, Status.SKIP]


def _copy_to_clipboard(text: str):
    clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    clip.set_text(text, -1)
    clip.store()


class FindingRow(Gtk.ListBoxRow):
    def __init__(self, finding, show_category=False):
        super().__init__()
        self.finding = finding
        self.set_selectable(False)

        expander = Gtk.Expander()
        expander.set_resize_toplevel(False)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.set_margin_top(4)
        header.set_margin_bottom(4)

        dot = Gtk.Label(label="●")
        dot.get_style_context().add_class(STATUS_DOT_CLASS[finding.status.value])
        header.pack_start(dot, False, False, 0)

        badge = Gtk.Label(label=finding.status.label)
        badge.get_style_context().add_class("sd-badge")
        badge.get_style_context().add_class(STATUS_CSS_CLASS[finding.status.value])
        header.pack_start(badge, False, False, 0)

        if show_category:
            cat = Gtk.Label(label=CATEGORY_LABELS.get(finding.category, finding.category))
            cat.get_style_context().add_class("sd-muted")
            header.pack_start(cat, False, False, 0)

        title = Gtk.Label(label=finding.title)
        title.set_xalign(0)
        title.set_ellipsize(Pango.EllipsizeMode.END)
        title.set_markup(f"<b>{GLib.markup_escape_text(finding.title)}</b>")
        header.pack_start(title, False, False, 0)

        summary = Gtk.Label(label=finding.summary)
        summary.set_xalign(0)
        summary.set_ellipsize(Pango.EllipsizeMode.END)
        summary.get_style_context().add_class("sd-muted")
        header.pack_start(summary, True, True, 0)

        expander.set_label_widget(header)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        body.set_margin_start(28)
        body.set_margin_end(10)
        body.set_margin_top(4)
        body.set_margin_bottom(10)

        if finding.detail:
            detail_label = Gtk.Label(label=finding.detail)
            detail_label.set_xalign(0)
            detail_label.set_selectable(True)
            detail_label.set_line_wrap(True)
            detail_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            detail_label.get_style_context().add_class("sd-raw")
            frame = Gtk.ScrolledWindow()
            frame.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            frame.set_max_content_height(260)
            frame.set_propagate_natural_height(True)
            frame.add(detail_label)
            body.pack_start(frame, False, False, 0)

        if finding.suggested_fix:
            fix_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            fix_label = Gtk.Label(label="Sugerencia:")
            fix_label.get_style_context().add_class("sd-muted")
            fix_box.pack_start(fix_label, False, False, 0)
            entry = Gtk.Entry()
            entry.set_text(finding.suggested_fix)
            entry.set_editable(False)
            entry.get_style_context().add_class("sd-mono")
            fix_box.pack_start(entry, True, True, 0)
            copy_btn = Gtk.Button(label="Copiar")
            copy_btn.get_style_context().add_class("sd-btn-flat")
            copy_btn.connect("clicked", lambda b: _copy_to_clipboard(finding.suggested_fix))
            fix_box.pack_start(copy_btn, False, False, 0)
            body.pack_start(fix_box, False, False, 0)

        if finding.raw_output and finding.raw_output.strip() != (finding.detail or "").strip() \
                and len(finding.raw_output) > 40:
            raw_expander = Gtk.Expander(label="Ver salida completa del comando")
            raw_label = Gtk.Label(label=finding.raw_output)
            raw_label.set_xalign(0)
            raw_label.set_selectable(True)
            raw_label.set_line_wrap(True)
            raw_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            raw_label.get_style_context().add_class("sd-raw")
            raw_scroll = Gtk.ScrolledWindow()
            raw_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            raw_scroll.set_max_content_height(260)
            raw_scroll.set_propagate_natural_height(True)
            raw_scroll.add(raw_label)
            raw_expander.add(raw_scroll)
            body.pack_start(raw_expander, False, False, 0)

        cmd_label = Gtk.Label(label="$ " + " ".join(finding.spec.cmd))
        cmd_label.set_xalign(0)
        cmd_label.set_selectable(True)
        cmd_label.get_style_context().add_class("sd-muted")
        cmd_label.get_style_context().add_class("sd-mono")
        body.pack_start(cmd_label, False, False, 0)

        expander.add(body)
        # abrir automáticamente los hallazgos que son problema, para no obligar a clickear todo
        expander.set_expanded(finding.status in (Status.ERROR, Status.WARN))

        self.add(expander)
        self.show_all()


class CategoryPage(Gtk.ScrolledWindow):
    """Una página del Stack: un ListBox con las filas de una categoría (o del resumen)."""

    def __init__(self, show_category=False):
        super().__init__()
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.show_category = show_category
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.listbox.set_header_func(self._header_func)

        self.empty_label = Gtk.Label(label="Todavía no corriste un análisis.")
        self.empty_label.get_style_context().add_class("sd-muted")
        self.empty_label.set_margin_top(24)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.set_margin_start(4)
        outer.set_margin_end(4)
        outer.pack_start(self.empty_label, False, False, 0)
        outer.pack_start(self.listbox, False, False, 0)
        self.add(outer)
        self.outer = outer

    @staticmethod
    def _header_func(row, before):
        if before is not None:
            row.set_header(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

    def clear(self):
        for child in list(self.listbox.get_children()):
            self.listbox.remove(child)
        self.empty_label.show()

    def add_finding(self, finding):
        self.empty_label.hide()
        row = FindingRow(finding, show_category=self.show_category)
        self.listbox.add(row)

    def count(self):
        return len(self.listbox.get_children())


class SidebarRow(Gtk.ListBoxRow):
    def __init__(self, key, label):
        super().__init__()
        self.key = key
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        self.label = Gtk.Label(label=label)
        self.label.set_xalign(0)
        box.pack_start(self.label, True, True, 0)

        self.badge_error = Gtk.Label(label="")
        self.badge_error.get_style_context().add_class("sd-badge")
        self.badge_error.get_style_context().add_class("sd-badge-error")
        box.pack_start(self.badge_error, False, False, 0)

        self.badge_warn = Gtk.Label(label="")
        self.badge_warn.get_style_context().add_class("sd-badge")
        self.badge_warn.get_style_context().add_class("sd-badge-warn")
        box.pack_start(self.badge_warn, False, False, 0)

        self.add(box)
        self.show_all()
        self.set_counts(0, 0)

    def set_counts(self, n_error, n_warn):
        if n_error:
            self.badge_error.set_text(str(n_error))
            self.badge_error.show()
        else:
            self.badge_error.hide()
        if n_warn:
            self.badge_warn.set_text(str(n_warn))
            self.badge_warn.show()
        else:
            self.badge_warn.hide()


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="sysdoctor-gui")
        self.set_default_size(1000, 680)

        self.controller = None  # lo asigna app.py después de construir la ventana

        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title("sysdoctor-gui")
        header.set_subtitle("Diagnóstico del sistema — Linux Mint MATE")
        self.set_titlebar(header)

        self.deep_check = Gtk.CheckButton(label="Chequeos profundos (más lento)")
        self.deep_check.set_tooltip_text(
            "Incluye rkhunter, lynis, clamav, aide y similares. Puede tardar varios minutos.")
        header.pack_start(self.deep_check)

        self.install_btn = Gtk.Button(label="Instalar herramientas")
        self.install_btn.get_style_context().add_class("sd-btn-flat")
        self.install_btn.set_tooltip_text(
            "Instala (opcionalmente) las herramientas de diagnóstico recomendadas vía apt.")
        header.pack_start(self.install_btn)

        self.save_btn = Gtk.Button(label="Guardar reporte")
        self.save_btn.set_sensitive(False)
        header.pack_end(self.save_btn)

        self.scan_btn = Gtk.Button(label="Analizar sistema")
        self.scan_btn.get_style_context().add_class("sd-btn-primary")
        header.pack_end(self.scan_btn)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(root)

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(230)
        root.pack_start(paned, True, True, 0)

        sidebar_scroll = Gtk.ScrolledWindow()
        sidebar_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sidebar_scroll.get_style_context().add_class("sd-sidebar")
        self.sidebar = Gtk.ListBox()
        self.sidebar.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.sidebar.connect("row-selected", self._on_sidebar_selected)
        sidebar_scroll.add(self.sidebar)
        paned.pack1(sidebar_scroll, resize=False, shrink=False)

        self.stack = Gtk.Stack()
        paned.pack2(self.stack, resize=True, shrink=False)

        self.pages = {}
        self.sidebar_rows = {}

        resumen_row = SidebarRow("__resumen__", "Resumen")
        self.sidebar.add(resumen_row)
        self.sidebar_rows["__resumen__"] = resumen_row
        resumen_page = CategoryPage(show_category=True)
        self.stack.add_named(resumen_page, "__resumen__")
        self.pages["__resumen__"] = resumen_page

        for cid, label in CATEGORIES:
            row = SidebarRow(cid, label)
            self.sidebar.add(row)
            self.sidebar_rows[cid] = row
            page = CategoryPage(show_category=False)
            self.stack.add_named(page, cid)
            self.pages[cid] = page

        self.sidebar.select_row(resumen_row)

        # barra de progreso (oculta hasta que arranca un escaneo)
        self.progress_revealer = Gtk.Revealer()
        progress_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        progress_box.set_margin_start(10)
        progress_box.set_margin_end(10)
        progress_box.set_margin_top(6)
        progress_box.set_margin_bottom(6)
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_show_text(False)
        self.progress_label = Gtk.Label(label="")
        self.progress_label.get_style_context().add_class("sd-muted")
        self.progress_label.set_ellipsize(Pango.EllipsizeMode.END)
        progress_box.pack_start(self.progress_bar, True, True, 0)
        progress_box.pack_start(self.progress_label, False, False, 0)
        self.progress_revealer.add(progress_box)
        root.pack_start(self.progress_revealer, False, False, 0)

        self._counts = {}  # category_id -> {status: n}
        self.show_all()
        self.progress_revealer.set_reveal_child(False)

    # ────────────────────────── API usada por controller ──────────────────────────

    def _on_sidebar_selected(self, listbox, row):
        if row is not None:
            self.stack.set_visible_child_name(row.key)

    def get_include_deep(self) -> bool:
        return self.deep_check.get_active()

    def set_scanning(self, scanning: bool):
        self.scan_btn.set_sensitive(not scanning)
        self.install_btn.set_sensitive(not scanning)
        self.scan_btn.set_label("Analizando…" if scanning else "Analizar sistema")
        self.progress_revealer.set_reveal_child(scanning)
        if not scanning:
            self.save_btn.set_sensitive(True)

    def set_progress(self, done: int, total: int, label: str):
        frac = (done / total) if total else 0.0
        self.progress_bar.set_fraction(min(1.0, frac))
        self.progress_label.set_text(f"{done}/{total} — {label}" if total else label)

    def clear_results(self):
        for page in self.pages.values():
            page.clear()
        self._counts = {cid: {"error": 0, "warn": 0} for cid, _ in CATEGORIES}
        self._counts["__resumen__"] = {"error": 0, "warn": 0}
        for row in self.sidebar_rows.values():
            row.set_counts(0, 0)

    def add_finding(self, finding):
        page = self.pages.get(finding.category)
        if page:
            page.add_finding(finding)
            if finding.status == Status.ERROR:
                self._counts.setdefault(finding.category, {"error": 0, "warn": 0})["error"] += 1
            elif finding.status == Status.WARN:
                self._counts.setdefault(finding.category, {"error": 0, "warn": 0})["warn"] += 1
            c = self._counts.get(finding.category, {"error": 0, "warn": 0})
            if finding.category in self.sidebar_rows:
                self.sidebar_rows[finding.category].set_counts(c["error"], c["warn"])

        if finding.status in (Status.ERROR, Status.WARN):
            self.pages["__resumen__"].add_finding(finding)
            if finding.status == Status.ERROR:
                self._counts["__resumen__"]["error"] += 1
            else:
                self._counts["__resumen__"]["warn"] += 1
            c = self._counts["__resumen__"]
            self.sidebar_rows["__resumen__"].set_counts(c["error"], c["warn"])

    def show_message(self, text: str, secondary: str = "", is_error: bool = False):
        dialog = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.ERROR if is_error else Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK, text=text,
        )
        if secondary:
            dialog.format_secondary_text(secondary)
        dialog.run()
        dialog.destroy()

    def append_install_log(self, pkg: str, ok: bool):
        # se muestra dentro de un diálogo de progreso propio, ver controller.py
        pass
