#!/usr/bin/env python3
"""main.py — punto de entrada de sysdoctor-gui."""
import sys

from app import SysDoctorApp


def main():
    app = SysDoctorApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
