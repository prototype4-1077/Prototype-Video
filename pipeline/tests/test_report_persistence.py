from __future__ import annotations
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from persist_reports import persist


def run(cwd,*args):
    return subprocess.run(['git',*args],cwd=cwd,text=True,capture_output=True,check=True).stdout


class ReportPersistenceTests(unittest.TestCase):
    def fixture(self, root):
        origin = root / 'origin.git'
        run(root,'init','--bare','--initial-branch=main',str(origin))
        local = root / 'local'
        run(root,'clone',str(origin),str(local))
        for key,value in [('user.name','Fixture'),('user.email','fixture@example.invalid')]:
            run(local,'config',key,value)
        (local / 'source.txt').write_text('1')
        (local / 'report.txt').write_text('initial')
        run(local,'add','source.txt','report.txt')
        run(local,'commit','-m','initial')
        run(local,'push','origin','main')
        return origin,local

    def test_concurrent_report_write_regenerates_against_new_source_without_force(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            origin,local = self.fixture(root)
            other = root / 'other'
            run(root,'clone',str(origin),str(other))
            run(other,'config','user.name','Other')
            run(other,'config','user.email','other@example.invalid')
            (other / 'source.txt').write_text('2')
            (other / 'report.txt').write_text('remote report')
            run(other,'add','source.txt','report.txt')
            run(other,'commit','-m','concurrent source and report')
            run(other,'push','origin','main')
            (local / 'report.txt').write_text('local old-source report')
            def regenerate():
                (local / 'report.txt').write_text('observed '+(local / 'source.txt').read_text())
            result = persist(local,['report.txt'],regenerate=regenerate)
            self.assertTrue(result['pushed'])
            self.assertEqual(result['attempts'],2)
            self.assertEqual(run(root,'--git-dir='+str(origin),'show','main:source.txt'),'2')
            self.assertEqual(run(root,'--git-dir='+str(origin),'show','main:report.txt'),'observed 2')

    def test_unrelated_user_work_is_never_committed_or_discarded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            origin,local = self.fixture(root)
            (local / 'source.txt').write_text('user edit')
            (local / 'report.txt').write_text('new report')
            before = run(root,'--git-dir='+str(origin),'rev-parse','main')
            with self.assertRaisesRegex(RuntimeError,'unrelated work'):
                persist(local,['report.txt'],regenerate=lambda:None)
            self.assertEqual((local / 'source.txt').read_text(),'user edit')
            self.assertEqual(run(root,'--git-dir='+str(origin),'rev-parse','main'),before)


    def test_preexisting_local_commits_cannot_be_smuggled_into_main(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            origin,local = self.fixture(root)
            (local / 'source.txt').write_text('unpublished code')
            run(local,'add','source.txt')
            run(local,'commit','-m','local work')
            (local / 'report.txt').write_text('new report')
            with self.assertRaisesRegex(RuntimeError,'pre-existing local commits'):
                persist(local,['report.txt'],regenerate=lambda:None)
            self.assertEqual(run(root,'--git-dir='+str(origin),'show','main:source.txt'),'1')


if __name__ == '__main__':
    unittest.main()
