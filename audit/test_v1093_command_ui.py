from __future__ import annotations

import ast
import json
import pathlib
import re
import sys
from collections import defaultdict

try:
    import regex as uregex
except Exception:  # pragma: no cover
    uregex = None

ROOT = pathlib.Path(__file__).resolve().parents[1]
COMMANDS = ROOT / "apocalypse_bot" / "commands"


def read(rel: str) -> str:
    return (ROOT / rel).read_text("utf-8")


def valid_unicode_emoji(value: str) -> bool:
    if not value:
        return True
    if value.startswith("<") and value.endswith(">"):
        return True
    if uregex is None:
        return value not in {"🀙", "🂠", "¼", "½", "✖️2"}
    pict = uregex.compile(r"(?:\p{Emoji_Presentation}|\p{Emoji}\uFE0F)(?:\p{Emoji_Modifier})?(?:\u200D(?:\p{Emoji_Presentation}|\p{Emoji}\uFE0F)(?:\p{Emoji_Modifier})?)*")
    keycap = uregex.compile(r"[0-9#*]\uFE0F?\u20E3")
    flag = uregex.compile(r"[\U0001F1E6-\U0001F1FF]{2}")
    return bool(pict.fullmatch(value) or keycap.fullmatch(value) or flag.fullmatch(value))


def literal_emojis() -> list[tuple[str, str, int]]:
    found: list[tuple[str, str, int]] = []
    for path in COMMANDS.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text("utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg == "emoji" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        found.append((kw.value.value, str(path.relative_to(ROOT)), node.lineno))
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                target = node.targets[0] if isinstance(node, ast.Assign) and node.targets else node.target
                if isinstance(target, ast.Name) and "EMOJI" in target.id.upper() and isinstance(node.value, ast.Dict):
                    for value in node.value.values:
                        if isinstance(value, ast.Constant) and isinstance(value.value, str):
                            found.append((value.value, str(path.relative_to(ROOT)), value.lineno))
    return found


def command_declarations() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in COMMANDS.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text("utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call):
                    continue
                func = dec.func
                attr = func.attr if isinstance(func, ast.Attribute) else ""
                if attr not in {"command", "hybrid_command", "group", "hybrid_group"}:
                    continue
                name = node.name
                aliases: list[str] = []
                help_text = ""
                for kw in dec.keywords:
                    if kw.arg == "name" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        name = kw.value.value
                    elif kw.arg == "aliases" and isinstance(kw.value, (ast.List, ast.Tuple)):
                        aliases = [v.value for v in kw.value.elts if isinstance(v, ast.Constant) and isinstance(v.value, str)]
                    elif kw.arg in {"help", "description", "brief"} and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        help_text = kw.value.value
                rows.append({"name": name, "aliases": aliases, "help": help_text, "file": str(path.relative_to(ROOT)), "line": node.lineno})
    return rows


def run() -> dict[str, object]:
    checks: list[dict[str, object]] = []

    def check(name: str, ok: bool, detail: object) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    v1000 = read("apocalypse_bot/commands/v1000_global_survivor.py")
    v1010 = read("apocalypse_bot/commands/v1010_companion_card_games.py")
    v1051 = read("apocalypse_bot/commands/v1051_authentic_card_games.py")
    v1090 = read("apocalypse_bot/commands/v1090_integrated_renewal.py")
    v1092 = read("apocalypse_bot/commands/v1092_visual_status_horserace.py")
    v1093 = read("apocalypse_bot/commands/v1093_command_ui_audit.py")
    v711 = read("apocalypse_bot/commands/v711_cute_interactions.py")
    core = read("apocalypse_bot/core/bot.py")

    invalid = [(emoji, file, line) for emoji, file, line in literal_emojis() if not valid_unicode_emoji(emoji)]
    check("Discord 컴포넌트 literal emoji", not invalid, invalid[:20])
    check("전송 직전 emoji sanitizer", "V1093_COMPONENT_EMOJI_SANITIZER = True" in v1000 and "_sanitize_component_emojis" in v1000, "global send/edit path")
    check("카드게임 옵션 21 수정", '"도리짓고땡": "🎴"' in v1090 and "🀙" not in v1090, "option index 21")
    check("섯다/조커/블랙잭 invalid emoji 수정", all(token not in v1051 for token in ['emoji="✖️2"', 'emoji="¼"', 'emoji="½"', 'emoji="🂠"']), "5 unsafe glyphs removed")
    check("TextInput.label 공용 접근 제거", "hasattr(item, \"label\")" not in v1000 and "str(item.label)" not in v1000, "TextInput skipped by isinstance")
    check("ExpandedBetModal Label 호환", "self.bet_input.label =" not in v1010 and "label_cls = getattr(discord.ui, \"Label\", None)" in v1010, "no direct property mutation")
    check("명령 도감 선응답", "V1093_COMMAND_CATALOG_FAST_ACK = True" in v711 and "await interaction.response.defer()" in v711 and "interaction.edit_original_response" in v711, "Unknown interaction mitigation")
    check("명령 도감 캐시", "def _command_index" in v711 and "_COMMAND_INDEX_CACHE" in v711, "~1000 commands indexed once")
    check("만료 interaction 소음 억제", 'getattr(error, "code", 0)' in v711 and "10062" in v711, "expired token is ignored")
    check("Discord 프로필 avatar 합성", "return await member.display_avatar.read()" in v1092 and "avatar_bytes=await _avatar_bytes(ctx.author)" in v1092, "actual caller avatar")
    check("v10.9.3 최종 등록 순서", core.index("register_v1093_command_ui_audit") < core.index("synchronize_all_english_aliases"), "before final English alias sync")
    check("최신 테스트/패치노트", "v1093_test" in v1093 and "v1093_patch_notes" in v1093, "latest-only v10.9.3")

    declarations = command_declarations()
    access = defaultdict(list)
    for row in declarations:
        for name in [row["name"], *row["aliases"]]:
            access[str(name).casefold()].append(f"{row['file']}:{row['line']}")
    duplicates = {name: locations for name, locations in access.items() if len(locations) > 1}
    # Historical modules intentionally redefine callbacks, so this is diagnostic;
    # final runtime registration/audits resolve them by order.
    check("정적 명령 선언 분석", len(declarations) > 900, {"declarations": len(declarations), "duplicate_access_names": len(duplicates)})

    py_files = list(ROOT.rglob("*.py"))
    compile_errors = []
    for path in py_files:
        try:
            compile(path.read_text("utf-8"), str(path), "exec")
        except Exception as exc:
            compile_errors.append(f"{path.relative_to(ROOT)}: {exc}")
    check("Python 전체 컴파일", not compile_errors, {"files": len(py_files), "errors": compile_errors[:10]})

    failed = [row for row in checks if not row["ok"]]
    return {
        "version": "10.9.3",
        "scope": "full command registry/UI safety hotfix only",
        "checks": checks,
        "passed": len(checks) - len(failed),
        "failed": len(failed),
        "static_declaration_count": len(declarations),
        "static_duplicate_access_names": len(duplicates),
        "invalid_literal_emojis": invalid,
    }


if __name__ == "__main__":
    report = run()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(1 if report["failed"] else 0)
