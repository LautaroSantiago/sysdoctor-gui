"""
models.py — estructuras de datos compartidas entre commands_db, scanner y analyzer.

Sin dependencias de GTK: este módulo es puro dominio/datos.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional


class Status(Enum):
    """Severidad de un hallazgo. El orden define prioridad en el resumen."""
    ERROR = "error"      # problema confirmado
    WARN = "warn"        # atención / posible problema
    INFO = "info"        # informativo, sin veredicto de bueno/malo
    OK = "ok"            # chequeo con veredicto explícito y todo bien
    SKIP = "skip"        # no se pudo o no correspondía correr el chequeo

    @property
    def label(self) -> str:
        return {
            Status.ERROR: "Error",
            Status.WARN: "Advertencia",
            Status.INFO: "Info",
            Status.OK: "OK",
            Status.SKIP: "Omitido",
        }[self]

    @property
    def sort_rank(self) -> int:
        # Menor = más urgente. Usado para ordenar el resumen de errores.
        return {
            Status.ERROR: 0,
            Status.WARN: 1,
            Status.INFO: 2,
            Status.OK: 3,
            Status.SKIP: 4,
        }[self]


@dataclass
class CommandSpec:
    """Definición estática de un chequeo del sistema (una entrada de commands_db)."""
    id: str
    category: str                       # id de categoría (ver commands_db.CATEGORIES)
    title: str                          # descripción corta (la que iba como comentario en el doc original)
    cmd: List[str]                      # argv, SIN shell — placeholders tipo {disk} se resuelven en runtime
    needs_sudo: bool = False
    needs_bin: Optional[List[str]] = None   # binarios que deben existir (any-of); si ninguno está, se omite
    parser: str = "raw_info"            # key en analyzer.PARSERS
    deep: bool = False                  # sólo corre si el usuario activó "chequeos profundos"
    condition: Optional[str] = None     # nombre de una condición dinámica (ver scanner.CONDITIONS)
    timeout: float = 20.0
    note: str = ""                      # texto fijo que se agrega siempre al detalle (contexto extra)
    patterns: Optional[List[str]] = None    # patrones regex que usan los parsers genéricos (grep-like)
    context_after: int = 0                  # líneas de contexto luego del match (equivalente a grep -A)


@dataclass
class CommandResult:
    spec: CommandSpec
    returncode: Optional[int]
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None         # error de ejecución (timeout, binario no encontrado, sin privilegios...)
    duration: float = 0.0


@dataclass
class Finding:
    spec: CommandSpec
    result: Optional[CommandResult]
    status: Status
    summary: str                        # una línea, lo que se ve en el resumen
    detail: str = ""                    # texto largo (líneas relevantes, no todo el output crudo)
    suggested_fix: Optional[str] = None # comando sugerido para el usuario, si aplica
    raw_output: str = ""                # salida cruda completa, colapsada en la UI

    @property
    def category(self) -> str:
        return self.spec.category

    @property
    def title(self) -> str:
        return self.spec.title


@dataclass
class ScanProgress:
    done: int
    total: int
    current_title: str
