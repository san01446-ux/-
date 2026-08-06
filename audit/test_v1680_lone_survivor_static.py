from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "apocalypse_bot/commands/v1680_lone_survivor.py"
CORE = ROOT / "apocalypse_bot/core/bot.py"
HUB = ROOT / "apocalypse_bot/commands/v1630_core_rpg_command_city_overhaul.py"


def test_module_compiles_and_registers():
    source = MODULE.read_text(encoding="utf-8")
    compile(source, str(MODULE), "exec")
    core = CORE.read_text(encoding="utf-8")
    assert "register_v1680_lone_survivor" in core


def test_command_surface_and_shortcuts():
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr == "command":
                    for kw in dec.keywords:
                        if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                            names.append(kw.value.value)
    assert len(names) == 10
    assert {"솔로원정", "원정이어하기", "주간변이지역", "원정도감", "1680통합검수"}.issubset(names)
    hub = HUB.read_text(encoding="utf-8")
    assert all(token in hub for token in ("quick_more2", "lone_expedition", "weekly_expedition", "expedition_codex"))


def test_static_feature_guards():
    source = MODULE.read_text(encoding="utf-8")
    for token in ("len(ZONES) == 7", "len(DIFFICULTIES) == 4", "len(COMPANIONS) == 5", "rescue_keep", "SEED_RE", "save_data()"):
        assert token in source
