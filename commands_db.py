"""
commands_db.py — catálogo de chequeos del sistema.

Basado en la guía de diagnóstico de Linux Mint MATE (Partes 1-10 + secciones
adicionales A-AP). Principio de diseño: el escaneo automático es 100% de
lectura — ningún comando de acá instala paquetes, cambia configuración,
crea archivos persistentes ni hace benchmarking/estrés. Eso se ofrece aparte
como acciones explícitas (ver controller.py: instalar herramientas, crear
snapshot de Timeshift), nunca de forma automática.

Los comandos van como argv (sin shell). Los pipes tipo "X | grep Y" del doc
original se resuelven de dos formas:
  - "cat archivo | grep patron"  ->  ["grep", "-i", "patron", "archivo"]
  - "programa | grep/awk ..."    ->  se corre "programa" solo y el filtro
                                      equivalente se aplica en Python
                                      (analyzer.py), vía spec.patterns.
"""
from models import CommandSpec

CATEGORIES = [
    ("hardware", "Hardware"),
    ("kernel", "Kernel"),
    ("drivers", "Drivers y firmware"),
    ("servicios", "Servicios y procesos"),
    ("procesos", "Procesos"),
    ("arranque", "Arranque"),
    ("memoria", "Memoria"),
    ("disco", "Disco y almacenamiento"),
    ("filesystem", "Sistema de archivos"),
    ("logs", "Logs"),
    ("red", "Red"),
    ("seguridad", "Seguridad e integridad"),
    ("escritorio", "Escritorio (MATE)"),
    ("paquetes", "Paquetes"),
    ("rendimiento", "Configuración y rendimiento"),
    ("energia", "Energía"),
    ("tareas", "Tareas programadas"),
    ("usoreal", "Uso real del sistema"),
    ("virtualizacion", "Virtualización"),
]


def C(id, category, title, cmd, sudo=False, bin=None, parser="raw_info",
      deep=False, condition=None, timeout=20.0, note="", patterns=None,
      context_after=0):
    if isinstance(bin, str):
        bin = [bin]
    return CommandSpec(
        id=id, category=category, title=title, cmd=cmd, needs_sudo=sudo,
        needs_bin=bin, parser=parser, deep=deep, condition=condition,
        timeout=timeout, note=note, patterns=patterns,
        context_after=context_after,
    )


COMMANDS = []
A = COMMANDS.append

# ───────────────────────── Parte 1 — Hardware ─────────────────────────

A(C("hw_lscpu", "hardware", "Modelo de CPU, núcleos, hilos, cache, virtualización",
    ["lscpu"], bin="lscpu"))
A(C("hw_cpu_mhz", "hardware", "Frecuencia actual de cada núcleo",
    ["grep", "cpu MHz", "/proc/cpuinfo"]))
A(C("hw_mpstat", "hardware", "Uso de CPU por núcleo (una muestra)",
    ["mpstat", "-P", "ALL", "1", "1"], bin="mpstat"))
A(C("hw_sensors", "hardware", "Temperaturas de CPU y otros sensores",
    ["sensors"], bin="sensors", parser="thermal_check",
    note="Si no muestra nada, corré 'sudo sensors-detect' una vez a mano (es interactivo)."))
A(C("hw_microcode_ver", "hardware", "Versión de microcódigo cargado en el CPU",
    ["grep", "-m1", "microcode", "/proc/cpuinfo"]))
A(C("hw_microcode_dmesg", "hardware", "Confirma actualización de microcódigo al arrancar",
    ["dmesg"], bin="dmesg", sudo=True, parser="grep_display", patterns=[r"microcode"]))
A(C("hw_ram_free", "memoria", "RAM total, usada, libre, cache/buffers",
    ["free", "-h"], bin="free"))
A(C("hw_ram_dmi", "memoria", "Módulos físicos de RAM: slots, velocidad, tipo, fabricante",
    ["dmidecode", "-t", "memory"], sudo=True, bin="dmidecode"))
A(C("hw_vmstat", "memoria", "Estadísticas detalladas de memoria del kernel",
    ["vmstat", "-s"], bin="vmstat"))
A(C("hw_lsblk", "disco", "Discos y particiones con filesystem y UUID",
    ["lsblk", "-f"], bin="lsblk"))
A(C("hw_df", "disco", "Espacio libre/usado por partición montada",
    ["df", "-h"], bin="df", parser="disk_usage"))
A(C("hw_smart_health", "disco", "Salud SMART del disco principal (PASSED/FAILED)",
    ["smartctl", "-H", "{disk_path}"], sudo=True, bin="smartctl",
    parser="smart_health", condition="has_disk"))
A(C("hw_smart_full", "disco", "Atributos SMART completos del disco principal",
    ["smartctl", "-a", "{disk_path}"], sudo=True, bin="smartctl",
    parser="smart_attrs", condition="has_disk"))
A(C("hw_hdparm_speed", "disco", "Velocidad de lectura (cache y directa)",
    ["hdparm", "-Tt", "{disk_path}"], sudo=True, bin="hdparm",
    condition="has_disk", timeout=25))
A(C("hw_lspci_gpu", "hardware", "Tarjeta gráfica detectada y driver cargado",
    ["lspci", "-k"], bin="lspci", parser="gpu_driver_check",
    patterns=[r"vga compatible controller", r"3d controller", r"display controller"],
    context_after=3))
A(C("hw_glxinfo", "hardware", "Aceleración 3D por hardware activa",
    ["glxinfo"], bin="glxinfo", parser="gl_renderer_check"))
A(C("hw_nvidia_smi", "hardware", "Uso y temperatura de GPU NVIDIA (si aplica)",
    ["nvidia-smi"], bin="nvidia-smi"))
A(C("hw_ip_a", "red", "Interfaces de red disponibles e IPs asignadas",
    ["ip", "a"], bin="ip"))
A(C("hw_ip_link", "red", "Estado UP/DOWN y velocidad negociada por interfaz",
    ["ip", "link", "show"], bin="ip", parser="grep_display",
    patterns=[r"state down", r"NO-CARRIER"]))
