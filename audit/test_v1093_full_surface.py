from __future__ import annotations

import ast
import json
import pathlib
import re
from collections import Counter, defaultdict

try:
    import regex as uregex
except Exception:  # pragma: no cover
    uregex = None

ROOT = pathlib.Path(__file__).resolve().parents[1]
COMMANDS = ROOT / "apocalypse_bot" / "commands"


def dotted_name(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def const_str(node: ast.AST | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def literal_sequence_len(node: ast.AST | None) -> int | None:
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return len(node.elts)
    return None


def unicode_emoji_ok(value: str) -> bool:
    if not value:
        return True
    if re.fullmatch(r"<a?:[A-Za-z0-9_]+:\d+>", value):
        return True
    if uregex is None:
        return value not in {"🀙", "🂠", "¼", "½", "✖️2"}
    pict = uregex.compile(
        r"(?:\p{Emoji_Presentation}|\p{Emoji}\uFE0F)"
        r"(?:\p{Emoji_Modifier})?"
        r"(?:\u200D(?:\p{Emoji_Presentation}|\p{Emoji}\uFE0F)(?:\p{Emoji_Modifier})?)*"
    )
    keycap = uregex.compile(r"[0-9#*]\uFE0F?\u20E3")
    flag = uregex.compile(r"[\U0001F1E6-\U0001F1FF]{2}")
    return bool(pict.fullmatch(value) or keycap.fullmatch(value) or flag.fullmatch(value))


def scan() -> dict[str, object]:
    violations: list[dict[str, object]] = []
    diagnostics: dict[str, object] = {}
    commands: list[dict[str, object]] = []
    py_files = sorted(ROOT.rglob("*.py"))
    syntax_errors: list[str] = []
    ui_calls = Counter()
    literal_options = 0

    def fail(path: pathlib.Path, line: int, kind: str, detail: object) -> None:
        violations.append({"file": str(path.relative_to(ROOT)), "line": line, "kind": kind, "detail": detail})

    for path in py_files:
        try:
            source = path.read_text("utf-8")
            tree = ast.parse(source, filename=str(path))
            compile(source, str(path), "exec")
        except Exception as exc:
            syntax_errors.append(f"{path.relative_to(ROOT)}: {exc}")
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    if not isinstance(dec, ast.Call):
                        continue
                    dname = dotted_name(dec.func)
                    if dname.rsplit(".", 1)[-1] not in {"command", "hybrid_command", "group", "hybrid_group"}:
                        continue
                    name = node.name
                    aliases: list[str] = []
                    description = ""
                    for kw in dec.keywords:
                        if kw.arg == "name" and const_str(kw.value) is not None:
                            name = const_str(kw.value) or ""
                        elif kw.arg == "aliases" and isinstance(kw.value, (ast.List, ast.Tuple)):
                            aliases = [x.value for x in kw.value.elts if isinstance(x, ast.Constant) and isinstance(x.value, str)]
                        elif kw.arg in {"help", "brief", "description"} and const_str(kw.value) is not None:
                            description = const_str(kw.value) or ""
                    commands.append({"name": name, "aliases": aliases, "description": description, "decorator": dname, "file": str(path.relative_to(ROOT)), "line": node.lineno})
                    if not name or name != name.strip() or any(ch.isspace() for ch in name):
                        fail(path, node.lineno, "command_name", repr(name))
                    if dname.endswith(("hybrid_command", "hybrid_group")) and len(name) > 32:
                        fail(path, node.lineno, "hybrid_command_name_too_long", {"name": name, "length": len(name)})
                    for alias in aliases:
                        if not alias or alias != alias.strip() or any(ch.isspace() for ch in alias):
                            fail(path, node.lineno, "command_alias", repr(alias))

            if not isinstance(node, ast.Call):
                continue
            name = dotted_name(node.func)
            tail = name.rsplit(".", 1)[-1]
            kws = {kw.arg: kw.value for kw in node.keywords if kw.arg}

            if tail == "SelectOption":
                ui_calls["SelectOption"] += 1
                literal_options += 1
                limits = {"label": 100, "value": 100, "description": 100}
                for key, limit in limits.items():
                    value = const_str(kws.get(key))
                    if value is not None and len(value) > limit:
                        fail(path, node.lineno, f"select_option_{key}_too_long", {"length": len(value), "limit": limit, "value": value[:120]})
                emoji = const_str(kws.get("emoji"))
                if emoji is not None and not unicode_emoji_ok(emoji):
                    fail(path, node.lineno, "invalid_select_option_emoji", emoji)

            if tail in {"Select", "select"}:
                ui_calls["Select"] += 1
                count = literal_sequence_len(kws.get("options"))
                if count is not None and count > 25:
                    fail(path, node.lineno, "select_too_many_options", {"count": count, "limit": 25})
                placeholder = const_str(kws.get("placeholder"))
                if placeholder is not None and len(placeholder) > 150:
                    fail(path, node.lineno, "select_placeholder_too_long", {"length": len(placeholder), "limit": 150})
                custom_id = const_str(kws.get("custom_id"))
                if custom_id is not None and len(custom_id) > 100:
                    fail(path, node.lineno, "select_custom_id_too_long", {"length": len(custom_id), "limit": 100})

            if tail in {"Button", "button"}:
                ui_calls["Button"] += 1
                label = const_str(kws.get("label"))
                if label is not None and len(label) > 80:
                    fail(path, node.lineno, "button_label_too_long", {"length": len(label), "limit": 80})
                custom_id = const_str(kws.get("custom_id"))
                if custom_id is not None and len(custom_id) > 100:
                    fail(path, node.lineno, "button_custom_id_too_long", {"length": len(custom_id), "limit": 100})
                emoji = const_str(kws.get("emoji"))
                if emoji is not None and not unicode_emoji_ok(emoji):
                    fail(path, node.lineno, "invalid_button_emoji", emoji)

            if tail == "TextInput":
                ui_calls["TextInput"] += 1
                label = const_str(kws.get("label"))
                placeholder = const_str(kws.get("placeholder"))
                custom_id = const_str(kws.get("custom_id"))
                if label is not None and len(label) > 45:
                    fail(path, node.lineno, "text_input_label_too_long", {"length": len(label), "limit": 45})
                if placeholder is not None and len(placeholder) > 100:
                    fail(path, node.lineno, "text_input_placeholder_too_long", {"length": len(placeholder), "limit": 100})
                if custom_id is not None and len(custom_id) > 100:
                    fail(path, node.lineno, "text_input_custom_id_too_long", {"length": len(custom_id), "limit": 100})

            # Literal modal titles passed to Modal(...) or super().__init__(title=...).
            if tail in {"Modal", "__init__"}:
                title = const_str(kws.get("title"))
                if title is not None and len(title) > 45:
                    fail(path, node.lineno, "modal_title_too_long", {"length": len(title), "limit": 45})

    access: defaultdict[str, list[str]] = defaultdict(list)
    missing_descriptions = 0
    for row in commands:
        if not row["description"]:
            missing_descriptions += 1
        for n in [row["name"], *row["aliases"]]:
            access[str(n).casefold()].append(f"{row['file']}:{row['line']}")
    duplicates = {k: v for k, v in access.items() if len(v) > 1}

    # Required v10.9.3 guards and final registration order.
    v1000 = (COMMANDS / "v1000_global_survivor.py").read_text("utf-8")
    v711 = (COMMANDS / "v711_cute_interactions.py").read_text("utf-8")
    v1092 = (COMMANDS / "v1092_visual_status_horserace.py").read_text("utf-8")
    core = (ROOT / "apocalypse_bot" / "core" / "bot.py").read_text("utf-8")
    required = {
        "emoji_sanitizer": "V1093_COMPONENT_EMOJI_SANITIZER = True" in v1000,
        "textinput_skip": "is_text_input" in v1000 and "if not is_text_input" in v1000,
        "catalog_early_ack": "V1093_COMMAND_CATALOG_FAST_ACK = True" in v711 and "def _ack_component" in v711,
        "catalog_cache": "_COMMAND_INDEX_CACHE" in v711 and "def _command_index" in v711,
        "unknown_interaction_guard": "10062" in v711,
        "actual_discord_avatar": "display_avatar.read()" in v1092 and "avatar_bytes=await _avatar_bytes(ctx.author)" in v1092,
        "registration_order": "register_v1093_command_ui_audit" in core and core.index("register_v1093_command_ui_audit") < core.index("synchronize_all_english_aliases"),
    }
    for key, ok in required.items():
        if not ok:
            violations.append({"file": "required", "line": 0, "kind": key, "detail": "missing"})

    diagnostics.update({
        "python_files": len(py_files),
        "command_declarations": len(commands),
        "static_access_names": len(access),
        "static_duplicate_access_names": len(duplicates),
        "static_duplicate_examples": dict(list(sorted(duplicates.items()))[:20]),
        "missing_literal_descriptions": missing_descriptions,
        "literal_select_options": literal_options,
        "ui_calls": dict(ui_calls),
        "required_guards": required,
        "syntax_errors": syntax_errors,
    })

    return {
        "version": "10.9.3",
        "scope": "all Python commands and literal Discord UI constraints",
        "passed": not violations and not syntax_errors,
        "violations": violations,
        "diagnostics": diagnostics,
    }


if __name__ == "__main__":
    report = scan()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed"] else 1)
