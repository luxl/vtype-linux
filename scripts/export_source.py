#!/usr/bin/env python3
"""导出当前 Git 工作区的源码，供本地打包使用；包含尚未提交的修改。"""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile


def export_source(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    names = subprocess.check_output(
        ['git', '-C', str(root), 'ls-files', '--cached', '--others',
         '--exclude-standard', '-z']).split(b'\0')
    files = []
    forbidden = {'.git', '.deps', 'private-state', 'research', 'downloads',
                 'logs', 'runtime', 'AppDir', 'node_modules', '__pycache__'}
    for raw in sorted(set(names)):
        if not raw:
            continue
        name = Path(os.fsdecode(raw))
        path = root / name
        if path == output or (not path.exists() and not path.is_symlink()):
            continue
        if name.is_absolute() or '..' in name.parts or forbidden.intersection(name.parts):
            raise ValueError('拒绝导出非源码路径：' + str(name))
        if path.is_symlink() and not path.resolve().is_relative_to(root):
            raise ValueError('拒绝导出指向仓库外的链接：' + str(name))
        if not path.is_file() and not path.is_symlink():
            raise ValueError('不支持的源码文件类型：' + str(name))
        files.append((name, path))
    if not files:
        raise ValueError('没有可导出的源码')

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            with tarfile.open(fileobj=stream, mode='w', format=tarfile.PAX_FORMAT) as archive:
                for name, path in files:
                    info = archive.gettarinfo(str(path), arcname='vtype-linux/' + name.as_posix())
                    # 文件时间和本机用户信息不影响源码快照的校验值。
                    info.uid = info.gid = info.mtime = 0
                    info.uname = info.gname = ''
                    info.mode = 0o755 if info.mode & 0o111 else 0o644
                    if info.isfile():
                        with path.open('rb') as source:
                            archive.addfile(info, source)
                    else:
                        archive.addfile(info)
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(export_source(Path(__file__).resolve().parents[1], args.output))


if __name__ == '__main__':
    main()
