"""
analyzer.py — interpreta la salida cruda de cada comando y produce un Finding.

Cada función de PARSERS recibe (spec, result) y devuelve
(status, summary, detail, suggested_fix). analyze() arma el Finding final.
"""
import os
import re
from collections import Counter
from typing import List, Optional, Tuple

from models import CommandResult, CommandSpec, Finding, Status

# ───────────────────────────── utilidades ─────────────────────────────

_ERROR_WORDS = [r"\berror\b", r"\bfail(ed|ure)?\b", r"\bcritical\b", r"\bdenied\b"]


def _combined(result: CommandResult) -> str:
    parts = [result.stdout or ""]
    if result.stderr:
        parts.append(result.stderr)
    return "\n".join(p for p in parts if p)


def _lines(text: str) -> List[str]:
    return [l for l in (text or "").splitlines() if l.strip()]


def _truncate(items: List[str], n: int = 40) -> str:
    if len(items) <= n:
        return "\n".join(items)
    resto = len(items) - n
    return "\n".join(items[:n]) + f"\n… (+{resto} línea{'s' if resto != 1 else ''} más)"


def _grep(text: str, patterns: List[str], after: int = 0, ignorecase: bool = True) -> List[str]:
    """Emula 'grep -A N -E pat1|pat2|...' pero en Python, sobre texto ya capturado."""
    if not patterns:
        return []
    flags = re.IGNORECASE if ignorecase else 0
    compiled = [re.compile(p, flags) for p in patterns]
    lines = (text or "").splitlines()
    out, i = [], 0
    while i < len(lines):
        if any(c.search(lines[i]) for c in compiled):
            block = lines[i:i + 1 + after]
            out.extend(block)
            if after:
                out.append("—")
            i += 1 + after
        else:
            i += 1
    if out and out[-1] == "—":
        out.pop()
    return out


def _pct(value: str) -> Optional[int]:
    m = re.search(r"(\d+)\s*%", value)
    return int(m.group(1)) if m else None


def R(status: Status, summary: str, detail: str = "", fix: Optional[str] = None):
    return (status, summary, detail, fix)


def _ok(summary, detail=""):
    return R(Status.OK, summary, detail)


def _warn(summary, detail="", fix=None):
    return R(Status.WARN, summary, detail, fix)


def _error(summary, detail="", fix=None):
    return R(Status.ERROR, summary, detail, fix)


def _info(summary, detail=""):
    return R(Status.INFO, summary, detail)


def _skip(summary):
    return R(Status.SKIP, summary)


# ─────────────────────────────── dispatch ───────────────────────────────

def analyze(spec: CommandSpec, result: Optional[CommandResult]) -> Finding:
    if result is None:
        return Finding(spec, result, Status.SKIP, "No se corrió.", "")

    if result.error == "__timeout__":
        return Finding(spec, result, Status.WARN,
                        "El comando no respondió a tiempo (timeout).", _combined(result))
    if result.error == "__no_priv__":
        return Finding(spec, result, Status.SKIP,
                        "Se omitió: requiere privilegios y no se obtuvo acceso.", "")
    if result.error:
        return Finding(spec, result, Status.SKIP, f"No se pudo ejecutar: {result.error}", "")

    fn = PARSERS.get(spec.parser, raw_info)
    try:
        status, summary, detail, fix = fn(spec, result)
    except Exception as e:  # un parser roto nunca debe tirar abajo el scan completo
        status, summary, detail, fix = Status.INFO, "(no se pudo interpretar la salida)", \
            f"{type(e).__name__}: {e}", None
    return Finding(spec, result, status, summary, detail, fix, raw_output=_combined(result))


# ──────────────────────────── parsers genéricos ────────────────────────────

def raw_info(spec, result):
    text = _combined(result).strip()
    if not text:
        return _info("Sin salida.")
    first = _lines(text)[0][:140]
    return _info(first, text)


def grep_display(spec, result):
    text = _combined(result)
    matches = _grep(text, spec.patterns, spec.context_after) if spec.patterns else _lines(result.stdout)
    if not matches:
        return _info("Sin coincidencias.")
    return _info(f"{len(matches)} línea(s) relevante(s).", _truncate(matches))


