# sysdoctor-gui

<p align="center">

<a href="README.md">
    <img src="https://img.shields.io/badge/🇪🇸-Español-2ea44f?style=for-the-badge" alt="Spanish">
</a>

<a href="README.en.md">
    <img src="https://img.shields.io/badge/🇬🇧-English-0969da?style=for-the-badge" alt="English">
</a>

</p>

System diagnostic tool for **Linux Mint MATE**.

> **Note:** This is the English version of the documentation.
> For the Spanish version, click the **Español** button above.

## Features

- ~230 read-only diagnostic checks.
- GTK3 graphical interface.
- Prioritized summary of warnings and errors.
- Automatic hardware and system detection.
- Optional deep scans.
- Markdown report export.
- Native `pkexec` privilege elevation.

## Installation

```bash
git clone https://github.com/LautaroSantiago/sysdoctor-gui.git
cd sysdoctor-gui
./install.sh
```

## Usage

```bash
sysdoctor-gui
```

or

```bash
python3 main.py
```

## Project structure

```text
sysdoctor-gui/
├── analyzer.py
├── app.py
├── commands_db.py
├── controller.py
├── install.sh
├── main.py
├── models.py
├── priv_helper.py
├── scanner.py
├── theme.py
├── window.py
├── LICENSE
└── README.md
```

## Architecture

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

## License

MIT License.

## Author

**Lautaro** — University Programming Technician, UTN Facultad Regional Avellaneda.

- GitHub: https://github.com/LautaroSantiago
- LinkedIn: https://linkedin.com/in/lautaro-subeldia/