A(C("hw_ethtool", "red", "Velocidad y duplex de la interfaz ethernet principal",
    ["ethtool", "{iface}"], sudo=True, bin="ethtool", condition="has_iface"))
A(C("hw_ethtool_stats", "red", "Errores/paquetes perdidos en la interfaz principal",
    ["ethtool", "-S", "{iface}"], sudo=True, bin="ethtool", condition="has_iface",
    parser="keyword_scan", patterns=[r"error", r"drop", r"discard"]))
A(C("hw_iwconfig", "red", "Señal, velocidad y driver de la interfaz WiFi",
    ["iwconfig"], bin="iwconfig"))
A(C("hw_lsusb", "hardware", "Dispositivos USB conectados",
    ["lsusb"], bin="lsusb"))
A(C("hw_lspci_net", "red", "Driver cargado para la placa de red",
    ["lspci", "-k"], bin="lspci", parser="pci_driver_check",
    patterns=[r"ethernet controller", r"network controller"], context_after=3))
A(C("hw_dmesg_net", "red", "Eventos de red del kernel desde el último arranque",
    ["dmesg"], bin="dmesg", sudo=True, parser="grep_display",
    patterns=[r"\beth\w*\b", r"\bwlan\w*\b", r"wifi"]))

# ──────────────── Parte 2 — Kernel, Drivers y Firmware ────────────────

A(C("k_uname", "kernel", "Versión de kernel, arquitectura, fecha de compilación",
    ["uname", "-a"]))
A(C("k_cmdline", "kernel", "Parámetros con los que arrancó el kernel",
    ["cat", "/proc/cmdline"]))
A(C("k_lsmod", "kernel", "Módulos del kernel cargados actualmente",
    ["lsmod"], bin="lsmod", parser="lsmod_info"))
A(C("k_kernels_installed", "kernel", "Kernels instalados (candidatos a limpiar si hay varios viejos)",
    ["dpkg", "-l", "linux-image-*"], bin="dpkg"))
A(C("k_dkms", "kernel", "Módulos DKMS compilados fuera del kernel (drivers propietarios)",
    ["dkms", "status"], bin="dkms"))
A(C("k_dmesg_err", "kernel", "Mensajes de error grave del kernel desde el último arranque",
    ["dmesg", "-l", "err,crit,alert,emerg"], bin="dmesg", sudo=True, parser="keyword_scan"))
A(C("k_journal_err", "kernel", "Errores de kernel del arranque actual",
    ["journalctl", "-k", "-p", "err", "-b", "--no-pager"], sudo=True, bin="journalctl",
    parser="keyword_scan"))
A(C("k_journal_err_prev", "arranque", "Errores de kernel del arranque ANTERIOR",
    ["journalctl", "-k", "-p", "err", "-b", "-1", "--no-pager"], sudo=True, bin="journalctl",
    parser="journal_prev_boot"))
A(C("k_apparmor", "seguridad", "Estado de AppArmor: perfiles activos, enforce/complain",
    ["aa-status"], sudo=True, bin="aa-status"))
A(C("k_sysctl_security", "seguridad", "Parámetros de seguridad del kernel (ptrace, kptr, dmesg restrict)",
    ["sysctl", "kernel.kptr_restrict", "kernel.dmesg_restrict", "kernel.yama.ptrace_scope"],
    bin="sysctl", parser="security_sysctl"))

A(C("drv_lspci_all", "drivers", "Todos los dispositivos PCI y el driver que usa cada uno",
    ["lspci", "-k"], bin="lspci"))
A(C("drv_bluetooth", "drivers", "Estado del adaptador Bluetooth",
    ["bluetoothctl", "show"], bin="bluetoothctl", timeout=8))
A(C("drv_rfkill", "drivers", "WiFi/Bluetooth bloqueados por software o hardware",
    ["rfkill", "list"], bin="rfkill", parser="rfkill_check"))
A(C("drv_lsusb_tree", "drivers", "Árbol de dispositivos USB y driver que usa cada uno",
    ["lsusb", "-t"], bin="lsusb"))
A(C("drv_printers", "drivers", "Impresoras configuradas y predeterminada",
    ["lpstat", "-p", "-d"], bin="lpstat"))
A(C("drv_printers_avail", "drivers", "Dispositivos/drivers de impresión disponibles para CUPS",
    ["lpinfo", "-v"], bin="lpinfo"))

A(C("fw_bios", "drivers", "Versión y fecha de la BIOS/UEFI, fabricante",
    ["dmidecode", "-t", "bios"], sudo=True, bin="dmidecode"))
A(C("fw_boot_mode", "drivers", "Modo de arranque: UEFI o BIOS Legacy",
    ["test", "-d", "/sys/firmware/efi"], parser="boot_mode_check"))
A(C("fw_fwupd", "drivers", "Dispositivos con firmware actualizable (BIOS, SSD, etc.)",
    ["fwupdmgr", "get-devices"], bin="fwupdmgr", timeout=15))

# ──────────── Parte 3 — Servicios (systemd), Procesos y Arranque ────────────

A(C("svc_running", "servicios", "Servicios systemd activos en este momento",
    ["systemctl", "list-units", "--type=service", "--state=running", "--no-legend", "--plain"],
    bin="systemctl"))
A(C("svc_failed", "servicios", "Servicios que fallaron al iniciar",
    ["systemctl", "list-units", "--type=service", "--state=failed", "--no-legend", "--plain"],
    bin="systemctl", parser="failed_units"))
A(C("svc_blame", "arranque", "Servicios ordenados de más lento a más rápido en el arranque",
    ["systemd-analyze", "blame"], bin="systemd-analyze", parser="boot_blame_check"))
A(C("svc_critical_chain", "arranque", "Cadena de dependencias que más tiempo consumió al bootear",
    ["systemd-analyze", "critical-chain"], bin="systemd-analyze"))
A(C("svc_enabled", "servicios", "Todo lo que arranca automáticamente con el sistema",
    ["systemctl", "list-unit-files", "--state=enabled", "--no-legend"], bin="systemctl"))
