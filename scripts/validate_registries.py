#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class RegistrySpec:
    name: str
    path: Path
    schema_path: Path
    prefix: str
    required_entry_fields: tuple[str, ...]
    vocab_fields: tuple[str, ...]


REGISTRY_SPECS: tuple[RegistrySpec, ...] = (
    RegistrySpec(
        name="claims",
        path=ROOT / "data" / "claims" / "claim_registry.yaml",
        schema_path=ROOT / "data" / "schemas" / "claim_registry_schema.yaml",
        prefix="clm_",
        required_entry_fields=(
            "id",
            "title",
            "status",
            "empirical_backing",
            "source_ids",
            "dependencies",
            "risk_level",
            "intended_support_modes",
        ),
        vocab_fields=("status", "risk_level", "intended_support_modes", "empirical_backing"),
    ),
    RegistrySpec(
        name="definitions",
        path=ROOT / "data" / "definitions" / "core_definitions.yaml",
        schema_path=ROOT / "data" / "schemas" / "core_definitions_schema.yaml",
        prefix="def_",
        required_entry_fields=("id", "name", "statement"),
        vocab_fields=(),
    ),
    RegistrySpec(
        name="risks",
        path=ROOT / "data" / "risks" / "risk_register.yaml",
        schema_path=ROOT / "data" / "schemas" / "risk_register_schema.yaml",
        prefix="rsk_",
        required_entry_fields=("id", "title", "status", "level"),
        vocab_fields=("status", "level"),
    ),
    RegistrySpec(
        name="benchmarks",
        path=ROOT / "data" / "benchmarks" / "benchmark_registry.yaml",
        schema_path=ROOT / "data" / "schemas" / "benchmark_registry_schema.yaml",
        prefix="bmk_",
        required_entry_fields=("id", "title", "benchmark_type"),
        vocab_fields=("benchmark_type",),
    ),
    RegistrySpec(
        name="transforms",
        path=ROOT / "data" / "transforms" / "transformation_registry.yaml",
        schema_path=ROOT / "data" / "schemas" / "transformation_registry_schema.yaml",
        prefix="trn_",
        required_entry_fields=("id", "title", "transform_type"),
        vocab_fields=("transform_type",),
    ),
    RegistrySpec(
        name="costs",
        path=ROOT / "data" / "costs" / "cost_registry.yaml",
        schema_path=ROOT / "data" / "schemas" / "cost_registry_schema.yaml",
        prefix="cst_",
        required_entry_fields=("id", "title", "cost_type"),
        vocab_fields=("cost_type",),
    ),
)

REQUIRED_TOP_FIELDS = ("registry_id", "version", "entries")


class ValidationError(Exception):
    pass


