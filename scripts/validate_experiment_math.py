#!/usr/bin/env python3
"""Recompute saved arithmetic from shipped measurements, without running experiments."""
from __future__ import annotations

import csv
import gzip
import math
from pathlib import Path
import statistics
import sys

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "python"))
from closure_frontier.confirmatory import confirmatory_readiness


def csv_rows(path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    try:
        with gzip.open(ROOT / "vendors/six-birds-pica/paper/figdata/run_summary_table.csv.gz", "rt", newline="") as handle:
            source = list(csv.DictReader(handle))
        grouped = {}
        for row in source:
            grouped.setdefault((row["config_name"], int(row["n"])), []).append(row)

        def values(config, n, metric):
            out = []
            for row in grouped.get((config, n), []):
                try:
                    value = float(row[metric])
                except (TypeError, ValueError):
                    continue
                if math.isfinite(value):
                    out.append(value)
            return out

        def mean(config, n, metric):
            v = values(config, n, metric)
            return statistics.fmean(v) if v else None

        def close(actual, expected, where):
            if expected is None:
                assert actual == "", where
            else:
                # CSVs publish decimal scores rounded to eight places.
                assert math.isfinite(float(actual)), where
                assert abs(float(actual) - expected) <= 5.01e-9, (where, actual, expected)

        program = csv_rows(ROOT / "results/ticket-p6-1/program_effect_sizes.csv")
        for row in program:
            config, n, metric = row["config_name"], int(row["n"]), row["metric"]
            score, base = mean(config, n, metric), mean("baseline", n, metric)
            close(row["config_mean"], score, (config, n, metric))
            close(row["baseline_mean"], base, (config, n, metric, "baseline"))
            close(row["delta_vs_baseline"], score - base, (config, n, metric, "delta"))
            assert int(row["sample_count"]) == len(values(config, n, metric))

        cells = csv_rows(ROOT / "results/ticket-p6-1/cell_effect_sizes.csv")
        for row in cells:
            config, n, metric = row["loo_config"], int(row["n"]), row["metric"]
            score = mean(config, n, metric)
            full, base = mean("full_all", n, metric), mean("baseline", n, metric)
            close(row["loo_mean"], score, (config, n, metric))
            close(row["delta_vs_full_all"], None if full is None else score - full, (config, n, metric, "ablation"))
            close(row["delta_vs_baseline"], None if base is None else score - base, (config, n, metric, "baseline"))
            assert int(row["sample_count"]) == len(values(config, n, metric))

        atlas = yaml.safe_load((ROOT / "data/pica_atlas/program_atlas.yaml").read_text())
        members = {entry["label"]: set(entry["member_cells"]) for entry in atlas["entries"]}
        interactions = csv_rows(ROOT / "results/ticket-p6-1/interaction_delta_table.csv")
        for row in interactions:
            assert row["comparison_scope"] == "nearest_nonempty_shipped_strict_subprogram"
            assert row["best_comparison_scope"] == "all_measured_shipped_strict_subprograms_including_empty"
            config, n = row["config_name"], int(row["n"])
            score, base = mean(config, n, "frob_from_rank1"), mean("baseline", n, "frob_from_rank1")
            proper = [name for name, cells in members.items() if cells < members[config]]
            nonempty = [name for name in proper if members[name]]
            nearest = sorted(nonempty, key=lambda name: (-len(members[name]), name))
            assert row["closest_simpler_config"] == (nearest[0] if nearest else "")
            neighbor = mean(nearest[0], n, "frob_from_rank1") if nearest else None
            close(row["interaction_delta_abs_shift"], None if neighbor is None else
                  abs(score - base) - abs(neighbor - base), (config, n, "nearest gain"))
            measured = [(name, mean(name, n, "frob_from_rank1")) for name in proper]
            available = [(name, value) for name, value in measured if value is not None]
            available.sort(key=lambda item: (-abs(item[1] - base), item[0]))
            assert int(row["unmeasured_strict_subprogram_count"]) == len(measured) - len(available)
            assert row["best_absolute_shift_subprogram"] == (available[0][0] if available else "")
            close(row["gain_over_best_absolute_shift"], None if not available else
                  abs(score - base) - abs(available[0][1] - base), (config, n, "best gain"))

        for ticket in ["ticket-p6-4", "ticket-p6-4a", "ticket-p6-4b"]:
            rows = csv_rows(ROOT / "results" / ticket / "confirmatory_results.csv")
            decision = confirmatory_readiness(rows)
            stored = yaml.safe_load((ROOT / "results" / ticket / "readiness_rescore.yaml").read_text())
            for field in ["primary_coverage_complete", "final_verdict", "a14_only_remains_focus"]:
                assert stored[field] == decision[field], (ticket, field)
            if ticket != "ticket-p6-4":
                for row in rows:
                    config, n = row["config"], int(row["scale"])
                    close(row["primary_metric_mean"], mean(config, n, "frob_from_rank1"), (ticket, config, n))

        print(f"Experiment arithmetic validation passed: {len(program)} program rows, "
              f"{len(cells)} ablation rows, {len(interactions)} scoped comparisons; readiness gates recomputed")
    except (AssertionError, KeyError, TypeError, ValueError, OSError) as exc:
        print(f"Experiment arithmetic validation failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