A(C("svc_deps_graphical", "servicios", "Árbol de dependencias hasta el entorno gráfico",
    ["systemctl", "list-dependencies", "graphical.target"], bin="systemctl"))

A(C("proc_top_cpu", "procesos", "Top procesos que más CPU están usando",
    ["ps", "aux", "--sort=-%cpu"], parser="top_procs"))
A(C("proc_top_mem", "procesos", "Top procesos que más RAM están usando",
    ["ps", "aux", "--sort=-%mem"], parser="top_procs"))
A(C("proc_zombies", "procesos", "Procesos zombies (deberían ser muy pocos o ninguno)",
    ["ps", "aux"], parser="zombie_procs"))
A(C("proc_orphans", "procesos", "Procesos huérfanos (adoptados por init/systemd)",
    ["ps", "-ef"], parser="orphan_procs"))
A(C("proc_duplicates", "procesos", "Comandos repetidos (posibles instancias duplicadas o colgadas)",
    ["ps", "aux"], parser="duplicate_procs"))
A(C("proc_pidstat", "procesos", "Uso de CPU por proceso (5 muestras)",
    ["pidstat", "1", "5"], bin="pidstat", timeout=12))

A(C("boot_analyze", "arranque", "Tiempo total de arranque: firmware, GRUB, kernel, espacio de usuario",
    ["systemd-analyze"], bin="systemd-analyze", parser="boot_time_check"))
A(C("boot_grub_entries", "arranque", "Entradas de arranque que ofrece GRUB",
    ["grep", "-i", "menuentry", "/boot/grub/grub.cfg"]))

# ──────── Parte 4 — Memoria, Disco (a fondo) y Sistema de archivos ────────

A(C("mem_meminfo", "memoria", "Desglose completo de memoria (cache, dirty pages, slab)",
    ["cat", "/proc/meminfo"]))
A(C("mem_smem", "memoria", "Uso de memoria por proceso incluyendo memoria compartida",
    ["smem", "-t", "-k"], bin="smem"))
A(C("mem_swappiness", "memoria", "Qué tan agresivo es el sistema para usar swap",
    ["cat", "/proc/sys/vm/swappiness"]))
A(C("mem_swapon", "memoria", "Particiones/archivos swap activos y uso",
    ["swapon", "--show"], bin="swapon", parser="swap_usage"))
A(C("mem_oom", "memoria", "Si el OOM Killer mató algún proceso por falta de RAM",
    ["dmesg"], bin="dmesg", sudo=True, parser="oom_check"))
A(C("mem_ipcs", "memoria", "Segmentos de memoria compartida activos entre procesos",
    ["ipcs", "-m"], bin="ipcs"))

A(C("disk_fstrim_timer", "disco", "Si el TRIM automático semanal está activo",
    ["systemctl", "status", "fstrim.timer"], bin="systemctl"))
A(C("disk_iostat", "disco", "Uso de I/O por disco (5 muestras)",
    ["iostat", "-x", "1", "5"], bin="iostat", timeout=12))
A(C("disk_iotop", "disco", "Qué procesos generan I/O en disco ahora mismo",
    ["iotop", "-b", "-n", "1", "-o"], sudo=True, bin="iotop", timeout=10))
A(C("disk_inodes", "disco", "Uso de inodos por partición",
    ["df", "-i"], bin="df", parser="inode_usage"))
A(C("disk_hdparm_caps", "disco", "Soporte de NCQ y otras capacidades del disco",
    ["hdparm", "-I", "{disk_path}"], sudo=True, bin="hdparm", condition="has_disk",
    parser="grep_display", patterns=[r"queue depth", r"nominal"]))
A(C("disk_scheduler", "disco", "Scheduler de I/O activo para el disco principal",
    ["cat", "/sys/block/{disk_name}/queue/scheduler"], condition="has_disk"))

A(C("fs_dmesg_errors", "filesystem", "Errores de sistema de archivos reportados por el kernel",
    ["dmesg"], bin="dmesg", sudo=True, parser="keyword_scan",
    patterns=[r"(?=.*(ext4|xfs|btrfs))(?=.*(error|corrupt))"]))
A(C("fs_blkid", "filesystem", "UUID y tipo de filesystem de todos los dispositivos",
    ["blkid"], sudo=True, bin="blkid"))
A(C("fs_fstab", "filesystem", "Entradas de montaje automático configuradas",
    ["cat", "/etc/fstab"]))
A(C("fs_findmnt_verify", "filesystem", "Valida que /etc/fstab no tenga errores de configuración",
    ["findmnt", "--verify"], bin="findmnt", parser="findmnt_verify"))
A(C("fs_broken_symlinks", "filesystem", "Enlaces simbólicos rotos en el sistema",
    ["find", "/", "-xdev", "-type", "l", "-print"], parser="broken_symlinks",
    deep=True, timeout=90))
A(C("fs_suid", "filesystem", "Binarios con permiso SUID activo",
    ["find", "/", "-xdev", "-perm", "-4000", "-type", "f"], sudo=True,
    parser="count_list_info", timeout=60))
A(C("fs_sgid", "filesystem", "Binarios con permiso SGID activo",
    ["find", "/", "-xdev", "-perm", "-2000", "-type", "f"], sudo=True,
    parser="count_list_info", timeout=60))

# ───────────────────────────── Parte 5 — Logs ─────────────────────────────

A(C("log_journal_err", "logs", "Errores de todos los servicios en el arranque actual",
    ["journalctl", "-p", "err", "-b", "--no-pager"], sudo=True, bin="journalctl",
    parser="keyword_scan"))
A(C("log_journal_warn", "logs", "Warnings de todos los servicios en el arranque actual",
    ["journalctl", "-p", "warning", "-b", "--no-pager"], sudo=True, bin="journalctl",
    parser="keyword_scan"))
A(C("log_journal_err_prev_all", "logs", "Errores de todos los servicios en el arranque ANTERIOR",
    ["journalctl", "-p", "err", "-b", "-1", "--no-pager"], sudo=True, bin="journalctl",
    parser="journal_prev_boot"))
