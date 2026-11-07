import ast
from pathlib import Path


def test_primary_gui_does_not_import_optional_companion_decoder():
    gui_path = Path(__file__).parents[1] / "src" / "mirage_link" / "gui.py"
    tree = ast.parse(gui_path.read_text(encoding="utf-8"))

    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])

    assert "av" not in imported_roots
    assert "PIL" not in imported_roots
