from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOT = (ROOT / 'apocalypse_bot/core/bot.py').read_text(encoding='utf-8')
GUARD = (ROOT / 'apocalypse_bot/commands/v1330_command_registry_guard.py').read_text(encoding='utf-8')
FUN = (ROOT / 'apocalypse_bot/commands/v1220_chaos_festival_complete.py').read_text(encoding='utf-8')
CITY = (ROOT / 'apocalypse_bot/commands/v1320_black_city_complete.py').read_text(encoding='utf-8')


def test_guard_installed_before_extensions():
    assert BOT.index('install_command_registry_guard(bot)') < BOT.index('register_condition_commands(')


def test_render_collision_aliases_are_separated():
    assert 'aliases=["expedition", "adventure"]' not in FUN
    assert 'aliases=["fortune", "dailyfortune"]' not in FUN
    assert 'aliases=["attendance", "checkin"]' not in FUN
    assert 'aliases=["marketbuy", "buycitylisting"]' not in CITY
    assert 'festivalexpedition' in FUN
    assert 'festivalfortune' in FUN
    assert 'festivalcheckin' in FUN
    assert 'citymarketbuy' in CITY


def test_guard_removes_alias_instead_of_raising():
    assert 'command.aliases = clean_aliases' in GUARD
    assert 'except commands.CommandRegistrationError' in GUARD
    assert 'return None' in GUARD


def test_diagnostics_registered():
    assert 'name="명령등록검수"' in GUARD
    assert 'name="1330안정화검수"' in GUARD
