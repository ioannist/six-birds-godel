#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent

CLAIMS_PATH = ROOT / "data" / "claims" / "claim_registry.yaml"
INTERNAL_PATH = ROOT / "data" / "citations" / "internal_relevance.yaml"
EXTERNAL_PATH = ROOT / "data" / "citations" / "external_support.yaml"
INTERNAL_SCHEMA_PATH = ROOT / "data" / "schemas" / "internal_relevance_schema.yaml"
EXTERNAL_SCHEMA_PATH = ROOT / "data" / "schemas" / "external_support_schema.yaml"

REQUIRED_TOP_LEVEL_FIELDS = ("registry_id", "version", "entries")
REQUIRED_INTERNAL_FIELDS = (
    "id",
    "canonical_key",
    "title",
    "claim_links",
    "concepts_to_borrow",
    "likely_necessary",
    "warnings",
)
REQUIRED_EXTERNAL_FIELDS = (
    "id",
    "canonical_key",
    "title",
    "source_cluster",
    "claim_links",
    "support_roles",
)

REQUIRED_INTERNAL_IDS = {
    "src_int_six_birds_foundations",
    "src_int_to_count",
}

ALLOWED_INTERNAL_ENTRIES = {
    "src_int_six_birds_foundations": "Six Birds: Foundations of Emergence Calculus",
    "src_int_to_count": "To Count a Stone with Six Birds: A Mathematics is A Theory",
    "src_int_to_spend": "To Spend a Stone with Six Birds: Currency, Constraint Duality, and Shadow Prices Across Closure Layers",
    "src_int_to_chart": "To Chart a Stone with Six Birds: Emergence Phase Diagrams for Effective Theories in Control Space",
    "src_int_to_create": "To Create a Stone with Six Birds: Emergent Geometric and Thermodynamic Regimes from a Minimal Stochastic Substrate",
}


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


