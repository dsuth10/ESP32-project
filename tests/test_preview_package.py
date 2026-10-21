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
    for name in ['tools/compose/compose.env','tools/compose/companion.log','.local/private.txt','tools/compose/.venv/private.py','tools/compose/private.sqlite3']:
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(private_marker)
    output=tmp_path/'preview.zip'
    manifest=builder.build(output,tmp_path)
    with zipfile.ZipFile(output) as archive:
        names=archive.namelist()
        assert 'start_companion_feature.bat' in names
        assert 'preview-manifest.json' in names
        assert all(private_marker.encode() not in archive.read(name) for name in names)
        assert not any(name.endswith(('.env','.log','.sqlite3')) or '/.venv/' in name or name.startswith('.local/') for name in names)
    assert manifest
