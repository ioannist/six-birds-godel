#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "data" / "schemas" / "pica_mapping_schema.yaml"
VENDOR_ROOT = ROOT / "vendors" / "six-birds-pica"
CLAIMS_PATH = ROOT / "data" / "claims" / "claim_registry.yaml"


class ValidationError(Exception):
    pass


def _load_yaml(path: Path) -> Any:
    if not path.is_file():
        raise ValidationError(f"missing file: {path.relative_to(ROOT)}")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValidationError(f"invalid yaml: {path.relative_to(ROOT)}: {exc}") from exc


def _require(mapping: dict[str, Any], fields: list[str], where: str) -> None:
    missing = [f for f in fields if f not in mapping]
    if missing:
        raise ValidationError(f"{where} missing fields: {', '.join(missing)}")


def main() -> int:
    try:
        schema = _load_yaml(SCHEMA_PATH)
        if not isinstance(schema, dict):
            raise ValidationError("schema must be a mapping")
        _require(schema, ["required_files", "controlled_vocabularies"], "schema")
        required_files = schema["required_files"]
        if not isinstance(required_files, list) or not required_files:
            raise ValidationError("schema.required_files must be a non-empty list")

        vocab = schema["controlled_vocabularies"]
        if not isinstance(vocab, dict):
            raise ValidationError("schema.controlled_vocabularies must be a mapping")
        backing_vocab = vocab.get("empirical_backing")
        if not isinstance(backing_vocab, list) or not backing_vocab:
            raise ValidationError("schema controlled vocab empirical_backing missing")
        allowed_backing = set(backing_vocab)
        figdata_vocab = vocab.get("figdata_relevance")
        if not isinstance(figdata_vocab, list) or not figdata_vocab:
            raise ValidationError("schema controlled vocab figdata_relevance missing")
        allowed_fig_relevance = set(figdata_vocab)

        mapping_docs: dict[str, Any] = {}
        for rel in required_files:
            if not isinstance(rel, str):
                raise ValidationError("schema.required_files entries must be strings")
            path = ROOT / rel
            data = _load_yaml(path)
            if not isinstance(data, dict):
                raise ValidationError(f"{rel} must be a mapping")
            mapping_docs[rel] = data

        claims_data = _load_yaml(CLAIMS_PATH)
        if not isinstance(claims_data, dict):
            raise ValidationError("claim registry must be a mapping")
        entries = claims_data.get("entries")
        if not isinstance(entries, list) or not entries:
            raise ValidationError("claim registry entries missing/empty")
        claim_ids: set[str] = set()
        for idx, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise ValidationError(f"claim entry[{idx}] must be mapping")
            cid = entry.get("id")
            if not isinstance(cid, str):
                raise ValidationError(f"claim entry[{idx}] missing string id")
            if cid in claim_ids:
                raise ValidationError(f"duplicate claim id: {cid}")
            claim_ids.add(cid)
            backing = entry.get("empirical_backing")
            if backing not in allowed_backing:
                raise ValidationError(f"claim {cid} invalid empirical_backing: {backing}")

        # primitives_cells
        primitives = mapping_docs["data/pica_mapping/primitives_cells.yaml"]
        _require(primitives, ["mapping_id", "source_paths", "primitives_bridge", "cells_bridge"], "primitives_cells")
        for name, rel_path in primitives["source_paths"].items():
            if not isinstance(rel_path, str):
                raise ValidationError(f"primitives source path {name} must be string")
            if not (ROOT / rel_path).exists():
                raise ValidationError(f"primitives source path missing: {rel_path}")

        # ledger_surfaces
        ledger = mapping_docs["data/pica_mapping/ledger_surfaces.yaml"]
        _require(ledger, ["mapping_id", "surfaces"], "ledger_surfaces")
        surfaces = ledger["surfaces"]
        if not isinstance(surfaces, list) or not surfaces:
            raise ValidationError("ledger_surfaces.surfaces must be non-empty list")
        surface_ids: set[str] = set()
        for idx, surface in enumerate(surfaces):
            if not isinstance(surface, dict):
                raise ValidationError(f"ledger surface[{idx}] must be mapping")
            _require(
                surface,
                ["id", "logical_name", "source_path", "file_type", "records_parsed", "observed_fields"],
                f"ledger surface[{idx}]",
            )
            sid = surface["id"]
            if sid in surface_ids:
                raise ValidationError(f"duplicate ledger surface id: {sid}")
            surface_ids.add(sid)
            sp = surface["source_path"]
            if not isinstance(sp, str) or not (ROOT / sp).is_file():
                raise ValidationError(f"ledger surface path missing: {sp}")
            fields = surface["observed_fields"]
            if not isinstance(fields, list) or not fields:
                raise ValidationError(f"ledger surface[{idx}] observed_fields must be non-empty list")

        # figdata_surfaces
        fig = mapping_docs["data/pica_mapping/figdata_surfaces.yaml"]
        _require(fig, ["mapping_id", "entries"], "figdata_surfaces")
        entries_fig = fig["entries"]
        if not isinstance(entries_fig, list) or not entries_fig:
            raise ValidationError("figdata_surfaces.entries must be non-empty list")
        fig_ids: set[str] = set()
        for idx, entry in enumerate(entries_fig):
            if not isinstance(entry, dict):
                raise ValidationError(f"figdata entry[{idx}] must be mapping")
            _require(entry, ["id", "file_path", "format", "coarse_category", "relevance"], f"figdata entry[{idx}]")
            fid = entry["id"]
            if fid in fig_ids:
                raise ValidationError(f"duplicate figdata id: {fid}")
            fig_ids.add(fid)
            fp = entry["file_path"]
            if not isinstance(fp, str) or not (ROOT / fp).is_file():
                raise ValidationError(f"figdata path missing: {fp}")
            if entry["relevance"] not in allowed_fig_relevance:
                raise ValidationError(f"figdata entry[{idx}] invalid relevance: {entry['relevance']}")

        # claim_backing
        backing_doc = mapping_docs["data/pica_mapping/claim_backing.yaml"]
        _require(backing_doc, ["mapping_id", "entries"], "claim_backing")
        backing_entries = backing_doc["entries"]
        if not isinstance(backing_entries, list) or not backing_entries:
            raise ValidationError("claim_backing.entries must be non-empty list")
        mapped_claims: set[str] = set()
        for idx, entry in enumerate(backing_entries):
            if not isinstance(entry, dict):
                raise ValidationError(f"claim_backing entry[{idx}] must be mapping")
            _require(entry, ["claim_id", "empirical_backing", "vendor_surfaces", "note"], f"claim_backing entry[{idx}]")
            cid = entry["claim_id"]
            if cid in mapped_claims:
                raise ValidationError(f"duplicate claim_backing claim_id: {cid}")
            mapped_claims.add(cid)
            if cid not in claim_ids:
                raise ValidationError(f"claim_backing references unknown claim_id: {cid}")
            if entry["empirical_backing"] not in allowed_backing:
                raise ValidationError(
                    f"claim_backing entry[{idx}] invalid empirical_backing: {entry['empirical_backing']}"
                )
            surfaces = entry["vendor_surfaces"]
            if not isinstance(surfaces, list):
                raise ValidationError(f"claim_backing entry[{idx}] vendor_surfaces must be list")
            for sp in surfaces:
                if not isinstance(sp, str) or not (ROOT / sp).exists():
                    raise ValidationError(f"claim_backing entry[{idx}] missing vendor surface path: {sp}")

        if mapped_claims != claim_ids:
            missing = sorted(claim_ids - mapped_claims)
            extra = sorted(mapped_claims - claim_ids)
            raise ValidationError(f"claim_backing coverage mismatch; missing={missing}, extra={extra}")

        if not VENDOR_ROOT.is_dir():
            raise ValidationError("vendor root missing: vendors/six-birds-pica")

    except ValidationError as exc:
        print(f"pica mapping validation failed: {exc}")
        return 1

    print("pica mapping validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
