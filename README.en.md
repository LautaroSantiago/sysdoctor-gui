# sysdoctor-gui

<p align="center">

[![Español](https://img.shields.io/badge/README-Espa%C3%B1ol-2ea44f?style=for-the-badge)](README.md)
[![English](https://img.shields.io/badge/README-English-0969da?style=for-the-badge)](README.en.md)

</p>

Graphical system diagnostic tool for **Linux Mint MATE**.
Corre ~230 chequeos de sólo lectura (hardware, kernel, servicios, disco,
red, seguridad, escritorio, paquetes, rendimiento, energía, tareas
programadas, virtualización) y devuelve un resumen priorizado de errores
y advertencias, con la línea de comando exacta usada y una sugerencia de
solución cuando aplica.

![Python](https://img.shields.io/badge/Python-3.9%2B-3ea86b?style=flat-square)
![GTK](https://img.shields.io/badge/GTK-3-3ea86b?style=flat-square)
![Platform](https://img.shields.io/badge/platform-Linux%20Mint%20MATE-3ea86b?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-3ea86b?style=flat-square)

---

## Table of Contents

- [Motivación](#motivación)
- [Características](#características)
- [Principio de diseño: sólo lectura](#principio-de-diseño-sólo-lectura)
- [Privilegios (pkexec)](#privilegios-pkexec)
- [Instalación](#instalación)
- [Uso](#uso)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Extender el catálogo de chequeos](#extender-el-catálogo-de-chequeos)
- [Dependencias](#dependencias)
- [Licencia](#licencia)
- [Autor](#autor)

## Motivation

Este proyecto nace de una guía personal de diagnóstico de Linux Mint MATE
(~280 comandos organizados en 10 partes, de hardware a tareas programadas)
pensada para correr a mano en la terminal. `sysdoctor-gui` la convierte en
una herramienta gráfica: corre los chequeos relevantes, interpreta cada
salida y separa lo que es sólo información de lo que es un problema real.

## Features

- **~230 chequeos** organizados en 19 categorías navegables.
- **Resumen priorizado**: una pestaña dedicada que junta sólo errores y
  advertencias de todo el sistema, sin tener que revisar categoría por
  categoría.
- **Interpretación real de la salida**, no sólo texto crudo: estado SMART,
  servicios systemd caídos (con follow-up automático a sus logs), uso de
  disco/inodos por umbral, OOM killer, vulnerabilidades de CPU sin
  mitigar, rootkits, integridad de paquetes, salud de batería, arrays
  RAID degradados, y más de 50 heurísticas específicas.
- **Detección automática de contexto**: disco principal, interfaz de red,
  batería, NVMe — nada de rutas hardcodeadas tipo `/dev/sda` o `eth0`.
- **Chequeos profundos opcionales** (rkhunter, lynis, clamav, aide,
  debsums) detrás de un checkbox, para que el escaneo normal tarde
  menos de un minuto.
- **Instalación de herramientas recomendadas** como acción explícita y
  separada, paquete por paquete (un nombre inválido no frena al resto).
- **Reporte exportable** a Markdown.
- Paleta de colores y arquitectura propias, consistentes con mis otros
  proyectos de escritorio para Mint MATE.

## Design Principle: Read-Only

El escaneo automático **nunca** instala paquetes, cambia configuración,
crea snapshots ni corre benchmarks/estrés por su cuenta. Quedan afuera a
propósito: recuperación de disco (testdisk/ddrescue), `apt --fix-broken
install`, `ufw enable`, `update-grub`, fio/sysbench/stress-ng, herramientas
interactivas (htop, glances), y cualquier comando que necesite un objetivo
que no se pueda determinar sin adivinar (ej. un servidor remoto puntual).

Cuando un chequeo encuentra un problema con una solución conocida, el
reporte incluye el comando sugerido listo para copiar — la decisión de
correrlo queda siempre del lado del usuario.

## Privileges (pkexec)

Los chequeos que necesitan root piden acceso **una sola vez** por escaneo,
vía el prompt gráfico nativo de polkit (`pkexec`), no `sudo` por terminal.
A partir de ahí, todos los comandos privilegiados se ejecutan a través de
un único proceso auxiliar (`priv_helper.py`) lanzado una vez — nunca se
piden credenciales por cada comando individual. Si el prompt se cancela,
esos chequeos puntuales quedan marcados como omitidos y el resto del
análisis se completa igual.

## Installation

```bash
git clone https://github.com/LautaroSantiago/sysdoctor-gui.git
cd sysdoctor-gui
./install.sh
```

The installer is idempotent: it copies the application to `~/.local/share/sysdoctor-gui`, installs a launcher in `~/.local/bin/sysdoctor-gui`, adds the hicolor icon, and creates a MATE menu entry. It checks for required dependencies and offers to install any that are missing.

## Usage

From the MATE menu or from a terminal:

```bash
sysdoctor-gui
```

Without installing, directly from the repository:

```bash
python3 main.py
```

1. Tildá **"Chequeos profundos"** si querés incluir rkhunter/lynis/clamav/aide.
2. Apretá **"Analizar sistema"**. Si algún chequeo necesita privilegios te
   va a pedir la contraseña una sola vez.
3. Revisá la pestaña **Resumen** para ver sólo lo que necesita atención, o
   navegá por categoría en la barra lateral.
4. **"Guardar reporte"** exporta todo a un `.md`.

## 🌳 Estructura del proyecto

```text
sysdoctor-gui/
├── analyzer.py        # Interpreta la salida de los comandos
├── app.py             # Gtk.Application
├── commands_db.py     # Catálogo de ~230 chequeos
├── controller.py      # Conecta la interfaz con el motor de análisis
├── install.sh         # Instalador para el usuario actual
├── main.py            # Punto de entrada
├── models.py          # Modelos de datos (CommandSpec, Finding, Status)
├── priv_helper.py     # Proceso privilegiado ejecutado mediante pkexec
├── scanner.py         # Orquesta el escaneo y detecta el contexto
├── theme.py           # Colores y estilos GTK3
├── window.py          # Interfaz gráfica
├── LICENSE
└── README.md
```

### Arquitectura

```text
          GUI (GTK3)
               │
               ▼
        controller.py
               │
               ▼
          scanner.py
        ┌──────┴──────┐
        ▼             ▼
 commands_db.py   priv_helper.py
        │
        ▼
    analyzer.py
        │
        ▼
      Findings
        │
        ▼
      window.py
```

## Extender el catálogo de chequeos

Cada chequeo es una línea en `commands_db.py`:

```python
A(C("id_unico", "categoria", "Descripción corta",
    ["comando", "--flag", "{placeholder}"],
    sudo=True, bin="comando", parser="nombre_del_parser",
    deep=False, condition="has_algo", timeout=20))
```

Los placeholders (`{disk_path}`, `{iface}`, `{home}`, `{username}`,
`{battery_path}`, `{nvme_dev}`, etc.) se resuelven en
`scanner.build_context()`. Si el parser todavía no existe, se agrega en
`analyzer.py` y se registra en el diccionario `PARSERS` al final del
archivo — mientras tanto sirven los genéricos `"raw_info"`,
`"keyword_scan"` o `"grep_display"`.

## Dependencies

- Python 3.9+
- `python3-gi`, `gir1.2-gtk-3.0`, `python3-gi-cairo`
- `policykit-1` (pkexec — estándar en Mint)

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 python3-gi-cairo policykit-1
```

## License

MIT — ver [`LICENSE`](LICENSE).

## Author

**Lautaro** — Tecnicatura Universitaria en Programación, UTN Facultad
Regional Avellaneda.

- GitHub: [@LautaroSantiago](https://github.com/LautaroSantiago)
- LinkedIn: [lautaro-subeldia](https://linkedin.com/in/lautaro-subeldia/)
