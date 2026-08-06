from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAOS = ROOT / "apocalypse_bot" / "commands" / "v1220_chaos_festival_complete.py"
HOTFIX = ROOT / "apocalypse_bot" / "commands" / "v1221_runtime_ui_hotfix.py"
CITY = ROOT / "apocalypse_bot" / "commands" / "v1320_black_city_complete.py"
BOT = ROOT / "apocalypse_bot" / "core" / "bot.py"


def test_chaos_hub_select_has_no_component_emoji_payloads():
    text = CHAOS.read_text("utf-8")
    section = text[text.index("class FunHubSelect"):text.index("class FunHubView")]
    assert "emoji=" not in section


def test_chaos_event_fast_ack_happens_before_save_action():
    text = CHAOS.read_text("utf-8")
    start = text.index("async def handler(interaction")
    section = text[start:start + 2600]
    assert section.index("response.defer") < section.index("apply_event_action")
    assert "interaction.followup.send" in section
    assert 'EventActionButton(locale, "1", None' in text


def test_retry_runtime_catches_invalid_component_body():
    text = HOTFIX.read_text("utf-8")
    assert "50035" in text
    assert "invalid form body" in text.lower()
    assert "strip_view_emojis" in text
    assert "retry" in text.lower()


def test_registration_order_hotfix_then_city_then_alias_sync():
    text = BOT.read_text("utf-8")
    hotfix = text.index("register_v1221_runtime_ui_hotfix")
    city = text.index("register_v1320_black_city_complete")
    aliases = text.index("synchronize_all_english_aliases(bot)")
    assert hotfix < city < aliases


def test_black_city_module_compiles_and_has_no_select_emojis():
    ast.parse(CITY.read_text("utf-8"))
    text = CITY.read_text("utf-8")
    section = text[text.index("class CityHubSelect"):text.index("class CityHubView")]
    assert "emoji=" not in section
    assert 'name="1320통합검수"' in text
    assert 'name="오류검수"' in text

def test_black_city_background_loop_starts_only_after_ready():
    text = CITY.read_text("utf-8")
    assert '@bot.listen("on_ready")' in text
    immediate = text[text.index('@black_city_loop.before_loop'):]
    assert 'if not black_city_loop.is_running():\n        black_city_loop.start()' not in immediate.split('@bot.listen("on_ready")')[0]