def keyword_scan(spec, result):
    text = _combined(result)
    matches = _grep(text, spec.patterns, spec.context_after) if spec.patterns else _lines(result.stdout)
    if not matches:
        return _ok("Sin coincidencias.")
    return _warn(f"Se encontraron {len(matches)} coincidencia(s).", _truncate(matches))


def crash_signals_check(spec, result):
    text = _combined(result)
    matches = _grep(text, spec.patterns, spec.context_after) if spec.patterns else _lines(result.stdout)
    if not matches:
        return _ok("Sin señales de crash.")
    return _error(f"Se encontraron {len(matches)} señal(es) de crash.", _truncate(matches))


def head_lines(spec, result):
    lines = _lines(_combined(result))
    if not lines:
        return _info("Sin salida.")
    shown = lines[:30]
    note = "" if len(lines) <= 30 else f"\n… (+{len(lines) - 30} línea(s) más)"
    return _info(f"{len(lines)} línea(s).", "\n".join(shown) + note)


def tail_lines(spec, result):
    lines = _lines(_combined(result))
    if not lines:
        return _info("Sin salida.")
    shown = lines[-50:]
    note = f"({len(lines) - len(shown)} línea(s) anteriores omitidas)\n" if len(lines) > len(shown) else ""
    return _info(f"{len(lines)} línea(s).", note + "\n".join(shown))


def count_lines_info(spec, result):
    n = len(_lines(result.stdout))
    return _info(f"{n} línea(s) en total.")


def count_list_info(spec, result):
    lines = _lines(result.stdout)
    return _info(f"{len(lines)} archivo(s) encontrados.", _truncate(lines))


def timed_run(spec, result):
    return _info(f"Tardó {result.duration:.2f}s en responder.", _combined(result).strip()[:300])


# ────────────────────────── parsers específicos ──────────────────────────

def smart_health(spec, result):
    text = result.stdout.lower()
    if "failed" in text:
        return _error("El disco reporta salud SMART FAILED.", result.stdout,
                       fix="Hacé un backup ya y planeá reemplazar el disco.")
    if "passed" in text:
        return _ok("Salud SMART: PASSED.")
    return _info("No se pudo determinar el estado SMART (¿no soportado?).", result.stdout)


def smart_attrs(spec, result):
    bad = {}
    for attr in ("Reallocated_Sector_Ct", "Current_Pending_Sector",
                 "Offline_Uncorrectable", "Reported_Uncorrect"):
        m = re.search(rf"{attr}\s+.*?(\d+)\s*$", result.stdout, re.MULTILINE)
        if m and int(m.group(1)) > 0:
            bad[attr] = int(m.group(1))
    if bad:
        detail = "\n".join(f"{k}: {v}" for k, v in bad.items())
        return _warn(f"Atributos SMART con valores > 0: {', '.join(bad)}.", detail,
                     fix="Revisá smartctl -a completo y considerá un backup preventivo.")
    if not result.stdout.strip():
        return _skip("Sin datos SMART disponibles.")
    return _ok("Atributos SMART clave en 0 (sin sectores reasignados/pendientes).")


def failed_units(spec, result):
    lines = _lines(result.stdout)
    if not lines:
        return _ok("No hay servicios fallando.")
    names = [l.split()[0] for l in lines if l.split()]
    return _error(f"{len(lines)} servicio(s) fallando: {', '.join(names)}", "\n".join(lines),
                  fix=f"journalctl -u {names[0]} -b   # revisá el log de cada uno")


def journal_prev_boot(spec, result):
    low = (result.stderr or "").lower()
    if result.returncode not in (0,) and (
        "no such boot" in low or "failed to look up boot" in low or "not available" in low
    ) and not result.stdout.strip():
        return _skip("No hay un arranque anterior registrado todavía.")
    return keyword_scan(spec, result)


