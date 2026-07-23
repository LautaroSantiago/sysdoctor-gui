#!/usr/bin/env python3
"""
priv_helper.py — proceso auxiliar que corre como root (lanzado vía pkexec).

Protocolo: por cada línea JSON leída de stdin {"id": str, "cmd": [argv...],
"timeout": float} ejecuta el comando y escribe una línea JSON a stdout:
{"id": str, "returncode": int|null, "stdout": str, "stderr": str,
 "error": str|null, "duration": float}.

Termina al recibir {"cmd": "__quit__"} o al cerrarse stdin (EOF).
No depende de GTK ni de nada fuera de la librería estándar: éste es el
único módulo que corre con privilegios de root, así que se mantiene lo
más chico y auditable posible.
"""
import json
import subprocess
import sys
import time


def main():
    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            msg = json.loads(raw_line)
        except json.JSONDecodeError:
            continue

        if msg.get("cmd") == "__quit__":
            break

        req_id = msg.get("id", "")
        cmd = msg.get("cmd") or []
        timeout = msg.get("timeout", 20.0)

        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
                errors="replace",
            )
            reply = {
                "id": req_id, "returncode": proc.returncode,
                "stdout": proc.stdout, "stderr": proc.stderr,
                "error": None, "duration": time.monotonic() - start,
            }
        except subprocess.TimeoutExpired:
            reply = {
                "id": req_id, "returncode": None, "stdout": "", "stderr": "",
                "error": "__timeout__", "duration": time.monotonic() - start,
            }
        except FileNotFoundError:
            reply = {
                "id": req_id, "returncode": None, "stdout": "", "stderr": "",
                "error": "binario no encontrado", "duration": time.monotonic() - start,
            }
        except Exception as e:  # nunca queremos que el helper se caiga entero
            reply = {
                "id": req_id, "returncode": None, "stdout": "", "stderr": "",
                "error": f"{type(e).__name__}: {e}", "duration": time.monotonic() - start,
            }

        sys.stdout.write(json.dumps(reply) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
