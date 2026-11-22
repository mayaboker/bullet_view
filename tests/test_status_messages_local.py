"""Keep status parsing and the View package independent of bullet_msgs."""
import ast
from pathlib import Path
import tomllib

from bullet_view.status_messages import parse_status_text, STATUS_MESSAGE_BY_INDEX


def test_local_status_parser_preserves_context_and_legacy_text():
    parsed = parse_status_text('[07] [t=27.075 f=4809] HOVER: settling')
    assert (parsed.index, parsed.body, parsed.simulation_time_s, parsed.image_sequence) == (
        7, 'HOVER: settling', 27.075, 4809)
    assert parse_status_text('[07] legacy').body == 'legacy'
    assert STATUS_MESSAGE_BY_INDEX[7].description


def test_view_source_and_dependencies_do_not_import_bullet_msgs():
    root = Path(__file__).resolve().parents[1]
    for source in (root / 'src' / 'bullet_view').rglob('*.py'):
        for node in ast.walk(ast.parse(source.read_text())):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith('bullet_msgs'), source
            elif isinstance(node, ast.Import):
                assert all(not item.name.startswith('bullet_msgs') for item in node.names), source
    project = tomllib.loads((root / 'pyproject.toml').read_text())
    assert 'bullet-msgs' not in project['project']['dependencies']
    assert 'bullet-msgs' not in project['tool']['uv']['sources']