def disk_usage(spec, result):
    offenders = []
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 6:
            continue
        pct = _pct(parts[4])
        if pct is None:
            continue
        if pct >= 85:
            offenders.append((pct, f"{parts[5]} ({parts[0]}): {pct}% usado"))
    if not offenders:
        return _ok("Ninguna partición supera el 85% de uso.")
    offenders.sort(reverse=True)
    worst = offenders[0][0]
    status = Status.ERROR if worst >= 95 else Status.WARN
    return R(status, f"{len(offenders)} partición(es) con uso alto de disco (máx {worst}%).",
             "\n".join(o[1] for o in offenders))


def inode_usage(spec, result):
    offenders = []
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 6:
            continue
        pct = _pct(parts[4])
        if pct is None:
            continue
        if pct >= 85:
            offenders.append((pct, f"{parts[5]} ({parts[0]}): {pct}% de inodos usados"))
    if not offenders:
        return _ok("Ninguna partición se está quedando sin inodos.")
    offenders.sort(reverse=True)
    worst = offenders[0][0]
    status = Status.ERROR if worst >= 95 else Status.WARN
    return R(status, f"{len(offenders)} partición(es) con uso alto de inodos (máx {worst}%).",
             "\n".join(o[1] for o in offenders))


def oom_check(spec, result):
    matches = _grep(_combined(result), [r"out of memory", r"oom.?killer", r"oom_kill"])
    if not matches:
        return _ok("El OOM Killer no actuó (no se quedó sin memoria).")
    return _error(f"El OOM Killer mató proceso(s) por falta de RAM ({len(matches)} evento(s)).",
                  _truncate(matches),
                  fix="Considerá agregar swap o revisar qué proceso consume tanta RAM.")


def security_sysctl(spec, result):
    zeros = [l for l in result.stdout.splitlines() if re.search(r"=\s*0\s*$", l)]
    if zeros:
        return _warn(f"{len(zeros)} parámetro(s) de seguridad del kernel en modo permisivo (0).",
                     "\n".join(zeros))
    return _ok("Parámetros de seguridad del kernel en modo restrictivo.")


def findmnt_verify(spec, result):
    if result.returncode == 0 and not result.stdout.strip():
        return _ok("/etc/fstab sin errores de configuración.")
    return _warn("findmnt encontró problemas en /etc/fstab.", _combined(result))


def broken_symlinks(spec, result):
    paths = _lines(result.stdout)
    broken = [p for p in paths if p and not os.path.exists(p)]
    if not broken:
        return _ok(f"Sin enlaces simbólicos rotos ({len(paths)} revisados).")
    return _warn(f"{len(broken)} enlace(s) simbólico(s) roto(s).", _truncate(broken))


def recent_files_check(spec, result):
    paths = [p for p in _lines(result.stdout) if not p.startswith(("/tmp", "/var/log"))]
    if not paths:
        return _info("Sin archivos modificados en las últimas 24hs fuera de tmp/logs.")
    return _info(f"{len(paths)} archivo(s) modificados en las últimas 24hs.", _truncate(paths))


def rootkit_output(spec, result):
    text = _combined(result)
    infected = _grep(text, [r"infected", r"\bINFECTED\b"])
    warnings = _grep(text, [r"warning"])
    if infected:
        return _error(f"Se encontraron {len(infected)} indicio(s) de infección.", _truncate(infected))
    if warnings:
        return _warn(f"{len(warnings)} warning(s) — revisar (pueden ser falsos positivos comunes en Mint).",
                     _truncate(warnings))
    return _ok("Sin infecciones ni warnings.")


def clamav_check(spec, result):
    m = re.search(r"Infected files:\s*(\d+)", result.stdout)
    if m and int(m.group(1)) > 0:
        found = _grep(result.stdout, [r"FOUND$"])
        return _error(f"ClamAV encontró {m.group(1)} archivo(s) infectado(s).", _truncate(found))
    return _ok("ClamAV: sin archivos infectados.")


def debsums_check(spec, result):
    lines = _lines(result.stdout)
    if not lines:
        return _ok("Todos los archivos coinciden con su checksum original.")
    return _warn(f"{len(lines)} archivo(s) no coinciden con el paquete original.", _truncate(lines),
                 fix="dpkg -S <archivo>   # identificá el paquete, luego: sudo apt-get install --reinstall <paquete>")


