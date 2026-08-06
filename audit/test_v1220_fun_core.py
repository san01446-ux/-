from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
CORE = ROOT / "apocalypse_bot/commands/v1220_fun_core.py"
COMMANDS = ROOT / "apocalypse_bot/commands/v1220_chaos_festival_complete.py"
BOT = ROOT / "apocalypse_bot/core/bot.py"

spec = importlib.util.spec_from_file_location("v1220_fun_core", CORE)
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
assert spec.loader is not None
spec.loader.exec_module(core)


def test_catalogue_scale():
    row = core.audit_catalogues()
    assert row["version"] == "12.2.0"
    assert row["events"] == 8
    assert row["npcs"] == 6
    assert row["pets"] == 8
    assert row["expeditions"] == 8
    assert row["businesses"] == 8
    assert row["bingo_cells"] == 25


def test_reward_idempotency():
    user = {}
    first = core.reward_once(user, "event:1", 1000)
    second = core.reward_once(user, "event:1", 1000)
    assert first.ok and first.payload["amount"] == 1000
    assert not second.ok and second.code == "duplicate"


def test_secret_friend_has_no_self_targets():
    assignments = core.assign_secret_friends([1, 2, 3, 4, 5], "seed")
    assert len(assignments) == 5
    assert set(assignments) == {1, 2, 3, 4, 5}
    assert set(assignments.values()) == {1, 2, 3, 4, 5}
    assert all(sender != target for sender, target in assignments.items())


def test_mafia_and_liar_roles():
    mafia = core.mafia_roles([1, 2, 3, 4, 5, 6, 7], "seed")
    assert len(mafia) == 7
    assert "마피아" in mafia.values()
    liar = core.liar_roles([1, 2, 3, 4], "seed")
    assert liar.ok
    assert liar.payload["liar_id"] in liar.payload["words"]
    assert len(set(liar.payload["words"].values())) == 2


def test_expedition_restart_safe_state_and_completion():
    started = core.start_expedition("폐허", 42, now=1_700_000_000)
    assert started.ok and started.payload["status"] == "active"
    session = started.payload
    for _ in range(8):
        if session["status"] != "active":
            break
        result = core.advance_expedition(session, "정찰")
        assert result.ok
        session = result.payload["session"]
    assert session["status"] in {"complete", "failed"}
    assert session["id"].startswith("X-")


def test_business_income_is_deterministic_and_nonnegative():
    business = {"type": "cafe", "level": 3, "employees": ["루시안"], "rating": 1.2}
    first = core.business_income(business, 10, "2026-08-05")
    second = core.business_income(business, 10, "2026-08-05")
    assert first == second
    assert first > 0


def test_bingo_layout_and_lines():
    board = core.make_bingo(123, "2026-08")
    assert len(board) == 25
    assert board[12] == "자유칸"
    assert core.bingo_lines([0, 1, 2, 3, 4, 12]) == 1


def test_anonymous_message_safety():
    assert core.sanitize_anonymous_message("응원합니다!").ok
    assert not core.sanitize_anonymous_message("https://example.com").ok
    cleaned = core.sanitize_anonymous_message("@everyone 힘내요")
    assert cleaned.ok and "@everyone" not in cleaned.payload["text"]


def test_cosmetic_unlocks_and_secret_flags():
    fun = {"fun_score": 60, "secret_points": 7}
    unlocked = core.unlock_cosmetics(fun)
    assert unlocked
    flags = core.secret_flags(fun, {"hwatu_months": 12, "balance": -1, "expeditions_complete": 1, "underdog_race_wins": 1, "praise_chain": 5})
    assert {"twelve_moons", "bankrupt_explorer", "underdog_crown", "praise_door", "abaddon_final"}.issubset(flags)


def _decorated_commands(source: str):
    pattern = re.compile(r'@bot\.command\(name=["\']([^"\']+)["\'](?:,\s*aliases=\[([^\]]*)\])?')
    rows = []
    for match in pattern.finditer(source):
        aliases = re.findall(r'["\']([^"\']+)["\']', match.group(2) or "")
        rows.append((match.group(1), aliases))
    return rows


def test_command_surface_and_registration_order():
    source = COMMANDS.read_text(encoding="utf-8")
    ast.parse(source)
    rows = _decorated_commands(source)
    names = {name for name, _ in rows}
    required = {
        "혼돈축제", "돌발이벤트", "폭탄돌리기", "마피아", "라이어게임", "그림자추리", "생존룰렛", "심리전",
        "딜러대화", "동료뽑기", "탐험", "파티탐험", "사업개설", "오늘의명장면", "축제운세", "축제밸런스",
        "익명응원", "비밀친구", "서버빙고", "꾸미기센터", "비밀힌트", "전설아이템", "혼돈백업", "혼돈복구", "1220통합검수",
    }
    assert required.issubset(names)
    assert len(rows) >= 75
    bot_source = BOT.read_text(encoding="utf-8")
    assert "register_v1220_chaos_festival_complete" in bot_source
    assert bot_source.index("register_v1220_chaos_festival_complete") < bot_source.index("synchronize_all_english_aliases")


def test_new_command_names_do_not_collide_with_older_modules():
    current = COMMANDS.read_text(encoding="utf-8")
    current_names = []
    for primary, aliases in _decorated_commands(current):
        current_names.extend([primary, *aliases])
    older_names = set()
    for path in (ROOT / "apocalypse_bot/commands").glob("*.py"):
        if path in {COMMANDS, CORE}:
            continue
        for primary, aliases in _decorated_commands(path.read_text(encoding="utf-8", errors="ignore")):
            older_names.update([primary, *aliases])
    assert not (set(current_names) & older_names)
