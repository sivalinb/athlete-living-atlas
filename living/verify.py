"""Verify deployable asset references, synthetic provenance, and screenshot checksums."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
from .export import ROOT


def verify():
    html=(ROOT/'dist/index.html').read_text()
    for ref in re.findall(r'(?:src|href)="([^"]+)"',html):
        if ':' not in ref and not ref.startswith(('#','./')):
            assert (ROOT/'dist'/ref).is_file(), ref
    manifest=json.loads((ROOT/'dist/demo.json').read_text())
    assert manifest['synthetic'] is True
    gallery=ROOT/'docs/screenshots/manifest.json'
    if gallery.exists():
        for item in json.loads(gallery.read_text())['images']:
            path=ROOT/item['path']
            assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256'],item['path']
    names=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    for name in filter(None,names):
        assert not name.startswith(('.local/','.env','work/')),name
        assert Path(name).suffix not in {'.sqlite','.db','.zip','.gpx','.xml','.pem','.key'},name
    print('Static references, synthetic scope, tracked paths and screenshot checksums verified.')

if __name__=='__main__':verify()
