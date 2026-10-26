import importlib.util
from pathlib import Path
import zipfile
import uuid
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('preview_builder',ROOT/'tools/build_companion_preview.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


def test_preview_source_package_excludes_private_configuration_and_data(tmp_path):
    # Copy only the builder's declared source inputs into a synthetic tree.
    for path in builder.source_files(ROOT):
        target=tmp_path/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(path.read_bytes())
    private_marker='must-not-package-'+uuid.uuid4().hex
    for name in ['tools/compose/compose.env','tools/compose/companion.log','.local/private.txt','.local/teaching-board-candidate/lesson/board-requests/request.json','tools/compose/.venv/private.py','tools/compose/private.sqlite3','docs/research/private-consultation.md','.agents/skills/private.py']:
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(private_marker)
    output=tmp_path/'preview.zip'
    manifest=builder.build(output,tmp_path)
    with zipfile.ZipFile(output) as archive:
        names=archive.namelist()
        assert 'start_companion_feature.bat' in names
        assert 'tools/compose/run_teaching_board_candidate.ps1' in names
        assert 'tools/compose/setup_teaching_board_candidate.ps1' in names
        assert 'tools/compose/requirements-board.txt' in names
        assert 'tools/compose/board_recovery.py' in names
        assert 'tools/compose/examples/teaching-board-illustrative-rainfall.json' in names
        assert 'docs/2026-10-25-teaching-board-agent-candidate.md' in names
        for guide in ('docs/2026-10-26-school-arrival-guide.md',
                      'docs/2026-10-26-linux-hermes-school-handoff.md',
                      'docs/2026-10-26-teaching-board-request-recovery.md'):
            if (ROOT/guide).is_file():
                assert guide in names
        assert 'preview-manifest.json' in names
        assert all(private_marker.encode() not in archive.read(name) for name in names)
        assert not any(name.endswith(('.env','.log','.sqlite3')) or '/.venv/' in name or name.startswith('.local/') for name in names)
    assert not any(name.startswith(('docs/research/', '.agents/')) for name in names)
    assert manifest