A(C("log_journal_since", "logs", "Todo lo registrado en la última hora",
    ["journalctl", "--since", "1 hour ago", "--no-pager"], sudo=True, bin="journalctl",
    parser="tail_lines", timeout=15))
A(C("log_journal_disk", "logs", "Espacio que ocupan los logs guardados",
    ["journalctl", "--disk-usage"], sudo=True, bin="journalctl", parser="journal_disk_usage"))

A(C("log_dmesg_efw", "logs", "dmesg: errores, fallos y warnings",
    ["dmesg", "-T"], bin="dmesg", sudo=True, parser="keyword_scan",
    patterns=[r"\berror\b", r"\bfail\b", r"\bwarn"]))
A(C("log_dmesg_usb", "logs", "dmesg: eventos de USB (desconexiones, resets, sobrecorriente)",
    ["dmesg", "-T"], bin="dmesg", sudo=True, parser="keyword_scan",
    patterns=[r"usb.*disconnect", r"usb.*reset", r"over-current"]))
A(C("log_dmesg_crash", "logs", "dmesg: señales de crashes o bugs internos del kernel",
    ["dmesg", "-T"], bin="dmesg", sudo=True, parser="crash_signals_check",
    patterns=[r"segfault", r"\boops\b", r"kernel bug"]))
A(C("log_dmesg_tail", "logs", "Últimos 50 mensajes del kernel",
    ["dmesg", "-T"], bin="dmesg", sudo=True, parser="tail_lines"))

A(C("log_syslog_tail", "logs", "Últimas 100 líneas del log general del sistema",
    ["tail", "-100", "/var/log/syslog"], sudo=True))
A(C("log_syslog_errors", "logs", "Errores recientes filtrados dentro de syslog",
    ["grep", "-iE", "error|fail|critical", "/var/log/syslog"], sudo=True,
    parser="keyword_scan"))
A(C("log_auth_tail", "logs", "Intentos de login, uso de sudo, cambios de usuario recientes",
    ["tail", "-50", "/var/log/auth.log"], sudo=True))
A(C("log_auth_failures", "seguridad", "Intentos de login fallidos",
    ["grep", "-iE", "authentication failure|Failed password", "/var/log/auth.log"],
    sudo=True, parser="auth_failures"))
A(C("log_sudo_history", "seguridad", "Historial reciente de comandos ejecutados con sudo",
    ["grep", "-i", "sudo", "/var/log/auth.log"], sudo=True, parser="tail_lines"))
A(C("log_sizes", "logs", "Los 10 archivos de log más pesados",
    ["ls", "-la", "/var/log/"], parser="log_sizes"))
A(C("log_grep_crashes_all", "logs", "Crashes graves en todos los logs del sistema",
    ["grep", "-riE", "segfault|traceback|panic", "/var/log/"], sudo=True,
    parser="crash_signals_check", timeout=40))

# ─────────────────── Parte 6 — Red y red avanzada ───────────────────

A(C("net_resolv_conf", "red", "Servidores DNS que usa el sistema ahora mismo",
    ["cat", "/etc/resolv.conf"]))
A(C("net_resolvectl", "red", "Estado de resolución DNS por interfaz",
    ["resolvectl", "status"], bin="resolvectl"))
A(C("net_dig", "red", "Tiempo de respuesta y resolución DNS de prueba",
    ["dig", "google.com"], bin="dig", parser="dns_check", timeout=12))
A(C("net_route", "red", "Tabla de rutas: gateway e interfaz de salida",
    ["ip", "route", "show"], bin="ip"))
A(C("net_ping", "red", "Pérdida de paquetes y latencia contra un servidor estable",
    ["ping", "-c", "20", "8.8.8.8"], bin="ping", parser="ping_loss", timeout=30))
A(C("net_mtr", "red", "Traceroute + ping combinados por cada salto de la ruta",
    ["mtr", "-rw", "-c", "10", "8.8.8.8"], bin="mtr", timeout=25))
A(C("net_traceroute", "red", "Ruta que sigue el tráfico hasta salir a internet",
    ["traceroute", "-w", "2", "-q", "1", "-m", "15", "google.com"], bin="traceroute",
    timeout=35))
A(C("net_ss_summary", "red", "Resumen de conexiones activas TCP/UDP",
    ["ss", "-s"], bin="ss"))
A(C("net_ss_ports", "red", "Qué procesos tienen puertos abiertos y en qué protocolo",
    ["ss", "-tulnp"], sudo=True, bin="ss"))
A(C("net_mtu", "red", "MTU configurado en cada interfaz",
    ["ip", "link", "show"], bin="ip", parser="grep_display", patterns=[r"mtu"]))
A(C("net_congestion", "red", "Algoritmo de control de congestión TCP activo",
    ["sysctl", "net.ipv4.tcp_congestion_control"], bin="sysctl"))
A(C("net_buffers", "red", "Tamaño máximo de buffers de red del kernel",
    ["sysctl", "net.core.rmem_max", "net.core.wmem_max"], bin="sysctl"))
A(C("net_ipv6", "red", "Si IPv6 está desactivado a nivel sistema",
    ["sysctl", "net.ipv6.conf.all.disable_ipv6"], bin="sysctl"))
A(C("net_nmcli_status", "red", "Estado de todas las interfaces según NetworkManager",
    ["nmcli", "device", "status"], bin="nmcli"))
A(C("net_nmcli_active", "red", "Detalle de la conexión activa: IP, gateway, DNS",
    ["nmcli", "connection", "show", "--active"], bin="nmcli"))
A(C("net_nethogs", "red", "Qué proceso consume más ancho de banda (muestra de 6s)",
    ["timeout", "6", "nethogs", "-t", "{iface}"], sudo=True, bin="nethogs",
    condition="has_iface", timeout=10, deep=True))
A(C("net_iftop", "red", "Tráfico en vivo por conexión (muestra de 5s)",
    ["iftop", "-t", "-s", "5", "-N", "-n", "-i", "{iface}"], sudo=True, bin="iftop",
    condition="has_iface", timeout=12, deep=True))

