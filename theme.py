"""
theme.py — paleta y hoja de estilos GTK3.

Misma paleta verde oscuro usada en Arkhas / redshift-gui / nfs-gui / rofi / dunst:
base #11261E, acento #3ea86b. El resto de la paleta se deriva de esos dos colores.
"""
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

PALETTE = {
    "bg_base":       "#11261E",
    "bg_panel":      "#16302A",
    "bg_elevated":   "#1C3B30",
    "bg_hover":      "#204436",
    "accent":        "#3ea86b",
    "accent_bright": "#55C684",
    "accent_dim":    "#2C7A4E",
    "text_primary":  "#EAF6EF",
    "text_secondary": "#8FAE9D",
    "text_disabled": "#5C7568",
    "border":        "#24463A",
    "warn":          "#E0A83E",
    "error":         "#E0524F",
    "info":          "#4FB3BF",
    "ok":            "#3ea86b",
    "skip":          "#5C7568",
}

CSS = """
@define-color bg_base {bg_base};
@define-color bg_panel {bg_panel};
@define-color bg_elevated {bg_elevated};
@define-color bg_hover {bg_hover};
@define-color accent {accent};
@define-color accent_bright {accent_bright};
@define-color accent_dim {accent_dim};
@define-color text_primary {text_primary};
@define-color text_secondary {text_secondary};
@define-color text_disabled {text_disabled};
@define-color border_c {border};
@define-color warn_c {warn};
@define-color error_c {error};
@define-color info_c {info};
@define-color ok_c {ok};
@define-color skip_c {skip};

window {{
    background-color: @bg_base;
    color: @text_primary;
}}

headerbar {{
    background: @bg_panel;
    color: @text_primary;
    border-bottom: 1px solid @border_c;
    box-shadow: none;
    text-shadow: none;
}}
headerbar .title {{
    color: @text_primary;
    font-weight: 600;
}}
headerbar .subtitle {{
    color: @text_secondary;
}}

label {{ color: @text_primary; }}
.sd-muted {{ color: @text_secondary; font-size: 92%; }}
.sd-mono {{ font-family: monospace; }}

button {{
    background: @bg_elevated;
    color: @text_primary;
    border: 1px solid @border_c;
    border-radius: 6px;
    padding: 5px 12px;
    transition: background 120ms ease;
}}
button:hover {{ background: @bg_hover; }}
button:disabled {{ color: @text_disabled; }}
button.sd-btn-primary {{
    background: @accent;
    color: @bg_base;
    border: 1px solid @accent_dim;
    font-weight: 600;
}}
button.sd-btn-primary:hover {{ background: @accent_bright; }}
button.sd-btn-primary:disabled {{ background: @accent_dim; color: @text_disabled; }}
button.sd-btn-flat {{
    background: transparent;
    border: none;
}}
button.sd-btn-flat:hover {{ background: @bg_hover; }}

checkbutton {{ color: @text_primary; }}
checkbutton check {{
    background: @bg_elevated;
    border: 1px solid @border_c;
    border-radius: 3px;
}}
checkbutton check:checked {{
    background: @accent;
    border-color: @accent_dim;
}}

entry {{
    background: @bg_elevated;
    color: @text_primary;
    border: 1px solid @border_c;
    border-radius: 6px;
    padding: 4px 8px;
}}
entry:focus {{ border-color: @accent; }}

scrolledwindow, viewport {{ background: @bg_base; }}

list, listbox {{
    background: @bg_base;
    color: @text_primary;
}}
row {{
    background: @bg_panel;
    border-bottom: 1px solid @border_c;
    padding: 2px;
}}
row:hover {{ background: @bg_hover; }}
row:selected {{ background: @bg_elevated; }}

.sd-sidebar {{
    background: @bg_panel;
    border-right: 1px solid @border_c;
}}
.sd-sidebar row {{
    background: transparent;
    border-bottom: none;
    padding: 6px 10px;
}}
.sd-sidebar row:selected {{
    background: @accent_dim;
}}

.sd-card {{
    background: @bg_panel;
    border: 1px solid @border_c;
    border-radius: 8px;
}}

.sd-badge {{
    border-radius: 999px;
    padding: 1px 9px;
    font-size: 85%;
    font-weight: 600;
}}
.sd-badge-error {{ background: alpha(@error_c, 0.18); color: @error_c; }}
.sd-badge-warn  {{ background: alpha(@warn_c, 0.18); color: @warn_c; }}
.sd-badge-info  {{ background: alpha(@info_c, 0.18); color: @info_c; }}
.sd-badge-ok    {{ background: alpha(@ok_c, 0.18); color: @ok_c; }}
.sd-badge-skip  {{ background: alpha(@skip_c, 0.18); color: @skip_c; }}

.sd-dot-error {{ color: @error_c; }}
.sd-dot-warn  {{ color: @warn_c; }}
.sd-dot-info  {{ color: @info_c; }}
.sd-dot-ok    {{ color: @ok_c; }}
.sd-dot-skip  {{ color: @skip_c; }}

.sd-title {{ font-size: 115%; font-weight: 700; color: @text_primary; }}
.sd-section-title {{
    font-size: 105%;
    font-weight: 700;
    color: @accent_bright;
    padding: 4px 2px;
}}

.sd-raw {{
    background: @bg_base;
    color: @text_secondary;
    font-family: monospace;
    font-size: 92%;
    padding: 8px;
    border-radius: 6px;
    border: 1px solid @border_c;
}}

progressbar trough {{
    background: @bg_elevated;
    border-radius: 6px;
    min-height: 8px;
}}
progressbar progress {{
    background: @accent;
    border-radius: 6px;
    min-height: 8px;
}}

separator {{ background: @border_c; }}

tooltip {{
    background: @bg_elevated;
    color: @text_primary;
    border: 1px solid @border_c;
}}

scrollbar slider {{
    background: @bg_elevated;
    border-radius: 6px;
}}
scrollbar slider:hover {{ background: @bg_hover; }}
""".format(**PALETTE)


def apply_theme() -> None:
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS.encode("utf-8"))
    screen = Gdk.Screen.get_default()
    Gtk.StyleContext.add_provider_for_screen(
        screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )


STATUS_CSS_CLASS = {
    "error": "sd-badge-error",
    "warn": "sd-badge-warn",
    "info": "sd-badge-info",
    "ok": "sd-badge-ok",
    "skip": "sd-badge-skip",
}

STATUS_DOT_CLASS = {
    "error": "sd-dot-error",
    "warn": "sd-dot-warn",
    "info": "sd-dot-info",
    "ok": "sd-dot-ok",
    "skip": "sd-dot-skip",
}