def _normalize_title(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _load_claims() -> tuple[set[str], dict[str, list[str]], set[str]]:
    data = _load_yaml(CLAIMS_PATH)
    if not isinstance(data, dict):
        raise ValidationError("claim registry must be a mapping")
    _require_fields(data, REQUIRED_TOP_LEVEL_FIELDS, "claim registry")

    entries = data["entries"]
    if not isinstance(entries, list) or not entries:
        raise ValidationError("claim registry entries must be a non-empty list")

    claim_ids: set[str] = set()
    claim_sources: dict[str, list[str]] = {}
    known_citation_backed: set[str] = set()

    for idx, entry in enumerate(entries):
        where = f"claim entry[{idx}]"
        if not isinstance(entry, dict):
            raise ValidationError(f"{where} must be a mapping")
        _require_fields(entry, ("id", "status", "source_ids"), where)
        claim_id = entry["id"]
        if not isinstance(claim_id, str) or not claim_id.startswith("clm_"):
            raise ValidationError(f"{where} invalid id: {claim_id}")
        if claim_id in claim_ids:
            raise ValidationError(f"duplicate claim id: {claim_id}")
        claim_ids.add(claim_id)

        source_ids = entry["source_ids"]
        if not isinstance(source_ids, list):
            raise ValidationError(f"{where} source_ids must be a list")
        for source_id in source_ids:
            if not isinstance(source_id, str):
                raise ValidationError(f"{where} source_id must be a string: {source_id}")
        claim_sources[claim_id] = source_ids

        status = entry["status"]
        if status == "known_citation_backed":
            known_citation_backed.add(claim_id)
            if not source_ids:
                raise ValidationError(f"{where} known_citation_backed must have non-empty source_ids")

    return claim_ids, claim_sources, known_citation_backed


def _load_schema_vocab() -> tuple[set[str], set[str]]:
    external_schema = _load_yaml(EXTERNAL_SCHEMA_PATH)
    if not isinstance(external_schema, dict):
        raise ValidationError("external schema must be a mapping")
    _require_fields(
        external_schema,
        ("schema_id", "registry_id", "id_prefix", "required_top_level_fields", "required_entry_fields", "controlled_vocabularies"),
        "external schema",
    )
    vocab = external_schema["controlled_vocabularies"]
    if not isinstance(vocab, dict):
        raise ValidationError("external schema controlled_vocabularies must be a mapping")
    source_cluster_values = vocab.get("source_cluster")
    support_role_values = vocab.get("support_roles")
    if not isinstance(source_cluster_values, list) or not source_cluster_values:
        raise ValidationError("external schema source_cluster vocabulary missing/invalid")
    if not isinstance(support_role_values, list) or not support_role_values:
        raise ValidationError("external schema support_roles vocabulary missing/invalid")
    return set(source_cluster_values), set(support_role_values)


def main() -> int:
    try:
        claim_ids, claim_sources, known_citation_backed = _load_claims()
        allowed_clusters, allowed_roles = _load_schema_vocab()

        internal_schema = _load_yaml(INTERNAL_SCHEMA_PATH)
        if not isinstance(internal_schema, dict):
            raise ValidationError("internal schema must be a mapping")
        _require_fields(
            internal_schema,
            ("schema_id", "registry_id", "id_prefix", "required_top_level_fields", "required_entry_fields"),
            "internal schema",
        )

        internal_data = _load_yaml(INTERNAL_PATH)
        external_data = _load_yaml(EXTERNAL_PATH)

        if not isinstance(internal_data, dict):
            raise ValidationError("internal ledger must be a mapping")
        if not isinstance(external_data, dict):
            raise ValidationError("external ledger must be a mapping")

        _require_fields(internal_data, REQUIRED_TOP_LEVEL_FIELDS, "internal ledger")
        _require_fields(external_data, REQUIRED_TOP_LEVEL_FIELDS, "external ledger")

        internal_entries = internal_data["entries"]
        external_entries = external_data["entries"]
        if not isinstance(internal_entries, list) or not internal_entries:
            raise ValidationError("internal ledger entries must be a non-empty list")
        if not isinstance(external_entries, list) or not external_entries:
            raise ValidationError("external ledger entries must be a non-empty list")

        source_ids_seen: set[str] = set()
        canonical_keys_seen: set[str] = set()
        internal_titles_seen: set[str] = set()
        external_titles_seen: set[str] = set()
        source_to_claims: dict[str, set[str]] = {}

        internal_id_set: set[str] = set()
        for idx, entry in enumerate(internal_entries):
            where = f"internal entry[{idx}]"
            if not isinstance(entry, dict):
                raise ValidationError(f"{where} must be a mapping")
            _require_fields(entry, REQUIRED_INTERNAL_FIELDS, where)

            source_id = entry["id"]
            if not isinstance(source_id, str) or not source_id.startswith("src_int_"):
                raise ValidationError(f"{where} invalid internal id: {source_id}")
            if source_id in source_ids_seen:
                raise ValidationError(f"duplicate source id across ledgers: {source_id}")
            source_ids_seen.add(source_id)
            internal_id_set.add(source_id)

            if source_id not in ALLOWED_INTERNAL_ENTRIES:
                raise ValidationError(f"{where} internal id outside allowed set: {source_id}")
            expected_title = ALLOWED_INTERNAL_ENTRIES[source_id]
            if entry["title"] != expected_title:
                raise ValidationError(f"{where} title mismatch for {source_id}")

            canonical_key = entry["canonical_key"]
            if not isinstance(canonical_key, str) or not canonical_key:
                raise ValidationError(f"{where} canonical_key must be a non-empty string")
            if canonical_key in canonical_keys_seen:
                raise ValidationError(f"duplicate canonical_key across ledgers: {canonical_key}")
            canonical_keys_seen.add(canonical_key)

            title = entry["title"]
            if not isinstance(title, str) or not title.strip():
                raise ValidationError(f"{where} title must be a non-empty string")
            normalized_title = _normalize_title(title)
            if normalized_title in internal_titles_seen:
                raise ValidationError(f"duplicate normalized title in internal ledger: {title}")
            internal_titles_seen.add(normalized_title)

            claim_links = entry["claim_links"]
            if not isinstance(claim_links, list) or not claim_links:
                raise ValidationError(f"{where} claim_links must be a non-empty list")
            for claim_id in claim_links:
                if claim_id not in claim_ids:
                    raise ValidationError(f"{where} invalid claim link: {claim_id}")

            concepts_to_borrow = entry["concepts_to_borrow"]
            if not isinstance(concepts_to_borrow, list) or not concepts_to_borrow:
                raise ValidationError(f"{where} concepts_to_borrow must be a non-empty list")
            for concept in concepts_to_borrow:
                if not isinstance(concept, str) or not concept.strip():
                    raise ValidationError(f"{where} invalid concepts_to_borrow item: {concept}")

            likely_necessary = entry["likely_necessary"]
            if not isinstance(likely_necessary, bool):
                raise ValidationError(f"{where} likely_necessary must be boolean")

            warnings = entry["warnings"]
            if not isinstance(warnings, list) or not warnings:
                raise ValidationError(f"{where} warnings must be a non-empty list")
            for warning in warnings:
                if not isinstance(warning, str) or not warning.strip():
                    raise ValidationError(f"{where} invalid warning item: {warning}")

            source_to_claims[source_id] = set(claim_links)

        missing_required_internal = REQUIRED_INTERNAL_IDS - internal_id_set
        if missing_required_internal:
            raise ValidationError(
                "missing required internal sources: " + ", ".join(sorted(missing_required_internal))
            )

        for idx, entry in enumerate(external_entries):
            where = f"external entry[{idx}]"
            if not isinstance(entry, dict):
                raise ValidationError(f"{where} must be a mapping")
            _require_fields(entry, REQUIRED_EXTERNAL_FIELDS, where)

            source_id = entry["id"]
            if not isinstance(source_id, str) or not source_id.startswith("src_ext_"):
                raise ValidationError(f"{where} invalid external id: {source_id}")
            if source_id in source_ids_seen:
                raise ValidationError(f"duplicate source id across ledgers: {source_id}")
            source_ids_seen.add(source_id)

            canonical_key = entry["canonical_key"]
            if not isinstance(canonical_key, str) or not canonical_key:
                raise ValidationError(f"{where} canonical_key must be a non-empty string")
            if canonical_key in canonical_keys_seen:
                raise ValidationError(f"duplicate canonical_key across ledgers: {canonical_key}")
            canonical_keys_seen.add(canonical_key)

            title = entry["title"]
            if not isinstance(title, str) or not title.strip():
                raise ValidationError(f"{where} title must be a non-empty string")
            normalized_title = _normalize_title(title)
            if normalized_title in external_titles_seen:
                raise ValidationError(f"duplicate normalized title in external ledger: {title}")
            external_titles_seen.add(normalized_title)

            source_cluster = entry["source_cluster"]
            if source_cluster not in allowed_clusters:
                raise ValidationError(f"{where} invalid source_cluster: {source_cluster}")

            claim_links = entry["claim_links"]
            if not isinstance(claim_links, list) or not claim_links:
                raise ValidationError(f"{where} claim_links must be a non-empty list")
            for claim_id in claim_links:
                if claim_id not in claim_ids:
                    raise ValidationError(f"{where} invalid claim link: {claim_id}")

            support_roles = entry["support_roles"]
            if not isinstance(support_roles, list) or not support_roles:
                raise ValidationError(f"{where} support_roles must be a non-empty list")
            bad_roles = [role for role in support_roles if role not in allowed_roles]
            if bad_roles:
                raise ValidationError(f"{where} invalid support_roles: {bad_roles}")

            source_to_claims[source_id] = set(claim_links)

        all_source_ids = set(source_to_claims.keys())
        for claim_id, source_ids in claim_sources.items():
            for source_id in source_ids:
                if source_id not in all_source_ids:
                    raise ValidationError(f"claim {claim_id} references unknown source_id: {source_id}")

        for claim_id in known_citation_backed:
            if not claim_sources.get(claim_id):
                raise ValidationError(f"known_citation_backed claim missing source_ids: {claim_id}")

        for claim_id, source_ids in claim_sources.items():
            for source_id in source_ids:
                linked_claims = source_to_claims.get(source_id, set())
                if claim_id not in linked_claims:
                    raise ValidationError(
                        f"bidirectional mismatch: claim {claim_id} -> {source_id} but source missing claim link"
                    )

        for source_id, linked_claims in source_to_claims.items():
            for claim_id in linked_claims:
                claim_linked_sources = set(claim_sources.get(claim_id, []))
                if source_id not in claim_linked_sources:
                    raise ValidationError(
                        f"bidirectional mismatch: source {source_id} -> {claim_id} but claim missing source_id"
                    )

    except ValidationError as exc:
        print(f"citation validation failed: {exc}")
        return 1

    print("citation validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
