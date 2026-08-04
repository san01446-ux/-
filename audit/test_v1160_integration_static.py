from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "apocalypse_bot" / "commands" / "v1160_game_recovery_validation.py"
BOT = ROOT / "apocalypse_bot" / "core" / "bot.py"


def _source() -> str:
    return RUNTIME.read_text(encoding="utf-8")


def test_runtime_module_parses() -> None:
    ast.parse(_source())


def test_registration_is_after_v1152_and_before_english_sync() -> None:
    source = BOT.read_text(encoding="utf-8")
    p1152 = source.index("register_v1152_traditional_hwatu_refresh")
    p1160 = source.index("register_v1160_game_recovery_validation")
    psync = source.index("synchronize_all_english_aliases")
    assert p1152 < p1160 < psync


def test_required_commands_and_policies_are_present() -> None:
    source = _source()
    for token in [
        'name="게임복구목록"', 'name="게임재개"', 'name="게임강제환불"',
        'name="잠수규칙"', 'name="잠수규칙설정"', 'name="턴시간설정"',
        'name="판정요청"', 'name="판정로그"', 'name="실전게임검수"',
    ]:
        assert token in source
    for token in ['action == "refund"', 'action == "pause"', 'action == "fold"', 'action == "abaddon"']:
        assert token in source


def test_exact_refund_and_result_once_hooks_exist() -> None:
    source = _source()
    assert "actual_paid" in source
    assert "publish_once" in source
    assert '"result_delivery"' in source
    assert "refund_plan" in source


def test_private_hands_are_not_in_reports() -> None:
    source = _source()
    report_block = source[source.index('name="판정요청"'):source.index('name="판정로그"')]
    assert '"hands"' not in report_block
    assert "private hands are not stored" in source
