from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "apocalypse_bot/commands/v1151_alert_settings_ui.py"
BOT = ROOT / "apocalypse_bot/core/bot.py"


def source() -> str:
    return MODULE.read_text(encoding="utf-8")


def test_v1151_registered_before_english_sync():
    text = BOT.read_text(encoding="utf-8")
    assert "register_v1151_alert_settings_ui" in text
    assert text.index("register_v1151_alert_settings_ui") < text.index("synchronize_all_english_aliases")


def test_dropdown_components_present():
    text = source()
    for token in [
        "class AlertTypeSelect", "class AlertModeSelect", "class AlertChannelSelect",
        "class AlertRoleSelect", "class RestorePointSelect", "class AlertSettingsView",
    ]:
        assert token in text
    assert "discord.ui.ChannelSelect" in text
    assert "discord.ui.RoleSelect" in text
    assert "min_values=0" in text


def test_five_safe_actions_present():
    text = source()
    for action in ["apply", "preview", "test", "backup", "restore"]:
        assert f'"{action}"' in text
    assert "_settings_backup" in text
    assert "_restore_settings" in text


def test_text_command_compatibility_kept():
    text = source()
    assert 'old_server_alerts = bot.remove_command("서버알림")' in text
    assert "await old_server_alerts.callback(ctx, 종류, 상태, 채널)" in text
    assert 'name="서버알림"' in text
    assert '"serveralerts"' in text


def test_no_everyone_ping_and_safe_mentions():
    text = source()
    assert "guild.default_role" in text
    assert "everyone=False" in text
    assert "AllowedMentions" in text


def test_latest_test_and_patchnotes():
    text = source()
    assert "test_command.callback = v1151_test" in text
    assert "patch_notes.callback = v1151_notes" in text
    assert 'name="알림UI검수"' in text