def _load_yaml(path: Path) -> Any:
    if not path.is_file():
        raise ValidationError(f"missing file: {path.relative_to(ROOT)}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ValidationError(f"invalid yaml: {path.relative_to(ROOT)}: {exc}") from exc


def _require_fields(record: dict[str, Any], fields: tuple[str, ...], where: str) -> None:
    missing = [field for field in fields if field not in record]
    if missing:
        raise ValidationError(f"{where} missing fields: {', '.join(missing)}")


def _validate_schema(schema_data: Any, spec: RegistrySpec) -> dict[str, set[str]]:
    if not isinstance(schema_data, dict):
        raise ValidationError(f"schema not a mapping: {spec.schema_path.relative_to(ROOT)}")
    _require_fields(
        schema_data,
        ("schema_id", "registry_id", "id_prefix", "required_top_level_fields", "required_entry_fields"),
        f"schema {spec.schema_path.relative_to(ROOT)}",
    )
    if schema_data["id_prefix"] != spec.prefix:
        raise ValidationError(f"schema prefix mismatch for {spec.name}: {schema_data['id_prefix']} != {spec.prefix}")

    vocab_cfg = schema_data.get("controlled_vocabularies", {})
    if vocab_cfg is None:
        vocab_cfg = {}
    if not isinstance(vocab_cfg, dict):
        raise ValidationError(f"schema controlled_vocabularies invalid for {spec.name}")

    vocab_sets: dict[str, set[str]] = {}
    for field, values in vocab_cfg.items():
        if not isinstance(values, list) or not values:
            raise ValidationError(f"schema vocabulary invalid for {spec.name}.{field}")
        vocab_sets[field] = {str(item) for item in values}
    return vocab_sets


def _validate_registry(
    registry_data: Any,
    spec: RegistrySpec,
    vocab_sets: dict[str, set[str]],
    all_ids: set[str],
) -> set[str]:
    if not isinstance(registry_data, dict):
        raise ValidationError(f"registry not a mapping: {spec.path.relative_to(ROOT)}")
    _require_fields(registry_data, REQUIRED_TOP_FIELDS, f"registry {spec.path.relative_to(ROOT)}")

    entries = registry_data["entries"]
    if not isinstance(entries, list):
        raise ValidationError(f"entries must be a list: {spec.path.relative_to(ROOT)}")
    if not entries:
        raise ValidationError(f"entries must be non-empty: {spec.path.relative_to(ROOT)}")

    seen_local: set[str] = set()
    for idx, entry in enumerate(entries):
        location = f"{spec.path.relative_to(ROOT)} entry[{idx}]"
        if not isinstance(entry, dict):
            raise ValidationError(f"{location} must be a mapping")
        _require_fields(entry, spec.required_entry_fields, location)

        entry_id = entry["id"]
        if not isinstance(entry_id, str):
            raise ValidationError(f"{location} id must be a string")
        if not entry_id.startswith(spec.prefix):
            raise ValidationError(f"{location} id prefix mismatch: {entry_id}")
        if entry_id in seen_local:
            raise ValidationError(f"duplicate id in {spec.name}: {entry_id}")
        if entry_id in all_ids:
            raise ValidationError(f"duplicate id across registries: {entry_id}")
        seen_local.add(entry_id)
        all_ids.add(entry_id)

        for field in spec.vocab_fields:
            allowed = vocab_sets.get(field)
            if allowed is None:
                raise ValidationError(f"schema missing vocabulary for {spec.name}.{field}")
            value = entry.get(field)
            if field == "intended_support_modes":
                if not isinstance(value, list) or not value:
                    raise ValidationError(f"{location} intended_support_modes must be a non-empty list")
                bad = [item for item in value if item not in allowed]
                if bad:
                    raise ValidationError(f"{location} invalid intended_support_modes: {bad}")
            else:
                if value not in allowed:
                    raise ValidationError(f"{location} invalid {field}: {value}")

        if spec.name == "claims":
            source_ids = entry.get("source_ids")
            if not isinstance(source_ids, list):
                raise ValidationError(f"{location} source_ids must be a list")
            for source_id in source_ids:
                if not isinstance(source_id, str):
                    raise ValidationError(f"{location} source_id must be string: {source_id}")
            if entry.get("status") == "known_citation_backed" and not source_ids:
                raise ValidationError(f"{location} known_citation_backed claim needs non-empty source_ids")

            deps = entry.get("dependencies")
            if not isinstance(deps, list):
                raise ValidationError(f"{location} dependencies must be a list")
            for dep in deps:
                if not isinstance(dep, str):
                    raise ValidationError(f"{location} dependency must be string: {dep}")

    return seen_local


def main() -> int:
    all_ids: set[str] = set()
    ids_by_registry: dict[str, set[str]] = {}
    claims_dependencies: list[tuple[str, list[str]]] = []

    try:
        for spec in REGISTRY_SPECS:
            schema_data = _load_yaml(spec.schema_path)
            vocab_sets = _validate_schema(schema_data, spec)
            registry_data = _load_yaml(spec.path)
            current_ids = _validate_registry(registry_data, spec, vocab_sets, all_ids)
            ids_by_registry[spec.name] = current_ids
            if spec.name == "claims":
                entries = registry_data["entries"]
                for entry in entries:
                    claims_dependencies.append((entry["id"], entry["dependencies"]))

        for claim_id, dependencies in claims_dependencies:
            for dep in dependencies:
                if dep not in all_ids:
                    raise ValidationError(f"unresolved dependency for {claim_id}: {dep}")

    except ValidationError as exc:
        print(f"registry validation failed: {exc}")
        return 1

    print("registry validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
