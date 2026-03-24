#!/usr/bin/env python3
"""Build a minimal arXiv source bundle from the current paper tree.

Default bundle contents:
- paper/main.tex
- paper/main.bbl
- all figure PDFs referenced by main.tex (from flatten manifest)

Optional:
- paper/references.bib (if --include_bib is passed)

Output:
- paper/submission/arxiv_source.tar.gz
- paper/submission/arxiv_source_manifest.txt
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", default="paper/figdata/T24_flatten_manifest.json")
    p.add_argument("--main_tex", default="paper/main.tex")
    p.add_argument("--main_bbl", default="paper/main.bbl")
    p.add_argument("--bib", default="paper/references.bib")
    p.add_argument(
        "--include_bib",
        action="store_true",
        help="Include references.bib in bundle (default: false; main.bbl only).",
    )
    p.add_argument("--outdir", default="paper/submission")
    p.add_argument("--bundle_name", default="arxiv_source.tar.gz")
    p.add_argument("--bundle_root", default="arxiv_source")
    p.add_argument("--verify_compile", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing flatten manifest: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fig_entries = manifest.get("figures", [])
    missing_assets = manifest.get("missing_assets", [])
    if missing_assets:
        raise RuntimeError(f"Flatten manifest has missing assets: {missing_assets}")

    required = [Path(args.main_tex), Path(args.main_bbl)]
    if args.include_bib:
        required.append(Path(args.bib))
    for req in required:
        if not req.exists():
            raise FileNotFoundError(f"Missing required file: {req}")

    files_to_copy: list[Path] = required.copy()
    for entry in fig_entries:
        if entry.get("exists"):
            p = Path(entry["resolved_path"])
            if not p.exists():
                raise FileNotFoundError(f"Missing figure asset on disk: {p}")
            files_to_copy.append(p)

    # Deduplicate while preserving order.
    deduped: list[Path] = []
    seen = set()
    for p in files_to_copy:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            deduped.append(p)
    files_to_copy = deduped

    bundle_root = outdir / args.bundle_root
    if bundle_root.exists():
        shutil.rmtree(bundle_root)
    bundle_root.mkdir(parents=True, exist_ok=True)
    (bundle_root / "fig").mkdir(parents=True, exist_ok=True)

    # Copy core files into bundle root.
    shutil.copy2(args.main_tex, bundle_root / "main.tex")
    shutil.copy2(args.main_bbl, bundle_root / "main.bbl")
    if args.include_bib:
        shutil.copy2(args.bib, bundle_root / "references.bib")

    # Copy figures into bundle_root/fig preserving only basenames.
    copied_figure_paths: list[Path] = []
    for p in files_to_copy:
        if p.name in {"main.tex", "main.bbl", "references.bib"}:
            continue
        dst = bundle_root / "fig" / p.name
        shutil.copy2(p, dst)
        copied_figure_paths.append(dst)

    # Manifest with hashes/sizes.
    manifest_out = outdir / "arxiv_source_manifest.txt"
    lines = []
    bundle_files = [
        bundle_root / "main.tex",
        bundle_root / "main.bbl",
        *sorted(copied_figure_paths),
    ]
    if args.include_bib:
        bundle_files.insert(2, bundle_root / "references.bib")
    for f in bundle_files:
        rel = f.relative_to(outdir)
        lines.append(f"{rel} | {f.stat().st_size} bytes | sha256={sha256(f)}")
    manifest_out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    tar_path = outdir / args.bundle_name
    if tar_path.exists():
        tar_path.unlink()
    with tarfile.open(tar_path, "w:gz") as tar:
        for f in bundle_files:
            tar.add(f, arcname=str(f.relative_to(bundle_root)))

    if args.verify_compile:
        cmd = ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", "main.tex"]
        proc = subprocess.run(cmd, cwd=bundle_root, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(
                "Bundle compile check failed:\n"
                f"returncode={proc.returncode}\n"
                f"stdout:\n{proc.stdout}\n"
                f"stderr:\n{proc.stderr}"
            )

    print(f"bundle: {tar_path}")
    print(f"bundle_root: {bundle_root}")
    print(f"manifest: {manifest_out}")
    print(f"files: {len(bundle_files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
