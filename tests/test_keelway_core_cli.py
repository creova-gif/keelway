import io
from contextlib import redirect_stdout,redirect_stderr
from pathlib import Path
import tempfile
import json
import unittest
from keelway_core.cli import main

class CLIBehaviors(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.project=self.root/'project';self.project.mkdir()
        (self.project/'x.py').write_text('print(1)\n')
        self.db=str(self.root/'db.sqlite')
    def tearDown(self):self.temp.cleanup()
    def run_cli(self,*args):
        with redirect_stdout(io.StringIO()) as o,redirect_stderr(io.StringIO()) as e:
            rc=main(['--database',self.db,*args])
        return rc,o.getvalue(),e.getvalue()
    def test_doctor(self):
        rc,o,e=self.run_cli('doctor')
        self.assertEqual(rc,0);self.assertFalse(json.loads(o)['enterprise_security_qualified'])
    def test_create(self):
        rc,o,e=self.run_cli('new',str(self.project),'Goal')
        self.assertEqual(rc,0);self.assertTrue(json.loads(o)['task_id'])
    def test_unknown_task(self):
        rc,o,e=self.run_cli('show','bad')
        self.assertEqual(rc,2);self.assertIn('unknown task',e)
    def test_approval_requires_confirm(self):
        rc,o,e=self.run_cli('approve','bad','0'*64,'--approver','human')
        self.assertEqual(rc,2);self.assertIn('--confirm',e)
    def test_apply_requires_confirm(self):
        rc,o,e=self.run_cli('apply','bad')
        self.assertEqual(rc,2);self.assertIn('--confirm',e)
    def test_unsandboxed_execution_denied_by_default(self):
        rc,o,e=self.run_cli('verify','bad','--','python','-V')
        self.assertEqual(rc,2);self.assertIn('UNSANDBOXED',e)
    def test_local_fixture_is_explicit_not_model(self):
        rc,o,e=self.run_cli('suggest','hello','--provider','fixture')
        self.assertEqual(rc,0);self.assertEqual(json.loads(o)['provider'],'fixture')

if __name__=='__main__':unittest.main()
