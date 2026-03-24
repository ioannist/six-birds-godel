#!/usr/bin/env python3
"""Build the manuscript PDF and a flattened TeX source into paper/build/."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    paper_dir = repo_root / "paper"
    tex_path = paper_dir / "main.tex"
    out_dir = paper_dir / "build"
    legacy_pdf_path = paper_dir / "main.pdf"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Enforce a single canonical PDF output path. Older build paths wrote
    # paper/main.pdf directly; remove that stale artifact before rebuilding.
    if legacy_pdf_path.exists():
        legacy_pdf_path.unlink()

    latexmk = shutil.which("latexmk")
    pdflatex = shutil.which("pdflatex")

    if latexmk:
        cmd = [
            latexmk,
            "-cd",
            "-pdf",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-output-directory=build",
            str(tex_path),
        ]
        subprocess.run(cmd, check=True, cwd=repo_root)
    elif pdflatex:
        cmd = [
            pdflatex,
            "-interaction=nonstopmode",
            "-halt-on-error",
            f"-output-directory={out_dir}",
            str(tex_path.name),
        ]
        subprocess.run(cmd, check=True, cwd=paper_dir)
        subprocess.run(cmd, check=True, cwd=paper_dir)
    else:
        raise SystemExit("Missing LaTeX tools: latexmk or pdflatex is required.")

    pdf_path = out_dir / "main.pdf"
    if not pdf_path.exists():
        raise SystemExit(f"Build failed: {pdf_path} not found")

    flattener = shutil.which("latexpand") or shutil.which("texflatten")
    if not flattener:
        raise SystemExit(
            "Missing LaTeX flattener: install 'latexpand' (recommended) or 'texflatten'."
        )

    flat_path = out_dir / "main_flattened.tex"
    if Path(flattener).name == "latexpand":
        cmd = [flattener, "-o", str(flat_path), str(tex_path.name)]
        subprocess.run(cmd, check=True, cwd=paper_dir)
    else:
        result = subprocess.run(
            [flattener, str(tex_path.name)],
            check=True,
            cwd=paper_dir,
            text=True,
            stdout=subprocess.PIPE,
        )
        flat_path.write_text(result.stdout, encoding="utf-8")

    if not flat_path.exists():
        raise SystemExit(f"Flattening failed: {flat_path} not found")

    if legacy_pdf_path.exists():
        raise SystemExit(
            f"Legacy PDF output reappeared at {legacy_pdf_path}; canonical output is {pdf_path}"
        )

    print(f"[build_paper] Wrote {pdf_path}")
    print(f"[build_paper] Wrote {flat_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
