from __future__ import annotations

import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CMD = ROOT / "apocalypse_bot" / "commands"
HOTFIX = CMD / "v1091_card_dashboard_hotfix.py"
LOCALIZER = CMD / "v1000_global_survivor.py"
V1090 = CMD / "v1090_integrated_renewal.py"
BOT = ROOT / "apocalypse_bot" / "core" / "bot.py"
INIT = ROOT / "apocalypse_bot" / "__init__.py"


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def literal_assignment(path: Path, name: str):
    tree = ast.parse(source(path), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        else:
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            return ast.literal_eval(value)
    raise AssertionError(name)


def test_hotfix_python_parses() -> None:
    ast.parse(source(HOTFIX), filename=str(HOTFIX))


def test_version_is_v1091() -> None:
    assert 'VERSION = "10.9.1"' in source(HOTFIX)
    match = re.search(r'__version__\s*=\s*"(\d+)\.(\d+)\.(\d+)"', source(INIT))
    assert match is not None
    assert tuple(map(int, match.groups())) >= (10, 9, 1)


def test_card_dashboard_command_and_aliases_exist() -> None:
    text = source(HOTFIX)
    assert '@bot.command(name="카드대시보드"' in text
    for alias in ("carddashboard", "cardcatalog", "cardgamesdashboard", "카드도감"):
        assert alias in text


def test_catalog_has_25_games_and_discord_limit_guard() -> None:
    text = source(HOTFIX)
    assert "for kind in ALL_GAMES" in text
    assert "len(ALL_GAMES) == 25" in text
    assert "len(ALL_GAMES) <= 25" in text


def test_all_25_games_have_player_metadata() -> None:
    player_ranges = literal_assignment(HOTFIX, "PLAYER_RANGES")
    assert len(player_ranges) == 25
    assert player_ranges["고스톱"] == (3, 3)
    assert player_ranges["육백"] == (3, 3)
    assert player_ranges["인디언포커"] == (2, 2)


def test_dashboard_launches_public_and_ai_routes() -> None:
    text = source(HOTFIX)
    assert "v1090_create_card_lobby" in text
    assert "v1090_start_ai_card" in text
    assert "StakeModal(self.kind, self.locale, False)" in text
    assert "StakeModal(self.kind, self.locale, True)" in text
    assert "bot.v1090_create_card_lobby = create_lobby_interaction" in source(V1090)


def test_modern_label_is_used_for_new_modal() -> None:
    text = source(HOTFIX)
    assert 'label_cls = getattr(discord.ui, "Label", None)' in text
    assert "component=self.amount" in text
    assert "self.amount = discord.ui.TextInput(placeholder=" in text


def test_localizer_skips_deprecated_textinput_label() -> None:
    text = source(LOCALIZER)
    assert "V1091_DEPRECATION_SAFE_LOCALIZER = True" in text
    assert "is_text_input" in text
    assert "if not is_text_input:" in text
    assert "item.label =" in text  # still valid for buttons/selects, guarded above
    assert "TextInput.label`` emits a DeprecationWarning" in text


def test_hotfix_registered_before_alias_sync() -> None:
    text = source(BOT)
    register_at = text.index("register_v1091_card_dashboard_hotfix")
    sync_at = text.index("synchronize_all_english_aliases")
    assert register_at < sync_at


def test_latest_test_and_patch_notes_are_scoped_to_v1091() -> None:
    text = source(HOTFIX)
    assert "이번 v10.9.1에서 수정한 카드 대시보드와 UI 경고 경로만" in text
    assert "이번 패치에서 실제로 수정한 항목만" in text
    assert "!테스트 상세" in text
    assert "!패치노트" in text
