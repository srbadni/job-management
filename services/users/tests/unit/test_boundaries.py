import ast
import unittest
from pathlib import Path


class ArchitectureTests(unittest.TestCase):
    def test_inner_layers_do_not_import_frameworks_or_outer_layers(self):
        root = Path(__file__).resolve().parents[2] / "app"
        forbidden = (
            "fastapi", "pydantic", "pydantic_settings", "sqlalchemy", "asyncpg", "alembic",
            "aio_pika", "redis", "minio", "urllib3",
            "app.infrastructure", "app.presentation",
        )
        for layer in ("domain", "application"):
            blocked = forbidden + (("app.application",) if layer == "domain" else ())
            for path in (root / layer).rglob("*.py"):
                for node in ast.walk(ast.parse(path.read_text())):
                    if isinstance(node, ast.Import):
                        names = [alias.name for alias in node.names]
                    elif isinstance(node, ast.ImportFrom):
                        names = [f"{node.module}.{alias.name}" for alias in node.names]
                    else:
                        continue
                    for name in names:
                        with self.subTest(path=path.name, dependency=name):
                            self.assertFalse(
                                any(name == item or name.startswith(item + ".") for item in blocked),
                                f"{layer} must not depend on {name}",
                            )
