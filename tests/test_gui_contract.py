"""Static GUI contract tests that do not require an interactive display."""
import ast
from pathlib import Path


def test_every_wifi_pairing_code_prompt_is_masked():
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

    code_prompts = [
        call for call in calls
        if call.args
        and isinstance(call.args[0], ast.Constant)
        and "رمز الاقتران" in str(call.args[0].value)
    ]
    assert len(code_prompts) == 2
    for call in code_prompts:
        options = {keyword.arg: keyword.value for keyword in call.keywords}
        assert ast.literal_eval(options["show"]) == "*"


def test_manual_wifi_fallback_is_explicit_and_uses_safe_engine_path():
    source = Path("src/mirage_link/gui.py").read_text(encoding="utf-8")
    assert "def _manual_wifi_fallback(self):" in source
    assert "askyesnocancel" in source
    assert "wifi_connect_manual" in source
    assert "لن يُستخدم USB" in source


def test_wifi_discovery_status_uses_neutral_wording_for_empty_results():
    source = Path("src/mirage_link/gui.py").read_text(encoding="utf-8")
    assert "لم تُكتشف خدمة هاتف عبر Wi-Fi:" in source
    assert "تعذر فحص خدمات Wi-Fi عبر mDNS:" not in source
