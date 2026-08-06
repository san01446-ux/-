from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from apocalypse_bot.commands.v1160_recovery_rules import (
    apply_encoded_state,
    coerce_turn_seconds,
    decode_state,
    encode_state,
    normalize_afk_action,
    refund_plan,
    snapshot_checksum,
    validate_hwatu_assets,
)


@dataclass(frozen=True)
class Card:
    month: int
    kind: str


class Holder:
    def __init__(self) -> None:
        self.cards = []
        self.values = {}


def test_state_roundtrip_preserves_types() -> None:
    source = {1: (Card(1, "bright"), {2, 3}), "cards": [Card(8, "animal")]}
    encoded = encode_state(source)
    decoded = decode_state(encoded)
    assert decoded[1][0] == Card(1, "bright")
    assert decoded[1][1] == {2, 3}
    assert decoded["cards"][0] == Card(8, "animal")


def test_apply_encoded_state() -> None:
    target = Holder()
    apply_encoded_state(target, {"cards": encode_state([Card(3, "ribbon")]), "values": encode_state({4: 5})})
    assert target.cards[0].month == 3
    assert target.values == {4: 5}


def test_afk_normalization_and_limits() -> None:
    assert normalize_afk_action("아바돈 대행") == "abaddon"
    assert normalize_afk_action("자동폴드") == "fold"
    assert coerce_turn_seconds(1) == 20
    assert coerce_turn_seconds(9999) == 600


def test_refund_prefers_actual_paid() -> None:
    reservation = {"bet": 100, "players": [1, 2], "actual_paid": {"1": 850, "2": 100}}
    assert refund_plan(reservation) == {1: 850, 2: 100}
    assert refund_plan({"bet": 100, "players": [1, -1060, 2]}) == {1: 100, 2: 100}


def test_snapshot_checksum_stable() -> None:
    assert snapshot_checksum({"b": 2, "a": 1}) == snapshot_checksum({"a": 1, "b": 2})


def test_hwatu_validation(tmp_path: Path) -> None:
    cards = tmp_path / "cards"
    cards.mkdir()
    manifest = {str(m): {str(s): f"m{m:02d}_c{s}.png" for s in range(1, 5)} for m in range(1, 13)}
    manifest["_types"] = {str(m): {str(s): "junk" for s in range(1, 5)} for m in range(1, 13)}
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    for month in range(1, 13):
        for slot in range(1, 5):
            (cards / f"m{month:02d}_c{slot}.png").write_bytes(b"png")
    result = validate_hwatu_assets(manifest_path, cards, [m * 10 + s for m in range(1, 13) for s in range(1, 5)])
    assert result["ok"] is True
