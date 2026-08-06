from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "apocalypse_bot" / "commands" / "v1000_global_survivor.py"


def _load_translate_view():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    wanted = {"_sanitize_ui_emoji", "_sanitize_component_emojis", "_translate_view"}
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = {target.id for target in node.targets if isinstance(target, ast.Name)}
            if "_UI_EMOJI_REPLACEMENTS" in names:
                nodes.append(node)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "_UI_EMOJI_REPLACEMENTS":
            nodes.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in wanted:
            nodes.append(node)
    code = "from __future__ import annotations\n" + "\n\n".join(ast.unparse(node) for node in nodes)

    class TextInput:
        def __init__(self, placeholder="Stake"):
            self.placeholder = placeholder
            self.options = None

        @property
        def label(self):
            raise AssertionError("deprecated TextInput.label was read")

        @label.setter
        def label(self, value):
            raise AssertionError("deprecated TextInput.label was written")

    class Button:
        def __init__(self, label="Create"):
            self.label = label
            self.placeholder = None
            self.options = None

    class Label:
        def __init__(self, text="Stake", description="No cap", component=None):
            self.text = text
            self.description = description
            self.component = component

    fake_discord = SimpleNamespace(ui=SimpleNamespace(TextInput=TextInput, Label=Label))
    fake_commands = SimpleNamespace(Bot=object)

    def translate_text(text, locale, bot=None):
        return f"{locale}:{text}"

    namespace = {
        "Any": Any,
        "Optional": Optional,
        "Mapping": dict,
        "commands": fake_commands,
        "discord": fake_discord,
        "translate_text": translate_text,
    }
    exec(code, namespace)
    return namespace["_translate_view"], TextInput, Button, Label


def test_textinput_deprecated_label_is_never_touched() -> None:
    translate_view, TextInput, Button, _Label = _load_translate_view()
    input_item = TextInput()
    button = Button()
    view = SimpleNamespace(children=[input_item, button])
    result = translate_view(view, "en", None)
    assert result is view
    assert input_item.placeholder == "en:Stake"
    assert button.label == "en:Create"


def test_modern_label_text_and_nested_input_are_translated() -> None:
    translate_view, TextInput, _Button, Label = _load_translate_view()
    input_item = TextInput("Enter stake")
    label = Label(component=input_item)
    view = SimpleNamespace(children=[label])
    translate_view(view, "ko", None)
    assert label.text == "ko:Stake"
    assert label.description == "ko:No cap"
    assert input_item.placeholder == "ko:Enter stake"
