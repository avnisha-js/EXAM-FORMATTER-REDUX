"""Result object shared by the application shell.

Subjects fill this in. It does not describe exam structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OperationResult:
    ok: bool
    message: str
    kind: str = ""
    output_path: str | None = None
    diagnostics: list[str] = field(default_factory=list)

    def display(self) -> str:
        parts = [self.message, *self.diagnostics]
        return "\n".join(part for part in parts if part)
