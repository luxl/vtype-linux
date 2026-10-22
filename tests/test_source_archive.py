"""核对打包使用当前源码，包含新增文件并排除缓存与已删除文件。"""
import importlib.util
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    'export_source', Path(__file__).resolve().parents[1] / 'scripts/export_source.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SourceArchive(unittest.TestCase):
    def test_worktree_and_new_files_without_build_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            (root / '.gitignore').write_text('.deps/\nbuild/\n')
            (root / 'engine.c').write_text('old code\n')
            (root / 'removed.patch').write_text('old patch\n')
            subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
            (root / 'engine.c').write_text('current code\n')
            (root / 'new_test.py').write_text('new regression\n')
            (root / 'removed.patch').unlink()
            (root / '.deps').mkdir()
            (root / '.deps/private-data').write_text('not source')
            (root / 'build').mkdir()
            (root / 'build/generated').write_text('not source')
            output = root / '.deps/source.tar'
            digest = module.export_source(root, output)
            self.assertEqual(digest, module.export_source(root, output))
            with tarfile.open(output) as archive:
                self.assertEqual(set(archive.getnames()), {
                    'vtype-linux/.gitignore', 'vtype-linux/engine.c',
                    'vtype-linux/new_test.py'})
                self.assertEqual(archive.extractfile('vtype-linux/engine.c').read(), b'current code\n')
                self.assertEqual(archive.extractfile('vtype-linux/new_test.py').read(), b'new regression\n')

    def test_external_link_is_refused_without_replacing_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'repo'
            root.mkdir()
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            outside = Path(directory) / 'outside'
            outside.write_text('private')
            (root / 'link').symlink_to(outside)
            output = Path(directory) / 'source.tar'
            output.write_bytes(b'keep previous archive')
            with self.assertRaises(ValueError):
                module.export_source(root, output)
            self.assertEqual(output.read_bytes(), b'keep previous archive')


if __name__ == '__main__':
    unittest.main()