# ─────────────── Parte 7 — Seguridad e integridad (+ extras) ───────────────

A(C("sec_ufw_status", "seguridad", "Estado del firewall y reglas activas",
    ["ufw", "status", "verbose"], sudo=True, bin="ufw"))
A(C("sec_fail2ban", "seguridad", "Jails activos de fail2ban y cuántos intentos bloqueó",
    ["fail2ban-client", "status"], sudo=True, bin="fail2ban-client"))
A(C("sec_shell_users", "seguridad", "Usuarios con acceso real a shell",
    ["grep", "-E", "/bin/bash|/bin/sh", "/etc/passwd"]))
A(C("sec_sudo_group", "seguridad", "Quiénes tienen permisos de administrador",
    ["getent", "group", "sudo"], bin="getent"))
A(C("sec_sudoers_d", "seguridad", "Archivos de reglas sudo personalizadas (sólo nombres)",
    ["ls", "-la", "/etc/sudoers.d/"], sudo=True))
A(C("sec_last_logins", "seguridad", "Historial de inicios de sesión con IP/terminal de origen",
    ["last", "-a"], bin="last"))
A(C("sec_lastlog", "seguridad", "Último login de cada usuario del sistema",
    ["lastlog"], bin="lastlog"))
A(C("sec_who", "seguridad", "Quién está logueado ahora mismo",
    ["who"], bin="who"))
A(C("sec_nmap_local", "seguridad", "Puertos abiertos vistos desde afuera (localhost)",
    ["nmap", "-sT", "-O", "localhost"], sudo=True, bin="nmap", timeout=30))

A(C("sec_rkhunter", "seguridad", "Rootkit Hunter: chequeo completo del sistema",
    ["rkhunter", "--check", "--sk"], sudo=True, bin="rkhunter",
    parser="rootkit_output", deep=True, timeout=600))
A(C("sec_chkrootkit", "seguridad", "chkrootkit: segundo motor de detección de rootkits",
    ["chkrootkit"], sudo=True, bin="chkrootkit", parser="rootkit_output",
    deep=True, timeout=180))
A(C("sec_clamscan_home", "seguridad", "ClamAV: escaneo de la carpeta personal en busca de malware",
    ["clamscan", "-r", "-i", "{home}"], bin="clamscan", parser="clamav_check",
    deep=True, timeout=1800,
    note="Puede tardar bastante según el tamaño de tu carpeta personal."))
A(C("sec_lynis", "seguridad", "Auditoría de seguridad completa (índice de hardening)",
    ["lynis", "audit", "system", "--quiet"], sudo=True, bin="lynis",
    parser="lynis_output", deep=True, timeout=400))
A(C("sec_unhide_sys", "seguridad", "Procesos ocultos que no aparecen en 'ps' (técnicas de rootkit)",
    ["unhide", "sys"], sudo=True, bin="unhide", parser="rootkit_output",
    deep=True, timeout=120))
A(C("sec_unhide_tcp", "seguridad", "Puertos TCP ocultos",
    ["unhide-tcp"], sudo=True, bin="unhide-tcp", parser="rootkit_output",
    deep=True, timeout=60))
A(C("sec_auditd_report", "seguridad", "Resumen de eventos auditados por auditd",
    ["aureport", "--summary"], sudo=True, bin="aureport", condition="has_auditd_active"))

A(C("sec_debsums", "seguridad", "Archivos instalados vs checksums originales del paquete",
    ["debsums", "-c"], sudo=True, bin="debsums", parser="debsums_check",
    deep=True, timeout=180))
A(C("sec_recent_files", "seguridad", "Archivos modificados en las últimas 24hs (fuera de logs/tmp)",
    ["find", "/", "-xdev", "-mtime", "-1", "-type", "f"], sudo=True,
    parser="recent_files_check", deep=True, timeout=60))

A(C("sec_cpu_vulns", "seguridad", "Vulnerabilidades conocidas del CPU (Spectre/Meltdown y afines)",
    ["grep", "-r", ".", "/sys/devices/system/cpu/vulnerabilities/"],
    parser="vulnerabilities_cpu"))
A(C("sec_dmesg_mitigations", "seguridad", "Mitigaciones que aplicó el kernel al arrancar",
    ["dmesg"], bin="dmesg", sudo=True, parser="grep_display",
    patterns=[r"spectre", r"meltdown", r"mitigation"]))
A(C("sec_cpu_bugs", "seguridad", "Lista técnica de bugs de hardware detectados en el CPU",
    ["grep", "-m1", "bugs", "/proc/cpuinfo"]))

A(C("sec_secure_boot", "seguridad", "Estado de Secure Boot",
    ["mokutil", "--sb-state"], bin="mokutil", parser="secure_boot_info"))
A(C("sec_luks", "filesystem", "Particiones cifradas con LUKS detectadas",
    ["lsblk", "-f"], bin="lsblk", parser="grep_display", patterns=[r"crypto_luks"]))
A(C("sec_tpm", "seguridad", "Si hay chip TPM disponible para cifrado por hardware",
    ["ls", "/dev/"], parser="tpm_check"))

A(C("sec_systemd_sandboxing", "servicios", "Puntaje de exposición de cada servicio (sandboxing)",
    ["systemd-analyze", "security"], bin="systemd-analyze", timeout=20))

A(C("sec_aide_check", "seguridad", "Compara el estado actual contra la referencia de integridad (AIDE)",
    ["aide", "--check"], sudo=True, bin="aide", parser="aide_check",
    deep=True, timeout=400, condition="has_aide_db",
    note="Sólo corre si ya inicializaste una base AIDE antes (sudo aideinit); esta herramienta no la crea automáticamente."))

# ─────── Parte 8 — Entorno gráfico (MATE), autostart y paquetes ───────

A(C("mate_compositing", "escritorio", "Si el compositor de Marco está activo",
    ["gsettings", "get", "org.mate.Marco.general", "compositing-manager"], bin="gsettings"))
