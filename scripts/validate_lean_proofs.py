#!/usr/bin/env python3
"""Check the current kernel dependencies, not historical registry receipts."""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}


def main() -> int:
    declarations: list[str] = []
    for path in sorted((ROOT / "src" / "lean" / "ClosureFrontier").rglob("*.lean")):
        source = path.read_text(encoding="utf-8")
        namespace = "ClosureFrontier" if path.name == "Basic.lean" else "ClosureFrontier.TheoremTrack"
        declarations.extend(
            f"{namespace}.{name}"
            for name in re.findall(
                r"^(?:noncomputable\s+)?(?:theorem|def|abbrev|axiom|opaque)\s+([A-Za-z_][A-Za-z_0-9]*)",
                source, re.MULTILINE,
            )
        )
    if not declarations:
        print("Lean proof validation failed: no declarations found")
        return 1
    audit_source = "import ClosureFrontier\n" + "\n".join(
        f"#print axioms {name}" for name in declarations
    ) + "\n"
    result = subprocess.run(
        ["lake", "env", "lean", "--stdin"], input=audit_source,
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if result.returncode:
        print(result.stdout + result.stderr)
        return result.returncode
    # Lean emits one dependency report for every requested declaration.
    reports = re.findall(
        r"'([^']+)' (?:depends on axioms: \[([^\]]*)\]|does not depend on any axioms)",
        result.stdout,
    )
    reported = {name for name, _ in reports}
    if reported != set(declarations):
        print("Lean proof validation failed: incomplete dependency reports")
        print(result.stdout + result.stderr)
        return 1
    for name, axiom_text in reports:
        axioms = {a.strip() for a in axiom_text.split(",") if a.strip()}
        unexpected = axioms - ALLOWED_AXIOMS
        if unexpected:
            print(f"Lean proof validation failed: {name}: {sorted(unexpected)}")
            return 1
    print(f"Lean proof validation passed: {len(declarations)} declarations; only standard Lean axioms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
