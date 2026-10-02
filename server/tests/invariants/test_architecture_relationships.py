import ast
from pathlib import Path

import pytest


@pytest.mark.parametrize("layer", ["api", "services"])
def test_dependency_direction_preserves_repository_and_player_authorities(layer):
    root = Path(__file__).resolve().parents[2] / "app" / layer
    violations = []
    for path in sorted(root.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            modules = []
            if isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            elif isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            for module in modules:
                forbidden = (
                    module in {"sqlite3", "server.app.player.mpd_adapter"}
                    or module.startswith("server.app.player.mpd_adapter.")
                    or (layer == "api" and module.startswith("server.app.repositories"))
                )
                if forbidden:
                    violations.append(f"{path.name}:{node.lineno}: {module}")
    assert not violations, violations