def needrestart_check(spec, result):
    text = result.stdout
    svc = re.findall(r"NEEDRESTART-SVC:\s*(\S+)", text)
    ksta = re.search(r"NEEDRESTART-KSTA:\s*(\d+)", text)
    problems = []
    if svc:
        problems.append(f"{len(svc)} servicio(s) necesitan reiniciarse: {', '.join(svc[:10])}")
    if ksta and ksta.group(1) != "1":
        problems.append("El kernel en uso no coincide con el instalado (hace falta reiniciar).")
    if problems:
        return _warn(" / ".join(problems), text, fix="sudo needrestart -r a")
    return _ok("No hace falta reiniciar ningún servicio ni el sistema.")


def lynis_output(spec, result):
    text = result.stdout
    warns = _grep(text, [r"warning"])
    idx = re.search(r"Hardening index\s*:\s*(\d+)", text)
    idx_txt = f" Índice de hardening: {idx.group(1)}." if idx else ""
    if warns:
        return _warn(f"Lynis reportó {len(warns)} warning(s).{idx_txt}", _truncate(warns))
    return _info(f"Lynis no reportó warnings.{idx_txt}", text[-2000:])


def aide_check(spec, result):
    added = re.search(r"Added entries:\s*(\d+)", result.stdout)
    removed = re.search(r"Removed entries:\s*(\d+)", result.stdout)
    changed = re.search(r"Changed entries:\s*(\d+)", result.stdout)
    counts = {n: int(m.group(1)) for n, m in
              (("agregados", added), ("eliminados", removed), ("cambiados", changed)) if m}
    total = sum(counts.values())
    if total == 0 and counts:
        return _ok("AIDE: sin cambios respecto a la base de referencia.")
    if not counts:
        return _info("No se pudo interpretar el resumen de AIDE.", result.stdout[-2000:])
    detail = ", ".join(f"{v} {k}" for k, v in counts.items())
    return _warn(f"AIDE detectó cambios: {detail}.", result.stdout[-3000:])


def vulnerabilities_cpu(spec, result):
    vulnerable = []
    for line in result.stdout.splitlines():
        if ":" not in line:
            continue
        path, value = line.split(":", 1)
        name = os.path.basename(path.strip())
        if "vulnerable" in value.lower() and "not affected" not in value.lower():
            vulnerable.append(f"{name}: {value.strip()}")
    if vulnerable:
        return _warn(f"{len(vulnerable)} vulnerabilidad(es) de CPU sin mitigar.", "\n".join(vulnerable))
    return _ok("Todas las vulnerabilidades conocidas de CPU están mitigadas o no aplican.")


def apt_update_check(spec, result):
    problems = _grep(_combined(result), [r"^err:", r"could not", r"failed to fetch", r"error"])
    if problems:
        return _warn(f"{len(problems)} problema(s) al refrescar los repositorios.", _truncate(problems))
    return _ok("Repositorios actualizados sin errores.")


def zombie_procs(spec, result):
    zombies = []
    for line in result.stdout.splitlines()[1:]:
        parts = line.split(None, 10)
        if len(parts) > 7 and parts[7].startswith("Z"):
            zombies.append(line)
    if not zombies:
        return _ok("Sin procesos zombie.")
    return _warn(f"{len(zombies)} proceso(s) zombie.", _truncate(zombies))


def orphan_procs(spec, result):
    orphans = []
    for line in result.stdout.splitlines()[1:]:
        parts = line.split(None, 7)
        if len(parts) > 2 and parts[2] == "1" and parts[1] != "1":
            orphans.append(line)
    return _info(f"{len(orphans)} proceso(s) huérfano(s) (normal, adoptados por init).",
                 _truncate(orphans))


def duplicate_procs(spec, result):
    counter = Counter()
    for line in result.stdout.splitlines()[1:]:
        parts = line.split(None, 10)
        if len(parts) > 10:
            counter[parts[10].split()[0] if parts[10] else parts[10]] += 1
    top = [(cmd, n) for cmd, n in counter.most_common(10) if n > 1]
    if not top:
        return _info("Sin procesos claramente duplicados.")
    detail = "\n".join(f"{n}x  {cmd}" for cmd, n in top)
    return _info(f"{len(top)} comando(s) con múltiples instancias.", detail)