A(C("mate_procs", "escritorio", "Procesos activos del entorno MATE",
    ["ps", "aux"], parser="grep_display", patterns=[r"marco", r"caja", r"mate-panel"]))
A(C("mate_xrandr", "escritorio", "Monitores detectados, resolución y tasa de refresco",
    ["xrandr", "--verbose"], bin="xrandr", parser="grep_display",
    patterns=[r"connected", r" rate\b"]))
A(C("mate_autostart_user", "escritorio", "Programas que arrancan automáticamente para tu usuario",
    ["ls", "{home}/.config/autostart/"]))
A(C("mate_autostart_sys", "escritorio", "Programas que arrancan automáticamente para todos los usuarios",
    ["ls", "/etc/xdg/autostart/"]))
A(C("mate_blame_top", "escritorio", "Qué autostart tarda más en el arranque",
    ["systemd-analyze", "blame"], bin="systemd-analyze", parser="top_procs"))

A(C("pkg_apt_update", "paquetes", "Refresca la lista de paquetes y avisa si algún repo falla",
    ["apt-get", "update"], sudo=True, bin="apt-get", parser="apt_update_check", timeout=60))
A(C("pkg_upgradable", "paquetes", "Paquetes con actualizaciones pendientes",
    ["apt", "list", "--upgradable"], bin="apt", timeout=20))
A(C("pkg_sources", "paquetes", "Repositorio principal configurado (/etc/apt/sources.list)",
    ["cat", "/etc/apt/sources.list"]))
A(C("pkg_sources_d", "paquetes", "PPAs y repositorios adicionales (/etc/apt/sources.list.d/)",
    ["find", "/etc/apt/sources.list.d/", "-name", "*.list", "-exec", "cat", "{}", ";"]))
A(C("pkg_kernels", "paquetes", "Kernels instalados actualmente vs el que estás usando",
    ["dpkg", "-l", "linux-image-*"], bin="dpkg", parser="grep_display", patterns=[r"^ii"]))
A(C("pkg_check", "paquetes", "Consistencia general de dependencias",
    ["apt-get", "check"], sudo=True, bin="apt-get", parser="keyword_scan"))
A(C("pkg_debsecan", "paquetes", "Vulnerabilidades (CVE) conocidas en paquetes instalados",
    ["debsecan"], sudo=True, bin="debsecan", parser="keyword_scan", deep=True, timeout=60))
A(C("pkg_needrestart", "paquetes", "Servicios que siguen corriendo con librerías viejas tras un update",
    ["needrestart", "-b"], sudo=True, bin="needrestart", parser="needrestart_check"))

A(C("pkg_snap_list", "paquetes", "Paquetes snap instalados",
    ["snap", "list"], bin="snap"))
A(C("pkg_snap_changes", "paquetes", "Historial de instalaciones/actualizaciones snap",
    ["snap", "changes"], bin="snap", parser="keyword_scan", patterns=[r"error"]))
A(C("pkg_flatpak_list", "paquetes", "Aplicaciones flatpak instaladas",
    ["flatpak", "list"], bin="flatpak"))
A(C("pkg_flatpak_runtimes", "paquetes", "Runtimes flatpak instalados",
    ["flatpak", "list", "--runtime"], bin="flatpak"))
A(C("pkg_holds", "paquetes", "Paquetes marcados para NO actualizarse nunca",
    ["apt-mark", "showhold"], bin="apt-mark"))

# ─── Parte 9 — Configuración del sistema, Rendimiento y Energía ───

A(C("perf_sysctl_vm", "rendimiento", "Swappiness y presión de cache de archivos",
    ["sysctl", "vm.swappiness", "vm.vfs_cache_pressure"], bin="sysctl"))
A(C("perf_ulimit", "rendimiento", "Límites de recursos para la sesión actual",
    ["cat", "/proc/self/limits"]))
A(C("perf_limits_conf", "rendimiento", "Límites configurados de forma permanente",
    ["cat", "/etc/security/limits.conf"]))
A(C("perf_file_max", "rendimiento", "Máximo de archivos abiertos permitidos a nivel sistema",
    ["sysctl", "fs.file-max"], bin="sysctl"))
A(C("perf_governor", "rendimiento", "Governor de CPU activo en cada núcleo",
    ["find", "/sys/devices/system/cpu", "-path", "*/cpufreq/scaling_governor",
     "-exec", "grep", "-H", ".", "{}", ";"]))
A(C("perf_cpupower", "rendimiento", "Info completa de frecuencias y governor disponibles",
    ["cpupower", "frequency-info"], bin="cpupower"))
A(C("perf_thp", "rendimiento", "Estado de Transparent Huge Pages",
    ["cat", "/sys/kernel/mm/transparent_hugepage/enabled"]))
A(C("perf_zswap", "rendimiento", "Si zswap (compresión de swap en RAM) está activo",
    ["cat", "/sys/module/zswap/parameters/enabled"]))
A(C("perf_zram", "rendimiento", "Dispositivos zram activos y cuánto están comprimiendo",
    ["zramctl"], bin="zramctl"))
A(C("perf_uptime", "rendimiento", "Load average de los últimos 1, 5 y 15 minutos",
    ["uptime"], bin="uptime", parser="load_check"))
A(C("perf_vmstat", "rendimiento", "Contexto de CPU, memoria, I/O y cambios de contexto",
    ["vmstat", "1", "5"], bin="vmstat", timeout=10))
A(C("perf_interrupts", "rendimiento", "Interrupciones (IRQ) por dispositivo y núcleo",
    ["head", "-n", "20", "/proc/interrupts"]))
A(C("perf_pidstat_ctxt", "rendimiento", "Cambios de contexto por proceso",
    ["pidstat", "-w", "1", "5"], bin="pidstat", timeout=12))

A(C("power_tlp", "energia", "Resumen del estado actual de TLP",
    ["tlp-stat", "-s"], sudo=True, bin="tlp-stat"))
A(C("power_cstates", "energia", "C-States disponibles (estados de bajo consumo)",
    ["find", "/sys/devices/system/cpu/cpu0/cpuidle", "-path", "*/name",
     "-exec", "cat", "{}", ";"]))
