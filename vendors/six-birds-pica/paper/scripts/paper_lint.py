#!/usr/bin/env python3
"""Paper lint for T24 consistency checks.

Runs compile checks, crossref/citation/asset/notation audits, unicode scan,
and placeholder classification. Writes JSON + text reports under paper/figdata.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Paths:
    repo: Path
    paper: Path
    tex: Path
    bib: Path
    log: Path
    fig_dir: Path
    out_json: Path
    out_txt: Path


def build_paths() -> Paths:
    repo = Path(__file__).resolve().parents[2]
    paper = repo / "paper"
    return Paths(
        repo=repo,
        paper=paper,
        tex=paper / "main.tex",
        bib=paper / "references.bib",
        log=paper / "main.log",
        fig_dir=paper / "fig",
        out_json=paper / "figdata" / "T24_paper_lint_report.json",
        out_txt=paper / "figdata" / "T24_paper_lint_report.txt",
    )


def run_compile(paths: Paths) -> tuple[int, str]:
    proc = subprocess.run(
        ["make", "-C", str(paths.paper), "pdf"],
        cwd=paths.repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout


def count_log_warnings(log_text: str) -> dict[str, int]:
    return {
        "undefined_citations_count": len(re.findall(r"Citation .* undefined", log_text)),
        "undefined_references_count": len(re.findall(r"Reference .* undefined", log_text)),
        "there_were_undefined_references_count": len(
            re.findall(r"There were undefined references", log_text)
        ),
    }


def line_number_from_pos(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def extract_labels_refs(text: str) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    labels = re.findall(r"\\label\{([^}]+)\}", text)

    ref_targets: list[str] = []
    for m in re.finditer(r"\\(?:ref|cref|Cref)\{([^}]+)\}", text):
        for t in m.group(1).split(","):
            t = t.strip()
            if t:
                ref_targets.append(t)

    label_counts = Counter(labels)
    dup_labels = sorted([k for k, v in label_counts.items() if v > 1])

    missing_ref_targets = sorted(set(ref_targets) - set(labels))
    unused_labels = sorted(set(labels) - set(ref_targets))
    return labels, ref_targets, missing_ref_targets, unused_labels, dup_labels


def extract_cite_keys(text: str) -> list[str]:
    keys: list[str] = []
    cite_pat = re.compile(r"\\cite[a-zA-Z*]*\s*(?:\[[^\]]*\]\s*)?\{([^}]*)\}")
    for m in cite_pat.finditer(text):
        for k in m.group(1).split(","):
            k = k.strip()
            if k:
                keys.append(k)
    return keys


def extract_bib_keys(bib_text: str) -> list[str]:
    return re.findall(r"@\w+\{([^,]+),", bib_text)


def extract_includegraphics(text: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    detok = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{\s*\\detokenize\{([^}]*)\}\s*\}")
    plain = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{\s*(?!\\detokenize\{)([^}]*)\s*\}")

    for pat in (detok, plain):
        for m in pat.finditer(text):
            token = m.group(1).strip()
            if not token:
                continue
            results.append(
                {
                    "token": token,
                    "line": line_number_from_pos(text, m.start()),
                }
            )
    return results


def resolve_graphic_token(paths: Paths, token: str) -> Path | None:
    token = token.strip()
    if not token:
        return None

    ext = Path(token).suffix.lower()
    exts = [""] if ext else [".pdf", ".png"]

    candidates: list[Path] = []
    for suf in exts:
        t = token + suf
        candidates.extend(
            [
                paths.paper / t,
                paths.fig_dir / t,
                paths.repo / t,
            ]
        )

    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


def find_substring_hits(lines: list[str], needle: str) -> tuple[int, list[int]]:
    hit_lines = [i for i, line in enumerate(lines, start=1) if needle in line]
    return len(hit_lines), hit_lines


def scan_unicode(lines: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ln, line in enumerate(lines, start=1):
        for idx, ch in enumerate(line):
            if ord(ch) > 127:
                lo = max(0, idx - 20)
                hi = min(len(line), idx + 21)
                out.append(
                    {
                        "char": ch,
                        "codepoint": f"U+{ord(ch):04X}",
                        "line": ln,
                        "context": line[lo:hi],
                    }
                )
    return out


def section_ranges(lines: list[str]) -> dict[str, tuple[int, int]]:
    heads: list[tuple[str, int]] = []
    for i, line in enumerate(lines, start=1):
        m = re.search(r"\\section\*?\{([^}]+)\}", line)
        if m:
            heads.append((m.group(1).strip(), i))

    ranges: dict[str, tuple[int, int]] = {}
    for idx, (name, start) in enumerate(heads):
        end = heads[idx + 1][1] - 1 if idx + 1 < len(heads) else len(lines)
        ranges[name] = (start, end)
    return ranges


def classify_placeholders(lines: list[str]) -> list[dict[str, Any]]:
    tokens = ["TODO", "TBD", "??", "PLACEHOLDER", "FIXME"]
    sec_ranges = section_ranges(lines)
    allowed_sections = {"Funding", "Data availability", "Acknowledgements"}

    out: list[dict[str, Any]] = []

    def in_allowed_section(line_no: int) -> bool:
        for sec in allowed_sections:
            if sec in sec_ranges:
                start, end = sec_ranges[sec]
                if start <= line_no <= end:
                    return True
        return False

    for ln, line in enumerate(lines, start=1):
        for tok in tokens:
            if tok in line:
                cls = "unexpected"
                if tok == "TBD" and "affiliation: TBD" in line:
                    cls = "allowed_placeholder"
                elif in_allowed_section(ln):
                    cls = "allowed_placeholder"
                out.append(
                    {
                        "token": tok,
                        "line": ln,
                        "context": line.strip(),
                        "classification": cls,
                    }
                )
    return out


def build_text_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("T24 Paper Lint Report")
    lines.append("=")
    lines.append(f"compile_exit_code: {report['compile_exit_code']}")
    lines.append(
        f"undefined citations: {report['undefined_citations_count']} | "
        f"undefined references: {report['undefined_references_count']} | "
        f"there-were-undefined-refs: {report['there_were_undefined_references_count']}"
    )
    lines.append("")
    lines.append(
        f"labels={report['labels_count']} refs={report['refs_count']} "
        f"missing_ref_targets={len(report['missing_ref_targets'])} "
        f"duplicate_labels={len(report['duplicate_labels'])}"
    )
    lines.append(
        f"cite_keys={report['cite_keys_count']} missing_bib_keys={len(report['missing_bib_keys'])}"
    )
    lines.append(
        f"includegraphics={report['includegraphics_count']} missing_fig_assets={len(report['missing_fig_assets'])}"
    )
    lines.append("")
    lines.append("Notation hits:")
    for k, v in report["notation_hits"].items():
        lines.append(f"- {k}: count={v['count']} lines={v['lines'][:8]}")
    lines.append("")
    lines.append(f"unicode_chars: {len(report['unicode_chars'])}")
    lines.append(f"placeholders: {len(report['placeholders'])}")
    unexpected = [p for p in report["placeholders"] if p["classification"] != "allowed_placeholder"]
    lines.append(f"unexpected_placeholders: {len(unexpected)}")
    if report["missing_ref_targets"]:
        lines.append(f"missing_ref_targets: {report['missing_ref_targets']}")
    if report["missing_bib_keys"]:
        lines.append(f"missing_bib_keys: {report['missing_bib_keys']}")
    if report["missing_fig_assets"]:
        lines.append("missing_fig_assets:")
        for item in report["missing_fig_assets"]:
            lines.append(f"  - line {item['line']}: {item['token']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    paths = build_paths()

    compile_exit_code, compile_stdout = run_compile(paths)

    tex_text = paths.tex.read_text(encoding="utf-8")
    bib_text = paths.bib.read_text(encoding="utf-8") if paths.bib.exists() else ""
    log_text = paths.log.read_text(encoding="utf-8", errors="replace") if paths.log.exists() else ""
    lines = tex_text.splitlines()

    warn_counts = count_log_warnings(log_text)

    labels, refs, missing_ref_targets, unused_labels, duplicate_labels = extract_labels_refs(tex_text)

    cite_keys = extract_cite_keys(tex_text)
    bib_keys = extract_bib_keys(bib_text)
    cite_set = sorted(set(cite_keys))
    bib_set = sorted(set(bib_keys))

    missing_bib_keys = sorted(set(cite_set) - set(bib_set))
    unused_bib_keys = sorted(set(bib_set) - set(cite_set))

    ig = extract_includegraphics(tex_text)
    missing_fig_assets: list[dict[str, Any]] = []
    resolved_fig_assets: list[dict[str, Any]] = []
    for item in ig:
        resolved = resolve_graphic_token(paths, item["token"])
        if resolved is None:
            missing_fig_assets.append(item)
        else:
            resolved_fig_assets.append({**item, "resolved": str(resolved.relative_to(paths.repo))})

    notation_hits: dict[str, Any] = {}
    for pat in [r"\\sigma_\\pi", "geo\\_", "sigma_pi", "lagr_geo_r2"]:
        count, hit_lines = find_substring_hits(lines, pat)
        notation_hits[pat] = {"count": count, "lines": hit_lines}

    # Symbol occurrence summaries for collision sanity
    _, epat_lines = find_substring_hits(lines, "\\Epat")
    _, etauf_lines = find_substring_hits(lines, "\\Etauf")
    notation_hits["\\Epat_occurrences"] = {
        "count": len(epat_lines),
        "lines": epat_lines,
        "first_3_lines": epat_lines[:3],
    }
    notation_hits["\\Etauf_occurrences"] = {
        "count": len(etauf_lines),
        "lines": etauf_lines,
        "first_3_lines": etauf_lines[:3],
    }

    unicode_chars = scan_unicode(lines)
    placeholders = classify_placeholders(lines)

    report = {
        "compile_exit_code": compile_exit_code,
        "compile_stdout_tail": "\n".join(compile_stdout.splitlines()[-40:]),
        **warn_counts,
        "labels_count": len(labels),
        "refs_count": len(refs),
        "missing_ref_targets": missing_ref_targets,
        "unused_labels": unused_labels,
        "duplicate_labels": duplicate_labels,
        "cite_keys_count": len(cite_set),
        "cite_keys": cite_set,
        "bib_keys_count": len(bib_set),
        "missing_bib_keys": missing_bib_keys,
        "unused_bib_keys": unused_bib_keys,
        "includegraphics_count": len(ig),
        "includegraphics_tokens": ig,
        "resolved_fig_assets": resolved_fig_assets,
        "missing_fig_assets": missing_fig_assets,
        "notation_hits": notation_hits,
        "unicode_chars": unicode_chars,
        "placeholders": placeholders,
    }

    paths.out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths.out_txt.write_text(build_text_report(report), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
