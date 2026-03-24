from __future__ import annotations

from closure_frontier.pica_adapter import (
    list_figdata_files,
    list_ledger_files,
    load_primitives_yaml,
    vendor_root,
)


def test_pica_adapter_smoke() -> None:
    root = vendor_root()
    assert root.is_dir()

    primitives = load_primitives_yaml()
    assert isinstance(primitives, dict)
    assert primitives

    ledger_files = list_ledger_files()
    figdata_files = list_figdata_files()
    assert len(ledger_files) > 0
    assert len(figdata_files) > 0
