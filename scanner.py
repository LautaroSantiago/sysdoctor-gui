"""
scanner.py — motor de ejecución: detección de contexto, canal privilegiado
(pkexec) y orquestación del escaneo completo. No depende de GTK: todo lo
que toca la interfaz gráfica vive en controller.py, que llama a este
módulo desde un hilo de fondo y traduce los callbacks a GLib.idle_add.
"""
import glob
import json
import os
import pwd
import queue
import shutil
import subprocess
import threading
import time
from typing import Callable, Dict, List, Optional

import analyzer
from models import CommandResult, CommandSpec, Finding, ScanProgress, Status

HELPER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "priv_helper.py")


# ─────────────────────────── detección de contexto ───────────────────────────

def _run(cmd: List[str], timeout: float = 5.0) -> Optional[str]:
    """Corre un comando sin privilegios, sólo para detección. None si falla."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.stdout
    except Exception:
        return None


def build_context() -> Dict[str, str]:
    """Detecta disco principal, interfaz de red principal, batería, NVMe, etc.
    No necesita privilegios: sólo lectura de /proc, /sys y comandos comunes."""
    ctx: Dict[str, str] = {}

    # --- disco principal (el que contiene la partición raíz) ---
    root_partition = None
    out = _run(["findmnt", "-no", "SOURCE", "/"])
    if out and out.strip().startswith("/dev/"):
        root_partition = out.strip()
    ctx["root_partition"] = root_partition or ""

    disk_name = None
    if root_partition:
        base = os.path.basename(root_partition)
        # nvme0n1p2 -> nvme0n1 ; sda1 -> sda ; mapper/algo -> no aplica
        m = None
        import re
        m = re.match(r"(nvme\d+n\d+)p?\d*$", base)
        if m:
            disk_name = m.group(1)
        else:
            m = re.match(r"([a-zA-Z]+)\d*$", base)
            if m:
                disk_name = m.group(1)
    if not disk_name:
        # fallback: primer disco tipo "disk" que liste lsblk
        out = _run(["lsblk", "-dno", "NAME,TYPE"])
        if out:
            for line in out.splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[1] == "disk":
                    disk_name = parts[0]
                    break
    ctx["disk_name"] = disk_name or ""
    ctx["disk_path"] = f"/dev/{disk_name}" if disk_name else ""

    # --- interfaz de red principal (la de la ruta por defecto) ---
    iface = None
    out = _run(["ip", "route", "show", "default"])
    if out:
        parts = out.split()
        if "dev" in parts:
            iface = parts[parts.index("dev") + 1]
    ctx["iface"] = iface or ""

    # --- home / usuario ---
    ctx["home"] = os.path.expanduser("~")
    try:
        ctx["username"] = pwd.getpwuid(os.getuid()).pw_name
    except Exception:
        ctx["username"] = os.environ.get("USER", "")

    # --- kernel en uso (para initramfs) ---
    ctx["kernel_release"] = os.uname().release

    # --- batería ---
    bat_dirs = sorted(glob.glob("/sys/class/power_supply/BAT*"))
    if bat_dirs:
        ctx["battery_sys_path"] = bat_dirs[0]
        bat_name = os.path.basename(bat_dirs[0])
        upower_out = _run(["upower", "-e"])
        battery_path = ""
        if upower_out:
            for line in upower_out.splitlines():
                if "battery_" + bat_name.lower() in line.lower() or "/battery" in line.lower():
                    battery_path = line.strip()
                    break
        ctx["battery_path"] = battery_path
    else:
        ctx["battery_sys_path"] = ""
        ctx["battery_path"] = ""

    # --- NVMe ---
    nvme_ctrls = sorted(glob.glob("/dev/nvme[0-9]"))
    ctx["nvme_dev"] = nvme_ctrls[0] if nvme_ctrls else ""

    return ctx


def build_conditions(ctx: Dict[str, str]) -> Dict[str, bool]:
    cond = {}
    cond["has_disk"] = bool(ctx.get("disk_path"))
    cond["has_iface"] = bool(ctx.get("iface"))
    cond["has_battery"] = bool(ctx.get("battery_sys_path"))
    cond["has_nvme"] = bool(ctx.get("nvme_dev"))
    cond["has_root_partition"] = bool(ctx.get("root_partition")) and ctx["root_partition"].startswith("/dev/")
    cond["has_sshd_config"] = os.path.exists("/etc/ssh/sshd_config")
    cond["has_aide_db"] = os.path.exists("/var/lib/aide/aide.db")
    active = _run(["systemctl", "is-active", "auditd"])
    cond["has_auditd_active"] = bool(active) and active.strip() == "active"
    return cond


def _which(name: str) -> Optional[str]:
    found = shutil.which(name)
    if found:
        return found
    for d in ("/usr/sbin", "/sbin", "/usr/local/sbin"):
        p = os.path.join(d, name)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def binary_available(spec: CommandSpec) -> bool:
    if not spec.needs_bin:
        return True
    return any(_which(b) for b in spec.needs_bin)


def resolve_argv(spec: CommandSpec, ctx: Dict[str, str]) -> Optional[List[str]]:
    out = []
    for a in spec.cmd:
        if "{" not in a:
            out.append(a)
            continue
        resolved = a
        for key, val in ctx.items():
            token = "{" + key + "}"
            if token in resolved:
                resolved = resolved.replace(token, val)
        out.append(resolved)
    return out


# ─────────────────────────── canal privilegiado (pkexec) ───────────────────────────

class PrivilegedChannel:
    """Un único proceso root (pkexec + priv_helper.py) reutilizado para todos
    los comandos que necesitan privilegios. Sólo se pide la contraseña UNA vez
    por escaneo (prompt gráfico nativo de polkit)."""

    def __init__(self):
        self.proc: Optional[subprocess.Popen] = None
        self.lock = threading.Lock()
        self.available = False
        self.error: Optional[str] = None
        self._queue: "queue.Queue" = queue.Queue()
        self._reader: Optional[threading.Thread] = None

    def _read_loop(self):
        try:
            assert self.proc and self.proc.stdout
            for line in self.proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self._queue.put(msg)
        except Exception:
            pass
        finally:
            self._queue.put(None)  # centinela: el proceso murió / stdout se cerró

    def _send_and_wait(self, req: dict, timeout: float) -> Optional[dict]:
        try:
            assert self.proc and self.proc.stdin
            self.proc.stdin.write(json.dumps(req) + "\n")
            self.proc.stdin.flush()
        except Exception:
            return None
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return {"error": "__timeout__"}

    def start(self, handshake_timeout: float = 180.0) -> bool:
        pkexec = shutil.which("pkexec")
        python3 = shutil.which("python3") or "/usr/bin/python3"
        if not pkexec:
            self.error = "pkexec no está instalado (paquete policykit-1)."
            return False
        if not os.path.exists(HELPER_PATH):
            self.error = f"No se encontró el helper privilegiado en {HELPER_PATH}."
            return False
        try:
            self.proc = subprocess.Popen(
                [pkexec, python3, HELPER_PATH],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1,
            )
        except Exception as e:
            self.error = f"No se pudo lanzar pkexec: {e}"
            return False

        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

        resp = self._send_and_wait({"id": "__ping__", "cmd": ["true"], "timeout": 5},
                                    handshake_timeout)
        if not resp or resp.get("error"):
            stderr_txt = ""
            try:
                if self.proc.stderr:
                    stderr_txt = self.proc.stderr.read(2000) or ""
            except Exception:
                pass
            self.error = "No se obtuvo acceso privilegiado (cancelado o denegado)."
            if stderr_txt.strip():
                self.error += f" — {stderr_txt.strip()[:200]}"
            self.available = False
            return False
        self.available = True
        return True

    def run(self, spec_id: str, argv: List[str], timeout: float) -> dict:
        with self.lock:
            if not self.available or self.proc is None or self.proc.poll() is not None:
                return {"error": "__no_priv__"}
            resp = self._send_and_wait({"id": spec_id, "cmd": argv, "timeout": timeout},
                                        timeout + 10)
            if resp is None:
                self.available = False
                return {"error": "__no_priv__"}
            return resp

    def stop(self):
        if not self.proc:
            return
        try:
            if self.proc.stdin:
                self.proc.stdin.write(json.dumps({"cmd": "__quit__"}) + "\n")
                self.proc.stdin.flush()
            self.proc.wait(timeout=3)
        except Exception:
            try:
                self.proc.terminate()
            except Exception:
                pass


# ───────────────────────────────── Scanner ─────────────────────────────────

ProgressCB = Callable[[ScanProgress], None]
FindingCB = Callable[[Finding], None]


class ScanCancelled(Exception):
    pass


class Scanner:
    def __init__(self, commands: List[CommandSpec]):
        self.commands = commands
        self.channel = PrivilegedChannel()
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    def _run_unprivileged(self, spec: CommandSpec, argv: List[str]) -> CommandResult:
        start = time.monotonic()
        try:
            proc = subprocess.run(argv, capture_output=True, text=True,
                                   timeout=spec.timeout, errors="replace")
            return CommandResult(spec, proc.returncode, proc.stdout, proc.stderr,
                                  None, time.monotonic() - start)
        except subprocess.TimeoutExpired:
            return CommandResult(spec, None, "", "", "__timeout__", time.monotonic() - start)
        except FileNotFoundError:
            return CommandResult(spec, None, "", "", "binario no encontrado",
                                  time.monotonic() - start)
        except Exception as e:
            return CommandResult(spec, None, "", "", f"{type(e).__name__}: {e}",
                                  time.monotonic() - start)

    def _run_privileged(self, spec: CommandSpec, argv: List[str]) -> CommandResult:
        start = time.monotonic()
        resp = self.channel.run(spec.id, argv, spec.timeout)
        if resp.get("error") and resp.get("returncode") is None and "stdout" not in resp:
            return CommandResult(spec, None, "", "", resp["error"], time.monotonic() - start)
        return CommandResult(
            spec, resp.get("returncode"), resp.get("stdout", ""), resp.get("stderr", ""),
            resp.get("error"), resp.get("duration", time.monotonic() - start),
        )

    def run_one(self, spec: CommandSpec, ctx: Dict[str, str]) -> Finding:
        argv = resolve_argv(spec, ctx)
        if argv is None:
            return Finding(spec, None, Status.SKIP, "Contexto no disponible para este chequeo.", "")
        result = self._run_privileged(spec, argv) if spec.needs_sudo else \
            self._run_unprivileged(spec, argv)
        return analyzer.analyze(spec, result)

    def run_scan(self, include_deep: bool, progress_cb: ProgressCB,
                 finding_cb: FindingCB) -> None:
        """Corre sincrónicamente (se espera que el caller lo dispare en un hilo)."""
        self._cancel.clear()
        ctx = build_context()
        cond = build_conditions(ctx)

        planned = []
        for spec in self.commands:
            if spec.deep and not include_deep:
                continue
            if spec.condition and not cond.get(spec.condition, False):
                continue
            if not binary_available(spec):
                continue
            planned.append(spec)

        needs_priv = any(s.needs_sudo for s in planned)
        if needs_priv:
            progress_cb(ScanProgress(0, len(planned), "Pidiendo acceso privilegiado…"))
            self.channel.start()
            if not self.channel.available:
                # seguimos igual: los chequeos con sudo quedan como SKIP con motivo claro
                pass

        total = len(planned)
        failed_services: List[str] = []
        for i, spec in enumerate(planned):
            if self._cancel.is_set():
                break
            progress_cb(ScanProgress(i, total, spec.title))
            finding = self.run_one(spec, ctx)
            if spec.id == "svc_failed" and finding.status == Status.ERROR:
                failed_services = [l.split()[0] for l in finding.raw_output.splitlines() if l.split()]
            finding_cb(finding)
            progress_cb(ScanProgress(i + 1, total, spec.title))

        # seguimiento dinámico: logs de cada servicio que falló
        for name in failed_services[:5]:
            if self._cancel.is_set():
                break
            sub = CommandSpec(
                id=f"svc_log_{name}", category="servicios",
                title=f"Log reciente del servicio fallido: {name}",
                cmd=["journalctl", "-u", name, "-b", "--no-pager", "-n", "40"],
                needs_sudo=True, parser="tail_lines", timeout=10,
            )
            finding_cb(self.run_one(sub, ctx))

        self.channel.stop()
        progress_cb(ScanProgress(total, total, "Listo."))


# ─────────────────── instalación opcional de herramientas ───────────────────
# Todos los paquetes que el documento original pide instalar en algún punto.
# Nunca se instalan solos: sólo si el usuario aprieta "Instalar herramientas".

RECOMMENDED_PACKAGES = sorted(set([
    "inxi", "lshw", "dmidecode", "lm-sensors", "smartmontools", "hdparm",
    "ethtool", "nvme-cli", "mesa-utils", "sysstat", "memtester",
    "ufw", "fail2ban", "rkhunter", "chkrootkit", "clamav", "debsums",
    "glances", "s-tui", "stress-ng", "nethogs", "iftop", "tcpdump", "arp-scan",
    "lynis", "unhide", "auditd", "ncdu", "fio", "strace", "ltrace", "lsof",
    "timeshift", "rsync", "testdisk", "gddrescue", "debsecan", "needrestart",
    "apt-listbugs", "aide", "systemd-coredump", "apport", "sysbench",
    "glmark2", "xorg-xdiagnose", "e2fsprogs", "kdump-tools", "usbutils",
    "chrony", "lvm2", "mdadm", "quota", "acpi", "mokutil", "cryptsetup",
    "cpu-checker", "smem", "iotop", "nmap",
]))


class ToolInstaller:
    """Instala RECOMMENDED_PACKAGES uno por uno vía el mismo canal pkexec,
    para que un nombre de paquete inválido (ej. boot-repair sin su PPA)
    no aborte la instalación de los demás."""

    def __init__(self):
        self.channel = PrivilegedChannel()

    def run(self, log_cb: Callable[[str, bool], None],
            progress_cb: ProgressCB) -> None:
        progress_cb(ScanProgress(0, len(RECOMMENDED_PACKAGES), "Pidiendo acceso privilegiado…"))
        if not self.channel.start():
            log_cb(f"No se pudo obtener acceso privilegiado: {self.channel.error}", False)
            return
        total = len(RECOMMENDED_PACKAGES)
        for i, pkg in enumerate(RECOMMENDED_PACKAGES):
            progress_cb(ScanProgress(i, total, f"Instalando {pkg}…"))
            resp = self.channel.run(f"install:{pkg}",
                                     ["apt-get", "install", "-y", "--no-install-recommends", pkg],
                                     60)
            ok = resp.get("returncode") == 0
            log_cb(pkg, ok)
            progress_cb(ScanProgress(i + 1, total, f"{pkg} {'OK' if ok else 'falló'}"))
        self.channel.stop()