def lsmod_info(spec, result):
    lines = _lines(result.stdout)
    n = max(0, len(lines) - 1)
    return _info(f"{n} módulo(s) del kernel cargados.", _truncate(lines))


def _pci_device_driver_blocks(text, patterns, after):
    """Devuelve [(linea_dispositivo, driver_o_None), ...] para lspci -k."""
    lines = text.splitlines()
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    out = []
    i = 0
    while i < len(lines):
        if any(c.search(lines[i]) for c in compiled):
            block = lines[i:i + 1 + after]
            driver = None
            for l in block[1:]:
                m = re.search(r"Kernel driver in use:\s*(\S+)", l)
                if m:
                    driver = m.group(1)
            out.append((lines[i].strip(), driver))
            i += 1 + after
        else:
            i += 1
    return out


def gpu_driver_check(spec, result):
    devices = _pci_device_driver_blocks(result.stdout, spec.patterns, spec.context_after)
    if not devices:
        return _info("No se detectó una GPU dedicada por este método.")
    no_driver = [d for d, drv in devices if drv is None]
    if no_driver:
        return _warn("Hay una GPU sin driver cargado por el kernel.", "\n".join(no_driver),
                     fix="Revisá si falta instalar el driver propietario o el firmware correspondiente.")
    detail = "\n".join(f"{d} -> driver: {drv}" for d, drv in devices)
    return _info(f"GPU detectada, driver cargado: {devices[0][1]}.", detail)


def pci_driver_check(spec, result):
    devices = _pci_device_driver_blocks(result.stdout, spec.patterns, spec.context_after)
    if not devices:
        return _info("No se detectó el dispositivo por este método.")
    no_driver = [d for d, drv in devices if drv is None]
    if no_driver:
        return _warn("Hay un dispositivo de red sin driver cargado.", "\n".join(no_driver))
    detail = "\n".join(f"{d} -> driver: {drv}" for d, drv in devices)
    return _info(f"Driver cargado: {devices[0][1]}.", detail)


def gl_renderer_check(spec, result):
    text = _combined(result)
    if re.search(r"llvmpipe", text, re.IGNORECASE):
        return _warn("El renderizado 3D va por software (llvmpipe), no por la GPU.", text,
                     fix="Revisá el driver de la GPU; puede que falte el paquete de aceleración correcto.")
    m = re.search(r"OpenGL renderer string:\s*(.+)", text) or re.search(r"^(?:direct rendering|OpenGL).*$",
                                                                          text, re.MULTILINE)
    if m:
        return _ok("Aceleración 3D por hardware activa.", text[:500])
    return _info("No se pudo confirmar el tipo de renderizado.", text[:500])


def rfkill_check(spec, result):
    blocked = _grep(result.stdout, [r"soft blocked:\s*yes", r"hard blocked:\s*yes"], after=0)
    matches = _grep(result.stdout, [r"blocked:\s*yes"])
    if matches:
        return _warn("Hay una interfaz bloqueada (rfkill).", result.stdout,
                     fix="rfkill unblock all   # si el bloqueo no es intencional")
    return _ok("Nada bloqueado por rfkill.")


def dns_check(spec, result):
    low = _combined(result).lower()
    if "connection timed out" in low or "no servers could be reached" in low:
        return _error("No se pudo resolver DNS (sin respuesta del servidor).", result.stdout)
    if "status: noerror" in low:
        return _ok("Resolución DNS funcionando correctamente.")
    if "status: servfail" in low or "status: nxdomain" in low:
        return _warn("El servidor DNS respondió con error.", result.stdout)
    return _info("No se pudo interpretar la respuesta de dig.", result.stdout[:500])


