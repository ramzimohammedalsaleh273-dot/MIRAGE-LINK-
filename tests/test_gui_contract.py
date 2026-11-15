"""Static GUI contract tests that do not require an interactive display."""
import ast
from pathlib import Path


def test_wifi_pairing_code_prompt_is_masked():
    source = Path("src/mirage_link/gui.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "simpledialog"
        and node.func.attr == "askstring"
    ]

    assert len(calls) == 1
    options = {keyword.arg: keyword.value for keyword in calls[0].keywords}
    assert ast.literal_eval(options["show"]) == "*"
