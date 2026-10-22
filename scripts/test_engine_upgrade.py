#!/usr/bin/env python3
"""用临时学习词库验证两个官方引擎版本之间的升级、保存和回退。"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import time

from test_bionic_daemon import Engine


def files(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob('*') if path.is_file()}


def run(old, new, scheme, keys):
    os.environ['WETYPE_DOUBLE_PIN'] = str(scheme)
    with tempfile.TemporaryDirectory(prefix='wetype-engine-upgrade-') as directory:
        root = Path(directory)
        original = root / 'original'
        (original / 'userdict/v5').mkdir(parents=True)
        (original / 'userdict/user_hot_word').mkdir(parents=True)
        with (root / 'engine.log').open('wb') as log:
            engine = Engine(old, original, False, None, log)
            try:
                engine.command('OPT spans', 'OK')
                words = engine.candidates(keys)
                rank = words.index((len(keys), '拟好'))
                engine.command('S %d' % rank, 'OK')
                time.sleep(.5)
                engine.command('SAVE', 'OK')
            finally:
                engine.close()
            before = files(original)
            assert before, '旧引擎没有保存学习词库'
            upgraded = root / 'upgraded'
            shutil.copytree(original, upgraded)

            engine = Engine(new, upgraded, False, None, log)
            try:
                engine.command('OPT spans', 'OK')
                words = engine.candidates(keys)
                assert words.index((len(keys), '拟好')) < rank, words[:5]
                selected, learned = next((index, word) for index, word in enumerate(words)
                                         if word[0] == len(keys) and word[1] not in ('你好', '拟好')
                                         and all('\u4e00' <= char <= '\u9fff' for char in word[1]))
                engine.command('S %d' % selected, 'OK')
                time.sleep(.5)
                engine.command('SAVE', 'OK')
            finally:
                engine.close()

            engine = Engine(new, upgraded, False, None, log)
            try:
                engine.command('OPT spans', 'OK')
                words = engine.candidates(keys)
                assert (len(keys), '拟好') in words
                assert words.index(learned) < selected, words[:5]
            finally:
                engine.close()
            assert files(original) == before, '升级测试修改了原词库副本'

            # 在另一份副本中回退，确认新版本的学习记录仍能被旧引擎读取。
            rollback = root / 'rollback'
            shutil.copytree(upgraded, rollback)
            engine = Engine(old, rollback, False, None, log)
            try:
                engine.command('OPT spans', 'OK')
                words = engine.candidates(keys)
                assert (len(keys), '拟好') in words
                assert words.index(learned) < selected, words[:5]
            finally:
                engine.close()
    print('PASS %s旧词库升级、继续学习、重启持久化及旧引擎回退' %
          ('全拼' if scheme == 0 else '微软双拼'), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old-engine', type=Path, required=True)
    parser.add_argument('--new-engine', type=Path, required=True)
    args = parser.parse_args()
    for name in ('WETYPE_CLOUD_NATIVE', 'WETYPE_CLOUD_FD', 'WETYPE_SYNC_FD', 'WETYPE_COS_FD'):
        os.environ.pop(name, None)
    run(args.old_engine.resolve(), args.new_engine.resolve(), 0, 'nihao')
    run(args.old_engine.resolve(), args.new_engine.resolve(), 2, 'nihk')


if __name__ == '__main__':
    main()