A(C("power_usb_maxpower", "energia", "Consumo eléctrico declarado por cada dispositivo USB",
    ["lsusb", "-v"], sudo=True, bin="lsusb", timeout=20, parser="grep_display",
    patterns=[r"^bus ", r"^device descriptor", r"maxpower"]))
A(C("power_usb_autosuspend", "energia", "Autosuspend activado por puerto USB",
    ["find", "/sys/bus/usb/devices", "-path", "*/power/control",
     "-exec", "grep", "-H", ".", "{}", ";"]))

# ─────────── Parte 10 — Tareas programadas y Uso real ───────────

A(C("task_crontab_user", "tareas", "Tareas cron programadas para tu usuario",
    ["crontab", "-l"], bin="crontab"))
A(C("task_crontab_root", "tareas", "Tareas cron programadas para root",
    ["crontab", "-l", "-u", "root"], sudo=True, bin="crontab"))
A(C("task_cron_dirs", "tareas", "Tareas cron del sistema organizadas por frecuencia",
    ["ls", "/etc/cron.d/", "/etc/cron.daily/", "/etc/cron.hourly/",
     "/etc/cron.weekly/", "/etc/cron.monthly/"]))
A(C("task_cron_log", "tareas", "Historial de ejecuciones de cron",
    ["grep", "-i", "cron", "/var/log/syslog"], sudo=True, parser="tail_lines"))
A(C("task_timers", "tareas", "Todos los timers systemd programados, con próxima ejecución",
    ["systemctl", "list-timers", "--all", "--no-legend"], bin="systemctl"))

A(C("usoreal_nautilus", "usoreal", "Tiempo que tarda en 'arrancar' Nautilus",
    ["nautilus", "--version"], bin="nautilus", parser="timed_run"))
A(C("usoreal_caja", "usoreal", "Tiempo que tarda en 'arrancar' Caja",
    ["caja", "--version"], bin="caja", parser="timed_run"))
A(C("usoreal_sar_cpu", "usoreal", "Uso de CPU en reposo (10 muestras)",
    ["sar", "-u", "1", "10"], bin="sar", timeout=15))
A(C("usoreal_sar_mem", "usoreal", "Uso de memoria en reposo (10 muestras)",
    ["sar", "-r", "1", "10"], bin="sar", timeout=15))
A(C("usoreal_top_snapshot", "usoreal", "Foto instantánea del sistema: procesos, carga, memoria",
    ["top", "-b", "-n", "1"], bin="top", parser="top_procs"))

# ───────────────────────── Virtualización ─────────────────────────

A(C("virt_flags", "virtualizacion", "Núcleos que soportan virtualización por hardware (VT-x/AMD-V)",
    ["grep", "-cE", "vmx|svm", "/proc/cpuinfo"]))
A(C("virt_kvmok", "virtualizacion", "Si podés usar virtualización acelerada (KVM)",
    ["kvm-ok"], sudo=True, bin="kvm-ok"))
A(C("virt_docker", "virtualizacion", "Contenedores Docker existentes",
    ["docker", "ps", "-a"], bin="docker"))
A(C("virt_lxc", "virtualizacion", "Contenedores LXC existentes",
    ["lxc", "list"], bin="lxc"))

# ───────────────────── Chequeos adicionales (A-AP) ─────────────────────

# Xorg
A(C("x_log_errors", "escritorio", "Errores del servidor gráfico Xorg desde el último arranque",
    ["grep", "-iE", "error|\\(ee\\)|fail", "/var/log/Xorg.0.log"]))
A(C("x_dpyinfo", "escritorio", "Info del servidor de display: resolución, color, extensiones",
    ["xdpyinfo"], bin="xdpyinfo", parser="head_lines"))
A(C("x_monitors", "escritorio", "Monitores detectados y cuál es el primario",
    ["xrandr", "--listmonitors"], bin="xrandr"))
A(C("x_glxinfo_b", "escritorio", "Renderer OpenGL: aceleración por hardware o software",
    ["glxinfo", "-B"], bin="glxinfo", parser="gl_renderer_check"))

# Audio
A(C("audio_aplay", "escritorio", "Tarjetas y dispositivos de audio detectados por ALSA",
    ["aplay", "-l"], bin="aplay"))
A(C("audio_cards", "escritorio", "Lista resumida de tarjetas de sonido",
    ["cat", "/proc/asound/cards"]))
A(C("audio_pactl_info", "escritorio", "Servidor de audio activo, versión, configuración por defecto",
    ["pactl", "info"], bin="pactl"))
A(C("audio_sinks", "escritorio", "Estado y latencia real de cada salida de audio",
    ["pactl", "list", "sinks"], bin="pactl", parser="grep_display",
    patterns=[r"state:", r"latency"]))

# Fuentes
A(C("fonts_count", "escritorio", "Cantidad total de fuentes instaladas",
    ["fc-list"], bin="fc-list", parser="count_lines_info"))
A(C("fonts_match", "escritorio", "Qué fuente real se usa cuando una app pide 'Sans' genérico",
    ["fc-match", "Sans"], bin="fc-match"))

# Locale
A(C("locale_current", "escritorio", "Variables de idioma/región activas en la sesión actual",
    ["locale"], bin="locale"))
A(C("locale_available", "escritorio", "Todos los locales generados y disponibles",
    ["locale", "-a"], bin="locale"))
A(C("locale_env", "escritorio", "Variables de entorno de idioma activas",
    ["printenv", "LANG", "LC_ALL"]))

# GRUB / initramfs
A(C("grub_default", "arranque", "Configuración editable de GRUB (timeout, kernel default)",
    ["cat", "/etc/default/grub"]))
A(C("grub_initramfs", "arranque", "Contenido del initramfs actual",
    ["lsinitramfs", "/boot/initrd.img-{kernel_release}"], bin="lsinitramfs",
    parser="head_lines"))

# Sincronización horaria
A(C("time_status", "red", "Hora actual, zona horaria y si el reloj está sincronizado",
    ["timedatectl", "status"], bin="timedatectl", parser="time_sync_check"))