def ping_loss(spec, result):
    text = _combined(result)
    m = re.search(r"(\d+)%\s*packet loss", text)
    if not m:
        if re.search(r"unreachable|unknown host|name or service not known", text, re.IGNORECASE):
            return _error("No hay conectividad hacia el destino de prueba.", text)
        return _info("No se pudo interpretar el resultado del ping.", text)
    pct = int(m.group(1))
    if pct == 100:
        return _error("Sin conectividad: 100% de paquetes perdidos.", text)
    if pct > 0:
        return _warn(f"{pct}% de paquetes perdidos.", text)
    return _ok("Sin pérdida de paquetes.")


def auth_failures(spec, result):
    lines = _lines(result.stdout)
    if not lines:
        return _ok("Sin intentos de login fallidos recientes.")
    if len(lines) > 15:
        return _warn(f"{len(lines)} intentos de login fallidos.", _truncate(lines))
    return _info(f"{len(lines)} intento(s) de login fallido(s).", _truncate(lines))


def battery_health(spec, result):
    text = result.stdout
    m = re.search(r"capacity:\s*(\d+)%", text)
    if not m:
        full = re.search(r"energy-full:\s*([\d.]+)\s*Wh", text)
        design = re.search(r"energy-full-design:\s*([\d.]+)\s*Wh", text)
        if full and design and float(design.group(1)) > 0:
            pct = round(float(full.group(1)) / float(design.group(1)) * 100)
        else:
            return _info("No se pudo determinar el desgaste de la batería.", text[:500])
    else:
        pct = int(m.group(1))
    if pct < 50:
        return _warn(f"La batería perdió más de la mitad de su capacidad original ({pct}%).", text[:500])
    if pct < 70:
        return _info(f"Capacidad de batería al {pct}% de su valor de fábrica.", text[:500])
    return _ok(f"Batería en buen estado ({pct}% de capacidad de fábrica).")


def mdraid_status(spec, result):
    text = result.stdout
    if "Personalities" in text and not re.search(r"^md\d+", text, re.MULTILINE):
        return _ok("No hay arrays RAID por software configurados.")
    if re.search(r"\[[U_]*_[U_]*\]", text) or "degraded" in text.lower():
        return _error("Hay un array RAID degradado.", text,
                       fix="sudo mdadm --detail /dev/mdX   # identificá qué disco falló")
    return _ok("Arrays RAID sincronizados y saludables.", text)


def coredump_list(spec, result):
    lines = _lines(result.stdout)
    data_lines = [l for l in lines if not l.upper().startswith("TIME")]
    if not data_lines:
        return _ok("No hay crashes (coredumps) registrados.")
    return _warn(f"{len(data_lines)} crash(es) registrados.", _truncate(data_lines),
                 fix="coredumpctl info <PID_o_nombre>   # para ver el detalle de uno")


def secure_boot_info(spec, result):
    low = result.stdout.lower()
    if "enabled" in low:
        return _info("Secure Boot: activado.")
    if "disabled" in low:
        return _info("Secure Boot: desactivado.")
    return _info("No se pudo determinar el estado de Secure Boot.", result.stdout)


def tpm_check(spec, result):
    has_tpm = any("tpm" in l.lower() for l in _lines(result.stdout))
    if has_tpm:
        return _info("Hay un chip TPM presente en /dev/.")
    return _info("No se detectó chip TPM.")


def tune2fs_check(spec, result):
    state = re.search(r"Filesystem state:\s*(\S+)", result.stdout)
    if state and state.group(1) != "clean":
        return _warn(f"El filesystem no está marcado como 'clean' (estado: {state.group(1)}).",
                     result.stdout, fix="sudo touch /forcefsck   # y reiniciá para forzar un chequeo")
    keep = _grep(result.stdout, [r"filesystem state", r"last checked", r"mount count"])
    return _ok("El filesystem está marcado como 'clean'.", "\n".join(keep))


def boot_mode_check(spec, result):
    if result.returncode == 0:
        return _info("Arranca en modo UEFI.")
    return _info("Arranca en modo BIOS Legacy.")


