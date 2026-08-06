from __future__ import annotations

import json
import time

from apocalypse_bot.commands.v1320_black_city_core import (
    DISTRICTS,
    PROFESSIONS,
    RECIPES,
    add_material,
    attempt_crime,
    buy_listing,
    choose_profession,
    craft,
    create_backup,
    create_faction,
    create_listing,
    determine_ending,
    donate_facility,
    economy_audit,
    ensure_guild,
    ensure_root,
    ensure_season,
    ensure_user,
    full_audit,
    gather,
    public_snapshot,
    restore_backup,
    territory_attack,
)


def user(balance=100_000):
    return {"balance": balance}


def city():
    root = ensure_root({})
    return ensure_guild(root, 1, guild_name="테스트")


def test_schema_is_json_serializable_and_defaults_off():
    row = city()
    assert len(row["districts"]) == 9
    assert row["settings"]["enabled"] is False
    assert row["settings"]["public_world"] is False
    json.dumps(row, ensure_ascii=False)


def test_user_profession_gather_and_craft():
    row = city()
    u = user()
    ok, name = choose_profession(u, "대장장이")
    assert ok and name == "대장장이"
    result = gather(row, u, 10, timestamp=10_000)
    assert result["ok"] and result["resource"] == "철광"
    add_material(u, "철광", 20)
    made = craft(u, "강화철판", 2)
    assert made == {"ok": True, "item": "강화철판", "qty": 2}
    assert ensure_user(u)["crafted"]["강화철판"] == 2


def test_market_escrow_and_idempotency():
    row = city()
    seller = user(); buyer = user()
    ensure_user(seller)["crafted"]["강화철판"] = 3
    listing = create_listing(row, seller, 1, "강화철판", 2, 1000)
    assert listing["ok"]
    before_buyer = buyer["balance"]
    before_seller = seller["balance"]
    sold = buy_listing(row, buyer, seller, 2, listing["listing"]["id"])
    assert sold["ok"]
    assert buyer["balance"] == before_buyer - 2000
    assert seller["balance"] == before_seller + 1940
    again = buy_listing(row, buyer, seller, 2, listing["listing"]["id"])
    assert not again["ok"]
    assert len(row["market"]["ledger"]) == 1


def test_faction_territory_is_guild_scoped():
    row = city(); u = user()
    ok, name, _ = create_faction(row, u, 1, "검은날개")
    assert ok
    result = territory_attack(row, u, 1, "중앙카지노", nonce="fixed")
    assert result["ok"]
    assert result["district"] == "중앙카지노"
    assert ensure_user(u)["stats"]["territory_actions"] == 1


def test_crime_never_touches_other_user_balance():
    row = city(); actor = user(); victim = user(77_777)
    before = victim["balance"]
    result = attempt_crime(row, actor, 1, "NPC금고털이", timestamp=20_000)
    assert result["ok"]
    assert victim["balance"] == before
    assert row["crime"]["event_fund"] >= 0


def test_facility_and_backup_restore():
    row = city(); u = user(500_000)
    backup = create_backup(row, 1)
    result = donate_facility(row, u, 1, "대형경기장", 100_000)
    assert result["ok"] and result["complete"]
    assert row["facilities"]["대형경기장"]["complete"]
    restored = restore_backup(row, backup["id"], 1)
    assert restored["ok"]
    assert not row.get("facilities", {}).get("대형경기장", {}).get("complete", False)


def test_season_and_eight_ending_catalogue_path():
    row = city()
    season = ensure_season(row, timestamp=1_000_000)
    assert season["stage"] == 1
    row["metrics"].update({"prosperity": 90, "economy": 90, "security": 90, "chaos": 10, "fame": 90})
    for name in list(row["facilities"]):
        row["facilities"][name]["complete"] = True
    # Add all defined facilities for the true-ending path.
    from apocalypse_bot.commands.v1320_black_city_core import FACILITIES
    for name in FACILITIES:
        row["facilities"].setdefault(name, {})["complete"] = True
    season["score"]["boss"] = 60
    assert determine_ending(row) == "진엔딩"


def test_public_snapshot_respects_opt_in():
    row = city()
    assert public_snapshot(row)["status"] == "private"
    row["settings"]["public_world"] = True
    snap = public_snapshot(row)
    assert snap["status"] == "online"
    raw = json.dumps(snap, ensure_ascii=False)
    assert "user_id" not in raw and "inventory" not in raw


def test_full_audit_passes_clean_state():
    row = city()
    result = full_audit(row, {})
    assert result["ok"], result
    assert result["passed"] == result["total"]
