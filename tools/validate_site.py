"""发布前核对静态资源、内容完整性和可执行脚本语法。"""
import argparse
import hashlib
import json
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []
        self.scripts = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for name in ('src', 'href', 'data-original', 'poster'):
            if attrs.get(name):
                self.refs.append(attrs[name])
        if tag == 'script' and not attrs.get('src'):
            self.current = {'type': attrs.get('type', ''), 'body': ''}

    def handle_data(self, data):
        if self.current is not None:
            self.current['body'] += data

    def handle_endtag(self, tag):
        if tag == 'script' and self.current is not None:
            self.scripts.append(self.current)
            self.current = None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('site', type=Path)
    parser.add_argument('--stage', type=Path)
    args = parser.parse_args()
    root = args.site.resolve(strict=True)
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('publication') != {'source_documents': 'local-only', 'raw_mrd_extract': 'local-only'}:
        raise ValueError('发布策略必须明确：原始资料仅留本地')
    actual = set()
    forbidden = {'.pdf', '.xlsx', '.pptx', '.xls', '.ppt', '.docx', '.doc', '.zip'}
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('发布目录禁止软链接：' + str(path))
        if path.is_file():
            name = path.relative_to(root).as_posix()
            if path.suffix.lower() in forbidden or path.name == 'MRD-V0.5核对索引.json':
                raise ValueError('原始资料不得公开：' + name)
            actual.add(name)
    if actual != set(manifest['files']) | {'manifest.json', 'static-validation.json'}:
        raise ValueError('目录与发布清单不一致')
    checked = 0
    for name, expected in manifest['files'].items():
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError(f'不允许软链接或目录越界：{name}')
        data = path.read_bytes()
        if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
            raise ValueError(f'资源与导出记录不一致：{name}')
        checked += 1
    for owner, deps in manifest['dependencies'].items():
        for dep in deps:
            if dep not in manifest['files'] or not (root / dep).is_file():
                raise FileNotFoundError(f'{owner} → {dep}')
    scripts = 0
    for name in manifest['files']:
        if not name.endswith('.html'):
            continue
        path = root / name
        text = path.read_text(encoding='utf-8')
        if '/api/report-text' in text or '/api/attachment-text' in text:
            raise ValueError(f'公开页面残留本地编辑接口：{path.name}')
        doc = Document()
        doc.feed(text)
        for ref in doc.refs:
            url = urlsplit(ref)
            if url.scheme or url.netloc or not url.path:
                continue
            if url.path.startswith('/'):
                raise ValueError(f'不兼容仓库子路径：{path.name}: {ref}')
            target = (path.parent / unquote(url.path)).resolve()
            if not target.is_relative_to(root) or not target.is_file():
                raise FileNotFoundError(f'{path.name}: {ref}')
        for script in doc.scripts:
            if script['type'] == 'application/json':
                json.loads(script['body'])
            elif script['type'] in ('', 'text/javascript', 'application/javascript', 'module'):
                result = subprocess.run(['node', '--input-type=' + ('module' if script['type'] == 'module' else 'commonjs'), '--check'], input=script['body'], text=True, capture_output=True)
                if result.returncode:
                    raise ValueError(f'{path.name} 脚本语法错误：{result.stderr}')
            else:
                continue
            scripts += 1
    if args.stage:
        stage = args.stage.resolve()
        if stage.exists() or stage.is_relative_to(root) or root.is_relative_to(stage):
            raise ValueError('发布目录必须全新，且与源目录隔离')
        for name in [*manifest['files'], 'manifest.json', 'static-validation.json']:
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / name, target)
    print(f'通过：{checked} 个资源、{scripts} 个脚本；失败：0')


if __name__ == '__main__':
    main()