def thermal_check(spec, result):
    temps = [float(t) for t in re.findall(r"[+]?(-?\d+(?:\.\d+)?)\s*°C", result.stdout)]
    if not temps:
        return _info("Sin lecturas de temperatura disponibles.", result.stdout)
    worst = max(temps)
    if worst >= 90:
        return _error(f"Temperatura muy alta detectada (~{worst:.0f}°C).", result.stdout)
    if worst >= 80:
        return _warn(f"Temperatura elevada detectada (~{worst:.0f}°C).", result.stdout)
    return _ok(f"Temperaturas normales (máx ~{worst:.0f}°C).", result.stdout)


def load_check(spec, result):
    m = re.search(r"load average:\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)", result.stdout)
    if not m:
        return _info("No se pudo leer el load average.", result.stdout)
    load1 = float(m.group(1))
    cores = os.cpu_count() or 1
    if load1 > cores * 2:
        return _warn(f"Carga alta: {load1} con {cores} núcleo(s) disponibles.", result.stdout)
    return _ok(f"Carga normal: {load1} con {cores} núcleo(s) disponibles.")


def top_procs(spec, result):
    lines = _lines(result.stdout)
    shown = lines[:16]
    return _info(f"{max(0, len(lines)-1)} proceso(s) listados.", "\n".join(shown))


def swap_usage(spec, result):
    lines = _lines(result.stdout)
    if len(lines) <= 1:
        return _info("Sin swap activo.")
    return _info(f"{len(lines)-1} dispositivo(s)/archivo(s) de swap activos.", "\n".join(lines))


def nvme_smart_check(spec, result):
    text = result.stdout
    crit = re.search(r"critical_warning\s*:\s*(0x[0-9a-fA-F]+)", text)
    used = re.search(r"percentage_used\s*:\s*(\d+)", text)
    media_err = re.search(r"media_errors\s*:\s*(\d+)", text)
    problems = []
    if crit and crit.group(1) not in ("0x0", "0x00"):
        problems.append(f"critical_warning = {crit.group(1)}")
    if media_err and int(media_err.group(1)) > 0:
        problems.append(f"media_errors = {media_err.group(1)}")
    if problems:
        return _error("El disco NVMe reporta problemas críticos.", "\n".join(problems) + "\n\n" + text)
    if used and int(used.group(1)) >= 80:
        return _warn(f"El disco NVMe tiene {used.group(1)}% de su vida útil usada.", text)
    return _ok("Salud NVMe correcta (sin errores críticos).", text)


def nvme_errorlog_check(spec, result):
    m = re.search(r"num_entries\s*:\s*(\d+)", result.stdout)
    if m and int(m.group(1)) > 0:
        return _warn(f"El log de errores NVMe tiene {m.group(1)} entrada(s).", result.stdout)
    if not result.stdout.strip():
        return _ok("Log de errores NVMe vacío.")
    return _info("Log de errores NVMe.", result.stdout[:1000])


def time_sync_check(spec, result):
    low = result.stdout.lower()
    if "synchronized: yes" in low or "system clock synchronized: yes" in low:
        return _ok("El reloj del sistema está sincronizado.", result.stdout)
    if "synchronized: no" in low or "system clock synchronized: no" in low:
        return _warn("El reloj del sistema NO está sincronizado.", result.stdout)
    return _info("Estado de sincronización horaria.", result.stdout)


def journal_disk_usage(spec, result):
    m = re.search(r"take up ([\d.]+)\s*([KMGT])", result.stdout, re.IGNORECASE)
    if not m:
        return _info(result.stdout.strip() or "Sin datos.")
    size, unit = float(m.group(1)), m.group(2).upper()
    mb = {"K": size / 1024, "M": size, "G": size * 1024, "T": size * 1024 * 1024}.get(unit, size)
    if mb > 2000:
        return _warn(f"Los logs de journald ocupan {size}{unit} — bastante espacio.", result.stdout,
                     fix="sudo journalctl --vacuum-time=2weeks")
    return _ok(f"Los logs de journald ocupan {size}{unit}.")


