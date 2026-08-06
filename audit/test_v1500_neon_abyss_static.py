from __future__ import annotations

import ast
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "apocalypse_bot" / "commands" / "v1500_neon_abyss.py"
DIALOGUE = ROOT / "apocalypse_bot" / "commands" / "v620_dialogue_memory.py"
CORE = ROOT / "apocalypse_bot" / "core" / "bot.py"
ASSETS = ROOT / "apocalypse_bot" / "assets" / "v1500"
SITE = Path("/mnt/data/v1500_site")
OLD_MANIFEST = Path("/mnt/data/ABADDON_COMMAND_MANIFEST_v13.3.0.json")


class RefParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        data = dict(attrs)
        for key in ("href", "src"):
            value = data.get(key)
            if value:
                self.refs.append(value)


def _commands() -> list[tuple[str, list[str], int]]:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    rows = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr == "command"):
                continue
            name = None
            aliases: list[str] = []
            for kw in dec.keywords:
                if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                    name = str(kw.value.value)
                if kw.arg == "aliases" and isinstance(kw.value, (ast.List, ast.Tuple)):
                    aliases = [str(x.value) for x in kw.value.elts if isinstance(x, ast.Constant)]
            if name:
                rows.append((name, aliases, node.lineno))
    return rows


def test_module_and_dialogue_compile() -> None:
    ast.parse(MODULE.read_text(encoding="utf-8"))
    ast.parse(DIALOGUE.read_text(encoding="utf-8"))
    ast.parse(CORE.read_text(encoding="utf-8"))


def test_registration_order_is_guard_then_v1500_then_english_sync() -> None:
    text = CORE.read_text(encoding="utf-8")
    assert text.index("register_v1330_command_registry_guard") < text.index("register_v1500_neon_abyss")
    assert text.index("register_v1500_neon_abyss") < text.index("synchronize_all_english_aliases")


def test_city_component_assets_are_complete_and_decodable() -> None:
    manifest = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "15.0.0"
    assert len(manifest["components"]) == 20
    for item in manifest["components"]:
        path = ASSETS / item["file"]
        assert path.exists(), path
        with Image.open(path) as image:
            image.verify()


def test_visual_previews_and_effect_assets_decode() -> None:
    required = [
        ASSETS / "city" / "neon_city_background.png",
        ASSETS / "boss" / "boss_stage_showcase.png",
        ASSETS / "effects" / "effect_legend.png",
        ASSETS / "previews" / "ABADDON_v15.0.0_MASTER_SHOWCASE.png",
        ASSETS / "previews" / "ABADDON_v15.0.0_LAYERED_CITY_PREVIEW.png",
        ASSETS / "previews" / "ABADDON_v15.0.0_CITY_PARTS_CATALOG.png",
        ASSETS / "previews" / "ABADDON_v15.0.0_ACTION_FX_PREVIEW.png",
        ASSETS / "previews" / "ABADDON_v15.0.0_CONTEXT_CHAT_KO.png",
        ASSETS / "previews" / "ABADDON_v15.0.0_CONTEXT_CHAT_EN.png",
    ]
    for path in required:
        assert path.exists(), path
        with Image.open(path) as image:
            image.verify()


def test_new_command_tokens_do_not_collide_with_v1330_manifest() -> None:
    old = json.loads(OLD_MANIFEST.read_text(encoding="utf-8"))["commands"]
    used: set[str] = set()
    for cmd in old:
        used.add(cmd["name"])
        used.update(cmd.get("aliases", []))
    internal: set[str] = set()
    for name, aliases, _ in _commands():
        for token in [name, *aliases]:
            assert token not in internal, token
            internal.add(token)
            if name == "도시지도" and token in {"도시지도", "citymap", "blackcitymap"}:
                continue
            assert token not in used, token


def test_every_new_command_has_ascii_access() -> None:
    for name, aliases, _ in _commands():
        if name == "도시지도":
            # Runtime replacement reuses the old citymap aliases dynamically.
            continue
        assert any(re.fullmatch(r"[a-z0-9_-]+", alias) for alias in aliases), name


def test_conversation_context_limits_and_hook() -> None:
    text = DIALOGUE.read_text(encoding="utf-8")
    assert "CONVERSATION_TIMEOUT_SECONDS = 60 * 60" in text
    assert "CONVERSATION_MAX_TURNS = 100" in text
    assert "CONVERSATION_HISTORY_LIMIT = 20" in text
    assert "_abaddon_v1500_conversation_reply" in text
    module = MODULE.read_text(encoding="utf-8")
    assert "v1500_mode" in module
    assert "v1500_en" in module and "v1500_ko" in module


def test_unicode_only_component_fx_policy() -> None:
    text = MODULE.read_text(encoding="utf-8")
    assert "PartialEmoji" not in text
    assert "<:" not in text and "<a:" not in text
    assert "discord.SelectOption" in text
    assert "emoji=" not in text  # Select/button emoji fields are intentionally avoided.


def test_latest_patchnotes_and_test_are_overridden() -> None:
    text = MODULE.read_text(encoding="utf-8")
    assert "patch_cmd = bot.get_command('패치노트')" in text
    assert "test_cmd = bot.get_command('테스트')" in text
    assert "v1500_patch_notes" in text
    assert "v1500_latest_test" in text


def test_website_latest_version_and_language_separation() -> None:
    ko = (SITE / "index.html").read_text(encoding="utf-8")
    en = (SITE / "en" / "index.html").read_text(encoding="utf-8")
    assert "v15.0.0" in ko and "v1500-section" in ko
    assert "v15.0.0" in en and "v1500-section" in en
    for path in (SITE / "en").glob("*.html"):
        assert not re.search(r"[가-힣]", path.read_text(encoding="utf-8")), path


def test_website_local_references_exist() -> None:
    missing: list[tuple[Path, str]] = []
    for html in SITE.rglob("*.html"):
        parser = RefParser()
        parser.feed(html.read_text(encoding="utf-8"))
        for ref in parser.refs:
            clean = ref.split("#", 1)[0].split("?", 1)[0]
            if not clean or clean.startswith(("http://", "https://", "mailto:", "javascript:", "data:")):
                continue
            target = (html.parent / clean).resolve()
            if not target.exists():
                missing.append((html, ref))
    assert not missing, missing[:20]
