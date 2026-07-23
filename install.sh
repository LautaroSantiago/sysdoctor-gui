#!/usr/bin/env bash
# install.sh — instala sysdoctor-gui para el usuario actual (idempotente).
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$HOME/.local/share/sysdoctor-gui"
BIN_DIR="$HOME/.local/bin"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
DESKTOP_DIR="$HOME/.local/share/applications"

echo "Chequeando dependencias..."
MISSING=()
python3 -c "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk" 2>/dev/null \
  || MISSING+=("gir1.2-gtk-3.0 python3-gi python3-gi-cairo")
command -v pkexec >/dev/null 2>&1 || MISSING+=("policykit-1")

if [ "${#MISSING[@]}" -gt 0 ]; then
  echo "Faltan paquetes: ${MISSING[*]}"
  echo "Instalalos con:"
  echo "  sudo apt install ${MISSING[*]}"
  read -rp "¿Instalar ahora? [s/N] " resp
  if [[ "$resp" =~ ^[sS]$ ]]; then
    sudo apt install -y ${MISSING[*]}
  else
    echo "Seguimos igual; instalá esos paquetes antes de correr sysdoctor-gui."
  fi
fi

echo "Copiando archivos a $APP_DIR ..."
mkdir -p "$APP_DIR"
cp -f "$SRC_DIR"/*.py "$APP_DIR"/
chmod +x "$APP_DIR/main.py" "$APP_DIR/priv_helper.py"

echo "Instalando lanzador en $BIN_DIR ..."
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/sysdoctor-gui" << EOF
#!/usr/bin/env bash
exec python3 "$APP_DIR/main.py" "\$@"
EOF
chmod +x "$BIN_DIR/sysdoctor-gui"

echo "Instalando ícono ..."
mkdir -p "$ICON_DIR"
cp -f "$SRC_DIR/icon.svg" "$ICON_DIR/sysdoctor-gui.svg"
command -v gtk-update-icon-cache >/dev/null 2>&1 \
  && gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo "Instalando lanzador de menú ..."
mkdir -p "$DESKTOP_DIR"
cp -f "$SRC_DIR/sysdoctor-gui.desktop" "$DESKTOP_DIR/sysdoctor-gui.desktop"
command -v update-desktop-database >/dev/null 2>&1 \
  && update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "Nota: $BIN_DIR no está en tu PATH. Agregá esto a tu ~/.bashrc:"
     echo "  export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac

echo ""
echo "Listo. Corré 'sysdoctor-gui' desde la terminal o buscalo en el menú de MATE"
echo "(puede que tengas que cerrar sesión una vez para que aparezca en el menú)."
