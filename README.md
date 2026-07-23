# sysdoctor-gui

Herramienta gráfica de diagnóstico de sistema para **Linux Mint MATE**.
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

## Índice

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

## Motivación

Este proyecto nace de una guía personal de diagnóstico de Linux Mint MATE
(~280 comandos organizados en 10 partes, de hardware a tareas programadas)
pensada para correr a mano en la terminal. `sysdoctor-gui` la convierte en
una herramienta gráfica: corre los chequeos relevantes, interpreta cada
salida y separa lo que es sólo información de lo que es un problema real.

## Características

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

## Principio de diseño: sólo lectura

El escaneo automático **nunca** instala paquetes, cambia configuración,
crea snapshots ni corre benchmarks/estrés por su cuenta. Quedan afuera a
propósito: recuperación de disco (testdisk/ddrescue), `apt --fix-broken
install`, `ufw enable`, `update-grub`, fio/sysbench/stress-ng, herramientas
interactivas (htop, glances), y cualquier comando que necesite un objetivo
que no se pueda determinar sin adivinar (ej. un servidor remoto puntual).

Cuando un chequeo encuentra un problema con una solución conocida, el
reporte incluye el comando sugerido listo para copiar — la decisión de
correrlo queda siempre del lado del usuario.

## Privilegios (pkexec)

Los chequeos que necesitan root piden acceso **una sola vez** por escaneo,
vía el prompt gráfico nativo de polkit (`pkexec`), no `sudo` por terminal.
A partir de ahí, todos los comandos privilegiados se ejecutan a través de
un único proceso auxiliar (`priv_helper.py`) lanzado una vez — nunca se
piden credenciales por cada comando individual. Si el prompt se cancela,
esos chequeos puntuales quedan marcados como omitidos y el resto del
análisis se completa igual.

## Instalación

```bash
git clone https://github.com/LautaroSantiago/sysdoctor-gui.git
cd sysdoctor-gui
./install.sh
```

El instalador es idempotente: copia la app a `~/.local/share/sysdoctor-gui`,
un lanzador a `~/.local/bin/sysdoctor-gui`, el ícono (hicolor) y la entrada
de menú de MATE. Chequea las dependencias y ofrece instalarlas si faltan.

## Uso

Desde el menú de MATE, o por terminal:

```bash
sysdoctor-gui
```

Sin instalar, directamente desde el repo:

```bash
python3 main.py
```

1. Tildá **"Chequeos profundos"** si querés incluir rkhunter/lynis/clamav/aide.
2. Apretá **"Analizar sistema"**. Si algún chequeo necesita privilegios te
   va a pedir la contraseña una sola vez.
3. Revisá la pestaña **Resumen** para ver sólo lo que necesita atención, o
   navegá por categoría en la barra lateral.
4. **"Guardar reporte"** exporta todo a un `.md`.

## Estructura del proyecto

```
models.py         estructuras de datos compartidas (CommandSpec, Finding, Status)
commands_db.py    catálogo de ~230 chequeos, organizados en 19 categorías
analyzer.py       interpreta la salida cruda de cada comando -> Finding
scanner.py        detección de contexto, canal pkexec, orquestación del escaneo
priv_helper.py    proceso mínimo que corre como root (lanzado vía pkexec)
theme.py          paleta de colores y CSS de GTK3
window.py         interfaz gráfica (GTK3)
controller.py     conecta la ventana con el scanner en un hilo de fondo
app.py            Gtk.Application
main.py           punto de entrada
install.sh        instalador idempotente para el usuario actual
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

## Dependencias

- Python 3.9+
- `python3-gi`, `gir1.2-gtk-3.0`, `python3-gi-cairo`
- `policykit-1` (pkexec — estándar en Mint)

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 python3-gi-cairo policykit-1
```

## Licencia

MIT — ver [`LICENSE`](LICENSE).

## Autor

**Lautaro** — Tecnicatura Universitaria en Programación, UTN Facultad
Regional Avellaneda.

- GitHub: [@LautaroSantiago](https://github.com/LautaroSantiago)
- LinkedIn: [lautaro-subeldia](https://linkedin.com/in/lautaro-subeldia/)
