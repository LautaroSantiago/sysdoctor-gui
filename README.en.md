<div align="center">

# 🩺 sysdoctor-gui

**Complete Linux Mint MATE diagnostics, in a graphical interface.**

Runs ~230 read-only checks covering hardware, kernel, services, disk,
network, security, desktop, packages, performance, power and scheduled
tasks — and shows you only what actually needs your attention.

![Python](https://img.shields.io/badge/Python-3.9%2B-3ea86b?style=flat-square&logo=python&logoColor=white)
![GTK](https://img.shields.io/badge/GTK-3-3ea86b?style=flat-square&logo=gtk&logoColor=white)
![Platform](https://img.shields.io/badge/platform-Linux%20Mint%20MATE-3ea86b?style=flat-square&logo=linux&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-3ea86b?style=flat-square)
![Status](https://img.shields.io/badge/status-active-3ea86b?style=flat-square)

[Leer en español](README.md)

</div>

---

## Table of contents

- [Motivation](#motivation)
- [Features](#features)
- [Design principle: read-only](#design-principle-read-only)
- [Privileges (pkexec)](#privileges-pkexec)
- [Installation](#installation)
- [Usage](#usage)
- [Project structure](#project-structure)
- [Extending the checks catalog](#extending-the-checks-catalog)
- [Dependencies](#dependencies)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)
- [Author](#author)

## Motivation

This project started from a personal Linux Mint MATE diagnostics guide
(~280 commands organized in 10 parts, from hardware to scheduled tasks)
meant to be run by hand in a terminal. `sysdoctor-gui` turns it into a
graphical tool: it runs the relevant checks, interprets each output with
its own heuristics, and separates what's just information from what's an
actual problem — without you having to read hundreds of lines of log
output yourself.

## Features

| | |
|---|---|
| 🗂️ **~230 checks** | Organized into 19 browsable categories, faithful to the original guide. |
| 🚨 **Prioritized summary** | A dedicated tab collects only errors and warnings across the whole system. |
| 🧠 **Real interpretation** | 50+ specific heuristics: SMART health, down systemd services, disk/inode usage thresholds, OOM killer, unmitigated CPU vulnerabilities, rootkits, package integrity, battery health, degraded RAID, and more. |
| 🔎 **Context detection** | Main disk, network interface, battery, NVMe — no hardcoded paths like `/dev/sda` or `eth0`. |
| 🐢 **Optional deep checks** | rkhunter, lynis, clamav, aide, debsums behind a checkbox; the normal scan runs in under a minute. |
| 📦 **Tool installer** | An explicit, separate action, package by package — one invalid name doesn't block the rest. |
| 📝 **Exportable report** | Full results to a `.md` file with one click. |
| 🔗 **Automatic follow-up** | If a systemd service failed, its recent log gets pulled in automatically. |
| 🎨 **Own visual identity** | Palette and architecture consistent with my other Mint MATE desktop projects. |

## Design principle: read-only

The automatic scan **never** installs packages, changes configuration,
creates snapshots, or runs benchmarks/stress tests on its own. Deliberately
left out: disk recovery (testdisk/ddrescue), `apt --fix-broken install`,
`ufw enable`, `update-grub`, fio/sysbench/stress-ng, interactive tools
(htop, glances), and any command that needs a target that can't be
determined without guessing (e.g. a specific remote server).

When a check finds a problem with a known fix, the report includes the
suggested command ready to copy — the decision to run it is always left
to the user.

## Privileges (pkexec)

Checks that need root ask for access **only once** per scan, through
polkit's native graphical prompt (`pkexec`), not `sudo` in a terminal.
From there, every privileged command runs through a single helper process
(`priv_helper.py`) launched once — credentials are never requested per
individual command. If the prompt is cancelled, those specific checks are
marked as skipped and the rest of the scan still completes.

## Installation

```bash
git clone https://github.com/LautaroSantiago/sysdoctor-gui.git
cd sysdoctor-gui
./install.sh
```

The installer is idempotent: it copies the app to
`~/.local/share/sysdoctor-gui`, a launcher to `~/.local/bin/sysdoctor-gui`,
the icon (hicolor), and the MATE menu entry. It checks dependencies and
offers to install them if missing.

## Usage

From the MATE menu, or from a terminal:

```bash
sysdoctor-gui
```

Without installing, directly from the repo:

```bash
python3 main.py
```

1. Check **"Deep checks"** if you want to include rkhunter/lynis/clamav/aide.
2. Click **"Analyze system"**. If any check needs privileges, you'll be
   asked for your password once.
3. Check the **Summary** tab to see only what needs attention, or browse
   by category in the sidebar.
4. **"Save report"** exports everything to a `.md` file.

## Project structure

```
sysdoctor-gui/
├── models.py         # shared data structures (CommandSpec, Finding, Status)
├── commands_db.py     # catalog of ~230 checks, organized into 19 categories
├── analyzer.py         # interprets each command's raw output -> Finding
├── scanner.py          # context detection, pkexec channel, scan orchestration
├── priv_helper.py     # minimal process that runs as root (launched via pkexec)
├── theme.py             # GTK3 color palette and CSS
├── window.py           # graphical interface (GTK3)
├── controller.py       # connects the window to the scanner on a background thread
├── app.py               # Gtk.Application
├── main.py              # entry point
├── install.sh            # idempotent installer for the current user
├── sysdoctor-gui.desktop # MATE menu launcher
└── icon.svg               # app icon
```

## Extending the checks catalog

Each check is one line in `commands_db.py`:

```python
A(C("unique_id", "category", "Short description",
    ["command", "--flag", "{placeholder}"],
    sudo=True, bin="command", parser="parser_name",
    deep=False, condition="has_something", timeout=20))
```

Placeholders (`{disk_path}`, `{iface}`, `{home}`, `{username}`,
`{battery_path}`, `{nvme_dev}`, etc.) are resolved in
`scanner.build_context()`. If the parser doesn't exist yet, add it in
`analyzer.py` and register it in the `PARSERS` dictionary at the end of
the file — the generic `"raw_info"`, `"keyword_scan"` or `"grep_display"`
work fine in the meantime.

## Dependencies

- Python 3.9+
- `python3-gi`, `gir1.2-gtk-3.0`, `python3-gi-cairo`
- `policykit-1` (pkexec — standard on Mint)

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 python3-gi-cairo policykit-1
```

## Roadmap

- [ ] `.deb` packaging
- [ ] Scan history to compare changes over time
- [ ] English translation of the checks catalog
- [ ] "This category only" mode for quick, targeted scans

## Contributing

Issues and pull requests are welcome. If you add a new check to the
catalog, explain which command it replaces and why it was left out of the
default scan (if applicable) — it helps keep the "read-only" principle
consistent across the project.

## License

MIT — see [`LICENSE`](LICENSE).

---

## Author

**Lautaro** — Computer Programming Technical Degree (Tecnicatura
Universitaria en Programación), UTN Facultad Regional Avellaneda,
Argentina.

[![GitHub](https://img.shields.io/badge/GitHub-LautaroSantiago-3ea86b?style=flat-square&logo=github&logoColor=white)](https://github.com/LautaroSantiago)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-lautaro--subeldia-3ea86b?style=flat-square&logo=linkedin&logoColor=white)](https://linkedin.com/in/lautaro-subeldia/)