def log_sizes(spec, result):
    rows = []
    for line in result.stdout.splitlines():
        parts = line.split(None, 8)
        if len(parts) < 9:
            continue
        try:
            size = int(parts[4])
        except ValueError:
            continue
        rows.append((size, parts[8]))
    if not rows:
        return _info(result.stdout.strip() or "Sin datos.")
    rows.sort(reverse=True)
    top = rows[:10]
    detail = "\n".join(f"{sz:>10} B  {name}" for sz, name in top)
    return _info(f"Archivo más pesado: {top[0][1]} ({top[0][0]} B).", detail)


def boot_time_check(spec, result):
    m = re.search(r"=\s*([\d.]+)s(?:\s*\(kernel\))?.*?=\s*([\d.]+)s", result.stdout, re.DOTALL)
    total = re.search(r"([\d.]+)s\s*$", result.stdout.strip())
    if total:
        secs = float(total.group(1))
        if secs > 60:
            return _warn(f"El arranque total tarda {secs:.1f}s — bastante lento.", result.stdout)
        return _ok(f"Arranque en {secs:.1f}s.", result.stdout)
    return _info(result.stdout.strip())


def boot_blame_check(spec, result):
    lines = _lines(result.stdout)
    if not lines:
        return _info("Sin datos de arranque.")
    m = re.search(r"([\d.]+)(m?s|min)", lines[0])
    detail = _truncate(lines[:20])
    if m:
        val, unit = float(m.group(1)), m.group(2)
        secs = val * 60 if unit == "min" else (val if unit == "s" else val / 1000)
        if secs > 15:
            return _warn(f"'{lines[0].split()[-1] if lines[0].split() else lines[0]}' tarda {lines[0].split()[0]} en iniciar.", detail)
    return _info(f"El más lento: {lines[0]}", detail)


# ─────────────────────────────── registro ───────────────────────────────

PARSERS = {
    "raw_info": raw_info,
    "grep_display": grep_display,
    "keyword_scan": keyword_scan,
    "crash_signals_check": crash_signals_check,
    "head_lines": head_lines,
    "tail_lines": tail_lines,
    "count_lines_info": count_lines_info,
    "count_list_info": count_list_info,
    "timed_run": timed_run,
    "smart_health": smart_health,
    "smart_attrs": smart_attrs,
    "failed_units": failed_units,
    "journal_prev_boot": journal_prev_boot,
    "disk_usage": disk_usage,
    "inode_usage": inode_usage,
    "oom_check": oom_check,
    "security_sysctl": security_sysctl,
    "findmnt_verify": findmnt_verify,
    "broken_symlinks": broken_symlinks,
    "recent_files_check": recent_files_check,
    "rootkit_output": rootkit_output,
    "clamav_check": clamav_check,
    "debsums_check": debsums_check,
    "needrestart_check": needrestart_check,
    "lynis_output": lynis_output,
    "aide_check": aide_check,
    "vulnerabilities_cpu": vulnerabilities_cpu,
    "apt_update_check": apt_update_check,
    "zombie_procs": zombie_procs,
    "orphan_procs": orphan_procs,
    "duplicate_procs": duplicate_procs,
    "lsmod_info": lsmod_info,
    "gpu_driver_check": gpu_driver_check,
    "pci_driver_check": pci_driver_check,
    "gl_renderer_check": gl_renderer_check,
    "rfkill_check": rfkill_check,
    "dns_check": dns_check,
    "ping_loss": ping_loss,
    "auth_failures": auth_failures,
    "battery_health": battery_health,
    "mdraid_status": mdraid_status,
    "coredump_list": coredump_list,
    "secure_boot_info": secure_boot_info,
    "tpm_check": tpm_check,
    "tune2fs_check": tune2fs_check,
    "boot_mode_check": boot_mode_check,
    "thermal_check": thermal_check,
    "load_check": load_check,
    "top_procs": top_procs,
    "swap_usage": swap_usage,
    "nvme_smart_check": nvme_smart_check,
    "nvme_errorlog_check": nvme_errorlog_check,
    "time_sync_check": time_sync_check,
    "journal_disk_usage": journal_disk_usage,
    "log_sizes": log_sizes,
    "boot_time_check": boot_time_check,
    "boot_blame_check": boot_blame_check,
}