A(C("time_sync_detail", "red", "Detalle de precisión de la sincronización horaria",
    ["timedatectl", "show-timesync", "--all"], bin="timedatectl"))
A(C("time_chrony", "red", "Precisión del reloj y desvío respecto al servidor NTP",
    ["chronyc", "tracking"], bin="chronyc"))
A(C("time_timesyncd", "red", "Estado del servicio de sincronización horaria",
    ["systemctl", "status", "systemd-timesyncd"], bin="systemctl"))

# NetworkManager - perfiles guardados
A(C("nm_profiles", "red", "Todos los perfiles de conexión guardados (wifi, ethernet, VPN)",
    ["nmcli", "connection", "show"], bin="nmcli"))
A(C("nm_profile_files", "red", "Archivos de configuración de cada conexión guardada",
    ["find", "/etc/NetworkManager/system-connections/", "-type", "f"], sudo=True))

# cgroups
A(C("cgroups_controllers", "servicios", "Controladores de cgroups v2 disponibles",
    ["cat", "/sys/fs/cgroup/cgroup.controllers"]))

# LVM / RAID
A(C("lvm_pvs", "disco", "Volúmenes físicos LVM existentes",
    ["pvs"], sudo=True, bin="pvs"))
A(C("lvm_vgs", "disco", "Grupos de volúmenes LVM existentes",
    ["vgs"], sudo=True, bin="vgs"))
A(C("lvm_lvs", "disco", "Volúmenes lógicos LVM existentes",
    ["lvs"], sudo=True, bin="lvs"))
A(C("raid_mdstat", "disco", "Estado de arrays RAID por software (mdadm)",
    ["cat", "/proc/mdstat"], parser="mdraid_status"))

# SSH server (condicional a que exista sshd_config)
A(C("ssh_config_effective", "red", "Configuración efectiva real del servidor SSH",
    ["sshd", "-T"], sudo=True, bin="sshd", condition="has_sshd_config", parser="head_lines"))
A(C("ssh_config_active", "red", "Configuración activa sin comentarios ni líneas vacías",
    ["grep", "-vE", "^#|^$", "/etc/ssh/sshd_config"], sudo=True,
    condition="has_sshd_config"))
A(C("ssh_listening", "red", "Si el servicio SSH está escuchando y en qué interfaz",
    ["ss", "-tlnp"], sudo=True, bin="ss", condition="has_sshd_config",
    parser="grep_display", patterns=[r":22\b"]))

# NFS/Samba (sólo lo local, sin apuntar a un servidor externo)
A(C("nfs_samba_mounts", "red", "Shares de red (NFS/CIFS) montados actualmente",
    ["grep", "-E", "nfs|cifs", "/proc/mounts"]))

# Batería (condicional)
A(C("bat_upower", "energia", "Capacidad actual vs de fábrica, ciclos, estado de carga",
    ["upower", "-i", "{battery_path}"], bin="upower", condition="has_battery",
    parser="battery_health"))
A(C("bat_acpi", "energia", "Resumen rápido: batería, temperatura, estado de AC",
    ["acpi", "-V"], bin="acpi", condition="has_battery"))
A(C("bat_cycles", "energia", "Cantidad de ciclos de carga completos",
    ["cat", "{battery_sys_path}/cycle_count"], condition="has_battery"))

# udev
A(C("udev_disk_info", "disco", "Cadena de atributos que usa udev para identificar el disco principal",
    ["udevadm", "info", "-a", "-n", "{disk_path}"], bin="udevadm",
    condition="has_disk", parser="tail_lines"))
A(C("udev_rules", "hardware", "Reglas personalizadas de udev",
    ["ls", "/etc/udev/rules.d/"]))

# NVMe (condicional)
A(C("nvme_list", "disco", "Discos NVMe detectados con modelo y firmware",
    ["nvme", "list"], bin="nvme"))
A(C("nvme_smart", "disco", "Salud NVMe: desgaste, temperatura, errores de media",
    ["nvme", "smart-log", "{nvme_dev}"], sudo=True, bin="nvme",
    condition="has_nvme", parser="nvme_smart_check"))
A(C("nvme_errors", "disco", "Log de errores internos del controlador NVMe",
    ["nvme", "error-log", "{nvme_dev}"], sudo=True, bin="nvme",
    condition="has_nvme", parser="nvme_errorlog_check"))

# Cuotas de disco
A(C("quota_user", "disco", "Límites de espacio asignados a tu usuario, si hay cuotas",
    ["quota", "-u", "{username}"], bin="quota"))

# Sesiones / logind
A(C("logind_sessions", "servicios", "Sesiones activas del sistema",
    ["loginctl", "list-sessions"], bin="loginctl"))
A(C("logind_conf", "energia", "Qué pasa al cerrar la tapa o apretar el botón de power",
    ["grep", "-vE", "^#|^$", "/etc/systemd/logind.conf"]))

# Coredumps
A(C("crash_coredumps", "logs", "Crashes registrados con fecha y proceso",
    ["coredumpctl", "list"], bin="coredumpctl", parser="coredump_list"))
A(C("crash_apport", "logs", "Reportes de crash guardados por apport",
    ["ls", "/var/crash/"]))

# Filesystem offline (sólo lectura de metadata, sin fsck real)
A(C("fs_tune2fs", "filesystem", "Info del filesystem: último chequeo, veces montado, errores",
    ["tune2fs", "-l", "{root_partition}"], sudo=True, bin="tune2fs",
    condition="has_root_partition", parser="tune2fs_check"))

# ───────────────────────── Utilidades del catálogo ─────────────────────────

CATEGORY_LABELS = dict(CATEGORIES)
COMMANDS_BY_ID = {c.id: c for c in COMMANDS}


def commands_by_category():
    """Devuelve {category_id: [CommandSpec, ...]} preservando el orden de CATEGORIES."""
    out = {cid: [] for cid, _ in CATEGORIES}
    for c in COMMANDS:
        out.setdefault(c.category, []).append(c)
    return out
