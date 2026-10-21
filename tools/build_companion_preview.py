"""Build a source preview without credentials, user data or firmware binaries."""
import argparse, hashlib, json, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def source_files(root=ROOT):
    paths=[root/p for p in ['start_companion.bat','start_companion_feature.bat','setup_companion_feature.bat',
        'docs/feature-media-testing.md','docs/media-sync-server.md','server/media_library_server.py',
        'server/hermes_voice_receiver.py','server/requirements-media.txt','server/tests/test_media_server_portable.py',
        'tools/build_companion_preview.py']]
    for path in (root/'tools/compose').rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and not any(p.startswith('.') for p in path.relative_to(root).parts):
            if path.suffix in {'.py','.bat'} or path.name in {'requirements.txt','compose.env.example'}:paths.append(path)
    paths.extend((root/'docs').glob('2026-10-21-*.md'))
    paths.extend((root/'docs/research').glob('2026-10-21-*.md'))
    return sorted(set(paths))

def build(destination,root=ROOT):
    destination=Path(destination);files=source_files(root);manifest={}
    for path in files:
        if not path.is_file():raise ValueError(f'Missing preview source: {path.relative_to(root)}')
        manifest[path.relative_to(root).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:archive.write(path,path.relative_to(root))
        archive.writestr('preview-manifest.json',json.dumps({'format':'source-preview','files':manifest},indent=2))
    with zipfile.ZipFile(destination) as archive:
        for name,digest in manifest.items():
            if hashlib.sha256(archive.read(name)).hexdigest()!=digest:raise ValueError('Preview verification failed')
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();manifest=build(args.output)
    print(json.dumps({'source_files':len(manifest),'sha256_verified':True,'credentials_or_data_included':False}))
