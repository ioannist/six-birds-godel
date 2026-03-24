#!/usr/bin/env python3
"""Build a compile-dependency manifest for the single-file manuscript."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


INCLUDE_RE = re.compile(
    r"""\\includegraphics(?:\[[^\]]*\])?\{\s*(?:\\detokenize\{([^}]*)\}|([^}]+))\s*\}"""
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tex", default="paper/main.tex")
    p.add_argument("--fig-dir", default="paper/fig")
    p.add_argument("--bib", default="paper/references.bib")
    p.add_argument("--out", default="paper/figdata/T24_flatten_manifest.json")
    return p.parse_args()


def ordered_unique(items: list[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def resolve_figure(token: str, tex_path: Path, fig_dir: Path) -> tuple[str, bool]:
    token = token.strip()
    candidates = []
    token_path = Path(token)

    # Direct token from manuscript directory.
    candidates.append((tex_path.parent / token_path).resolve())

    # Prefer figure directory resolution for bare tokens.
    if not token_path.suffix:
        candidates.append((fig_dir / token_path).resolve())
        candidates.append((fig_dir / f"{token}.pdf").resolve())
        candidates.append((fig_dir / f"{token}.png").resolve())
    else:
        candidates.append((fig_dir / token_path).resolve())

    for cand in candidates:
        if cand.exists():
            return str(cand.relative_to(Path.cwd())), True

    # Deterministic unresolved path default.
    fallback = (fig_dir / (f"{token}.pdf" if not token_path.suffix else token)).resolve()
    return str(fallback.relative_to(Path.cwd())), False


def main() -> int:
    args = parse_args()
    tex_path = Path(args.tex).resolve()
    fig_dir = Path(args.fig_dir).resolve()
    bib_path = Path(args.bib).resolve()
    out_path = Path(args.out).resolve()

    tex = tex_path.read_text(encoding="utf-8")
    raw_tokens: list[str] = []
    for m in INCLUDE_RE.finditer(tex):
        token = m.group(1) if m.group(1) is not None else m.group(2)
        raw_tokens.append(token.strip())
    tokens = ordered_unique(raw_tokens)

    figures = []
    missing_assets: list[str] = []
    for token in tokens:
        resolved_path, exists = resolve_figure(token, tex_path, fig_dir)
        row = {"token": token, "resolved_path": resolved_path, "exists": exists}
        figures.append(row)
        if not exists:
            missing_assets.append(token)

    out = {
        "tex_file": str(tex_path.relative_to(Path.cwd())),
        "bib_file": str(bib_path.relative_to(Path.cwd())),
        "bib_exists": bib_path.exists(),
        "n_figures_total": len(figures),
        "figures": figures,
        "missing_assets": missing_assets,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote={out_path.relative_to(Path.cwd())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

