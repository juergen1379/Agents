"""Ergebnis-Datenmodell der technischen Prüfung."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class Status(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"

    @property
    def rank(self) -> int:
        return {"green": 0, "yellow": 1, "red": 2}[self.value]

    @staticmethod
    def worst(statuses) -> "Status":
        result = Status.GREEN
        for s in statuses:
            if s.rank > result.rank:
                result = s
        return result


@dataclass
class Finding:
    """Eine einzelne Beobachtung. `code` ist stabil und dient später als Schlüssel
    für die laienverständlichen Erklärungen und Lösungsanleitungen im Bericht."""

    code: str
    status: Status
    message: str
    page: int | None = None  # 1-basiert
    data: dict = field(default_factory=dict)


@dataclass
class CheckResult:
    check_id: str
    title: str
    status: Status
    summary: str
    findings: list[Finding] = field(default_factory=list)
    measurements: dict = field(default_factory=dict)


@dataclass
class Report:
    file_name: str
    product_id: str
    product_name: str
    page_count: int
    status: Status
    checks: list[CheckResult]
    engine_version: str

    def to_dict(self) -> dict:
        def convert(obj):
            if isinstance(obj, Enum):
                return obj.value
            if isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [convert(v) for v in obj]
            return obj

        return convert(asdict(self))


def make_result(check_id: str, title: str, findings: list[Finding], ok_summary: str,
                measurements: dict | None = None) -> CheckResult:
    """Fasst Findings zu einem Prüfergebnis zusammen (Status = schlechtestes Finding)."""
    status = Status.worst(f.status for f in findings)
    problems = [f for f in findings if f.status != Status.GREEN]
    if problems:
        worst = max(problems, key=lambda f: f.status.rank)
        summary = worst.message
        if len(problems) > 1:
            summary += f" (+{len(problems) - 1} weitere)"
    else:
        summary = ok_summary
    return CheckResult(check_id, title, status, summary, findings, measurements or {})
