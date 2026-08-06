from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CMD = ROOT / "apocalypse_bot" / "commands"
V1090 = CMD / "v1090_integrated_renewal.py"
V1060 = CMD / "v1060_authentic_card_games.py"
V1051 = CMD / "v1051_authentic_card_games.py"
V651 = CMD / "v651_card_games.py"
BOT = ROOT / "apocalypse_bot" / "core" / "bot.py"

NEW_COMMANDS = {
    "훌라": {"hoola", "hula"},
    "라미": {"rummy"},
    "대통령": {"president", "daifugo"},
    "주사위카드": {"dicecard", "dicecardpoker"},
    "삼봉": {"sambong"},
    "도리짓고땡": {"dorijitgottaeng", "dori"},
    "민화투": {"minhwatu"},
    "육백": {"yukbaek", "hwatu600"},
    "블랙잭토너먼트": {"blackjacktournament", "bjtournament"},
}


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _literal(node: ast.AST):
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _decorated_commands(path: Path):
    tree = ast.parse(_source(path), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            call = dec if isinstance(dec, ast.Call) else None
            func = call.func if call else dec
            if not isinstance(func, ast.Attribute) or func.attr not in {"command", "hybrid_command", "group", "hybrid_group"}:
                continue
            kwargs = {kw.arg: _literal(kw.value) for kw in call.keywords if kw.arg} if call else {}
            name = kwargs.get("name") or node.name
            aliases = kwargs.get("aliases") or []
            found.append((name, tuple(aliases), node.lineno))
    return found


def test_v1090_python_parses() -> None:
    ast.parse(_source(V1090), filename=str(V1090))


def test_new_games_are_exactly_nine_and_total_is_twenty_five() -> None:
    source = _source(V1090)
    tree = ast.parse(source)
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"NEW_GAMES"}:
                    values[target.id] = _literal(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "NEW_GAMES":
            values[node.target.id] = _literal(node.value)
    assert set(values["NEW_GAMES"]) == set(NEW_COMMANDS)
    assert "ALL_GAMES: Tuple[str, ...] = tuple(AUTHENTIC_GAMES) + NEW_GAMES" in source
    assert "len(ALL_GAMES) == 25" in source


def test_every_new_game_has_natural_ascii_alias() -> None:
    commands = {name: set(aliases) for name, aliases, _line in _decorated_commands(V1090)}
    for name, aliases in NEW_COMMANDS.items():
        assert name in commands
        assert aliases <= commands[name]
        assert any(alias.isascii() for alias in commands[name])


def test_every_game_has_ai_factory_and_three_player_fill() -> None:
    source = _source(V1090)
    assert "for name in ALL_GAMES" in source
    assert "all(callable(factory_for(name).build) for name in ALL_GAMES)" in source
    assert "AI_ID_2" in source
    assert 'factory_for("고스톱").minimum == 3' in source
    assert 'factory_for("육백").minimum == 3' in source


def test_select_components_never_build_more_than_25_options() -> None:
    source = _source(V1090)
    assert source.count("enumerate(hand[:25])") >= 2
    assert "options=options" in source
    assert "len(ALL_GAMES) == 25" in source


def test_final_result_includes_balance_delta_and_fallback_publish() -> None:
    source1060 = _source(V1060)
    source1090 = _source(V1090)
    assert "def settlement_text" in source1060
    assert "잔액 **{before:,} → {current:,}칩**" in source1060
    assert "async def _publish_final" in source1060
    assert "await channel.send" in source1060
    assert source1060.count("await _publish_final") >= 5
    assert "승부 결과 · 최종 정산" in source1090
    assert "self.settlement_text(uid" in source1090
    assert "await _publish_final" in source1090


def test_onecard_and_joker_final_results_show_wallet_movement() -> None:
    source = _source(V1051)
    assert "원카드 승부 결과" in source
    assert "조커잡기 승부 결과" in source
    assert "잔액" in source
    assert "before" in source and "current" in source
    assert "await channel.send" in source


def test_safe_edit_returns_status_for_recovery_logic() -> None:
    source = _source(V651)
    assert "async def _safe_edit" in source
    assert "-> bool" in source
    assert "return True" in source
    assert "return False" in source


def test_negative_balance_and_uncapped_settlement_are_retained() -> None:
    source1060 = _source(V1060)
    source1090 = _source(V1090)
    assert "negative balances allowed" in source1060
    assert "배수 상한 없음" in source1060
    assert "무상한 입력" in source1090
    assert "80-digit integer" in source1090
    assert "파산신청" in source1090


def test_latest_only_audit_and_patch_notes_are_v1090() -> None:
    source = _source(V1090)
    assert 'VERSION = "10.9.0"' in source
    assert "이번 v10.9.0에서 추가·수정된 기능만" in source
    assert "!테스트 상세" in source
    assert "최신 패치노트" in source
    assert "홈페이지/명령어/설명 동기화" in source


def test_information_dashboard_status_lists_remaining_legacy_views() -> None:
    source = _source(V1090)
    assert "정보리뉴얼현황" in source
    for marker in ("상점", "장비", "보물", "TTS", "채널", "관리자"):
        assert marker in source


def test_v1090_registers_before_final_english_alias_sync() -> None:
    source = _source(BOT)
    register_at = source.index("register_v1090_integrated_renewal")
    sync_at = source.index("synchronize_all_english_aliases")
    assert register_at < sync_at
