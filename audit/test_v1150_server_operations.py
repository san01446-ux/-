from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "apocalypse_bot/commands/v1150_server_operations_permissions.py"
CORE = ROOT / "apocalypse_bot/core/bot.py"


def _source() -> str:
    return MODULE.read_text(encoding="utf-8")


def _commands() -> dict[str, list[str]]:
    tree = ast.parse(_source())
    rows: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute) or dec.func.attr != "command":
                continue
            name = None
            aliases: list[str] = []
            for keyword in dec.keywords:
                if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                    name = keyword.value.value
                elif keyword.arg == "aliases" and isinstance(keyword.value, (ast.List, ast.Tuple)):
                    aliases = [item.value for item in keyword.value.elts if isinstance(item, ast.Constant)]
            if isinstance(name, str):
                rows[name] = aliases
    return rows


def test_registration_precedes_english_sync() -> None:
    source = CORE.read_text(encoding="utf-8")
    assert source.index("register_v1150_server_operations_permissions") < source.index("synchronize_all_english_aliases")


def test_command_surface() -> None:
    commands = _commands()
    expected = {
        "서버운영", "서버알림", "알림채널", "알림멘션", "알림시간", "알림시간해제", "알림테스트",
        "서버봇목록", "서버봇권한검수", "권한백업", "봇권한적용", "권한자동설정",
        "권한복구", "권한변경내역", "서버설정백업", "서버설정복구", "서버설정검수",
    }
    assert expected <= commands.keys()
    assert "serveroperations" in commands["서버운영"]
    assert "serverbotaudit" in commands["서버봇권한검수"]
    assert "restorepermissions" in commands["권한복구"]


def test_backup_before_permission_change() -> None:
    source = _source()
    apply_block = source[source.index("async def apply_bot_permissions"):source.index("@bot.command(name=\"권한자동설정\"")]
    assert apply_block.index("_backup_entries") < apply_block.index("set_permissions")
    auto_block = source[source.index("async def auto_permissions"):source.index("@bot.command(name=\"권한복구\"")]
    assert auto_block.index("_backup_entries") < auto_block.index("set_permissions")


def test_other_bots_require_explicit_target_and_hierarchy() -> None:
    source = _source()
    assert "if not 대상.bot" in source
    assert "target.top_role >= me.top_role" in source
    assert "대상 봇을 지정" in source or "명시적으로" in source


def test_permission_restore_uses_pair_snapshot() -> None:
    source = _source()
    assert "overwrite.pair()" in source
    assert "PermissionOverwrite.from_pair" in source
    assert '"allow": int(allow.value)' in source
    assert '"deny": int(deny.value)' in source


def test_permission_profiles_and_inference() -> None:
    tree = ast.parse(_source())
    profiles = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PERMISSION_PROFILES" for t in node.targets):
            profiles = ast.literal_eval(node.value)
            break
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "PERMISSION_PROFILES":
            profiles = ast.literal_eval(node.value)
            break
    assert profiles is not None
    assert set(profiles) == {"general", "alerts", "games", "operations", "voice", "readonly", "blocked"}
    assert profiles["games"]["attach_files"] is True
    assert profiles["voice"]["connect"] is True
    assert profiles["blocked"]["view_channel"] is False


def test_notification_integrations() -> None:
    source = _source()
    for key in ("disaster", "patch", "quiz", "market", "frontier"):
        assert f'key == "{key}"' in source
    assert "quiet_hours_enabled" in source
    assert "operations_sync_loop" in source
    assert "v1150_dispatch_alert" in source


def test_patch_notifications_are_opt_in() -> None:
    source = _source()
    assert 'settings["patch_auto"] = False' in source
    assert "v1150_optin_migrated" in source
    assert "configured_patch_channel" in source


def test_latest_test_and_patch_notes_replaced() -> None:
    source = _source()
    assert "test_command.callback = v1150_test" in source
    assert "patch_notes.callback = v1150_notes" in source
    assert "!서버설정검수 상세" in source
