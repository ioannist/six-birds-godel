#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import subprocess
import time
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "python"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from closure_frontier.confirmatory import read_exp112_audit

VENDOR_ROOT = ROOT / "vendors" / "six-birds-pica"
RUN_BASE = VENDOR_ROOT / "lab" / "runs"
STAGE = "ticket_p7_cleanroom_smoke"
RUN_DIR = RUN_BASE / STAGE
RESULTS_DIR = ROOT / "results" / "ticket-p7"

JOBS: list[dict[str, Any]] = [
    {
        "exp": "EXP-112",
        "seed": 0,
        "scale": 64,
        "stage": STAGE,
        "config": "baseline",
        "env": {"SIX_BIRDS_AUDIT_RICH": "1"},
    },
    {
        "exp": "EXP-112",
        "seed": 0,
        "scale": 64,
        "stage": STAGE,
        "config": "A14_only",
        "env": {"SIX_BIRDS_AUDIT_RICH": "1"},
    },
]


def run_cmd(cmd: list[str], cwd: Path) -> tuple[int, str, str, float]:
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr, round(time.time() - t0, 2)


parse_audit_from_log = read_exp112_audit

def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    jobs_path = RESULTS_DIR / "jobs.json"
    jobs_path.write_text(json.dumps(JOBS, indent=2), encoding="utf-8")

    runner_bin = VENDOR_ROOT / "target" / "release" / "runner"
    build_cmd = ["cargo", "build", "--release"]
    build_invoked = False
    build_rc = 0
    build_secs = 0.0
    build_note = "release runner already present"

    if not runner_bin.exists():
        build_invoked = True
        build_note = "release runner missing; built via cargo"
        build_rc, build_out, build_err, build_secs = run_cmd(build_cmd, VENDOR_ROOT)
        (RESULTS_DIR / "build_stdout.log").write_text(build_out, encoding="utf-8")
        (RESULTS_DIR / "build_stderr.log").write_text(build_err, encoding="utf-8")
        if build_rc != 0:
            manifest = {
                "ticket": "P7",
                "status": "failed",
                "failure_stage": "build",
                "vendor_root": str(VENDOR_ROOT.relative_to(ROOT)),
                "runner_bin": str(runner_bin.relative_to(ROOT)),
                "build_command": " ".join(build_cmd),
                "build_returncode": build_rc,
            }
            (RESULTS_DIR / "smoke_manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
            (RESULTS_DIR / "smoke_summary.json").write_text(json.dumps({"status": "failed", "reason": "build_failed"}, indent=2), encoding="utf-8")
            (RESULTS_DIR / "tiny_audit.csv").write_text(
                "config,scale,seed,status,has_audit,log_path,frob_from_rank1,macro_gap,tau,k_values\n", encoding="utf-8"
            )
            (RESULTS_DIR / "runtime_notes.md").write_text(
                "# Ticket P7 Runtime Notes\n\n- build failed\n", encoding="utf-8"
            )
            return 1

    run_cmdline = [
        "python",
        "analysis/run_batch.py",
        "run",
        "--jobs",
        str(jobs_path),
        "--parallelism",
        "2",
        "--timeout",
        "3600",
        "--output-dir",
        str(RUN_BASE),
        "--binary",
        str(runner_bin),
    ]

    run_rc, run_out, run_err, run_secs = run_cmd(run_cmdline, VENDOR_ROOT)
    (RESULTS_DIR / "run_stdout.log").write_text(run_out, encoding="utf-8")
    (RESULTS_DIR / "run_stderr.log").write_text(run_err, encoding="utf-8")

    stage_status_path = RUN_DIR / "stage_status.json"
    stage_status: dict[str, Any] = {}
    if stage_status_path.exists():
        stage_status = json.loads(stage_status_path.read_text(encoding="utf-8"))

    jobs = stage_status.get("jobs", [])
    audit_rows: list[dict[str, Any]] = []
    artifact_index: list[dict[str, Any]] = []

    for job in jobs:
        log_path = Path(job.get("log_path", ""))
        log_abs = log_path if log_path.is_absolute() else (VENDOR_ROOT / log_path)
        audit = parse_audit_from_log(log_abs) if log_abs.exists() else None
        k_values = []
        if isinstance(audit, dict):
            for item in audit.get("multi_scale_scan", []):
                if isinstance(item, dict) and "k" in item:
                    k_values.append(item["k"])

        row = {
            "config": job.get("config", ""),
            "scale": job.get("scale", ""),
            "seed": job.get("seed", ""),
            "status": job.get("status", ""),
            "has_audit": isinstance(audit, dict),
            "log_path": str(log_abs.relative_to(ROOT)) if log_abs.exists() else str(log_path),
            "frob_from_rank1": "" if not isinstance(audit, dict) else audit.get("frob_from_rank1", ""),
            "macro_gap": "" if not isinstance(audit, dict) else audit.get("macro_gap", ""),
            "tau": "" if not isinstance(audit, dict) else audit.get("tau", ""),
            "k_values": "|".join(str(k) for k in k_values),
        }
        audit_rows.append(row)

        artifact_index.append(
            {
                "config": job.get("config", ""),
                "scale": job.get("scale", ""),
                "seed": job.get("seed", ""),
                "status": job.get("status", ""),
                "log_path": row["log_path"],
            }
        )

    csv_path = RESULTS_DIR / "tiny_audit.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        fields = [
            "config",
            "scale",
            "seed",
            "status",
            "has_audit",
            "log_path",
            "frob_from_rank1",
            "macro_gap",
            "tau",
            "k_values",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in audit_rows:
            writer.writerow(row)

    expected = {(job["config"], job["scale"], job["seed"]) for job in JOBS}
    observed = {(row["config"], row["scale"], row["seed"]) for row in audit_rows}
    success = (run_rc == 0 and stage_status.get("n_ok", 0) == len(JOBS)
               and len(audit_rows) == len(JOBS) and observed == expected
               and all(row["has_audit"] and row["status"] == "ok" for row in audit_rows))
    manifest = {
        "ticket": "P7",
        "status": "ok" if success else "failed",
        "vendor_root": str(VENDOR_ROOT.relative_to(ROOT)),
        "runner_bin": str(runner_bin.relative_to(ROOT)),
        "build": {
            "invoked": build_invoked,
            "note": build_note,
            "returncode": build_rc,
            "wall_secs": build_secs,
        },
        "run": {
            "command": " ".join(run_cmdline),
            "returncode": run_rc,
            "wall_secs": run_secs,
            "run_stage": STAGE,
            "run_dir": str(RUN_DIR.relative_to(ROOT)),
            "jobs_path": str(jobs_path.relative_to(ROOT)),
        },
        "jobs": JOBS,
    }
    (RESULTS_DIR / "smoke_manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    summary = {
        "status": "ok" if success else "failed",
        "n_jobs_expected": len(JOBS),
        "n_ok": stage_status.get("n_ok", 0),
        "n_failed": stage_status.get("n_failed", 0),
        "n_timeout": stage_status.get("n_timeout", 0),
        "vendor_artifact_stage_path": str(RUN_DIR.relative_to(ROOT)),
        "jobs_with_audit": sum(1 for r in audit_rows if r["has_audit"]),
        "run_returncode": run_rc,
    }
    (RESULTS_DIR / "smoke_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    (RESULTS_DIR / "vendor_artifact_index.yaml").write_text(
        yaml.safe_dump({"stage": STAGE, "artifacts": artifact_index}, sort_keys=False), encoding="utf-8"
    )

    runtime_lines = [
        "# Ticket P7 Runtime Notes",
        "",
        f"- build invoked: {'yes' if build_invoked else 'no'}",
        f"- build return code: {build_rc}",
        f"- run return code: {run_rc}",
        f"- run wall time seconds: {run_secs}",
        f"- jobs ok/failed/timeout: {stage_status.get('n_ok', 0)}/{stage_status.get('n_failed', 0)}/{stage_status.get('n_timeout', 0)}",
        f"- vendor artifact stage path: {RUN_DIR.relative_to(ROOT)}",
    ]
    if run_err.strip():
        runtime_lines.append("- run stderr was non-empty; see results/ticket-p7/run_stderr.log")
    else:
        runtime_lines.append("- no stderr blockers detected")
    (RESULTS_DIR / "runtime_notes.md").write_text("\n".join(runtime_lines) + "\n", encoding="utf-8")

    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
