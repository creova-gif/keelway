import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from keelway_core.engine import Engine, WorkflowError, digest, canonical, safe_target
from keelway_core.provider import FixtureProvider, OllamaLocal

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project = self.root/'project';self.project.mkdir()
        self.file = self.project/'hello.py';self.file.write_text('print("before")\n')
        self.engine = Engine(str(self.root/'store.sqlite'))
        self.tid = self.engine.create(str(self.project),'Update example')

    def tearDown(self):
        self.engine.close();self.tmp.cleanup()

    def draft(self, content=b'print("after")\n'):
        return self.engine.propose(self.tid,'hello.py',content)

    def approve(self, plan=None):
        plan = plan or self.engine.proposal(self.tid)
        self.engine.approve(self.tid,plan['plan_digest'],'developer')

    def test_initial_state(self): self.assertEqual(self.engine.task(self.tid)['state'],'CREATED')
    def test_event_on_create(self): self.assertEqual(self.engine.audit(self.tid)['events'],1)
    def test_no_empty_goal(self):
        with self.assertRaises(WorkflowError): self.engine.create(str(self.project),'  ')
    def test_proposal_state(self): self.assertEqual(self.draft()['state'],'AWAITING_APPROVAL')
    def test_proposal_repeat_denied(self):
        self.draft()
        with self.assertRaises(WorkflowError): self.draft()
    def test_no_apply_without_approve(self):
        self.draft()
        with self.assertRaises(WorkflowError): self.engine.apply(self.tid)
    def test_wrong_digest_rejected(self):
        self.draft()
        with self.assertRaises(WorkflowError): self.engine.approve(self.tid,'0'*64,'developer')
    def test_empty_approver_rejected(self):
        self.draft()
        with self.assertRaises(WorkflowError): self.engine.approve(self.tid,self.engine.proposal(self.tid)['plan_digest'],'')
    def test_exact_digest_approve(self):
        self.draft();self.approve();self.assertEqual(self.engine.task(self.tid)['state'],'APPROVED')
    def test_approved_apply_changes_real_file(self):
        self.draft();self.approve();result=self.engine.apply(self.tid)
        self.assertEqual(self.file.read_text(),'print("after")\n')
        self.assertEqual(result['state'],'VERIFYING')
    def test_original_mode_preserved(self):
        self.file.chmod(0o640);self.draft();self.approve();self.engine.apply(self.tid)
        self.assertEqual(self.file.stat().st_mode&0o777,0o640)
    def test_stale_source_denied(self):
        self.draft();self.approve();self.file.write_text('changed externally')
        with self.assertRaises(WorkflowError): self.engine.apply(self.tid)
        self.assertEqual(self.file.read_text(),'changed externally')
    def test_apply_second_time_denied(self):
        self.draft();self.approve();self.engine.apply(self.tid)
        with self.assertRaises(WorkflowError):self.engine.apply(self.tid)
    def test_verify_completion(self):
        self.draft();self.approve();self.engine.apply(self.tid)
        out=self.engine.mark_verified(self.tid,['python','-m','py_compile','hello.py'],0,'a'*64,'fixture-test')
        self.assertEqual(out['state'],'COMPLETED')
    def test_verify_failure(self):
        self.draft();self.approve();self.engine.apply(self.tid)
        out=self.engine.mark_verified(self.tid,['python','-m','py_compile','hello.py'],1,'a'*64,'fixture-test')
        self.assertEqual(out['state'],'FAILED')
    def test_verify_before_apply_denied(self):
        self.draft()
        with self.assertRaises(WorkflowError):self.engine.mark_verified(self.tid,['python'],0,'a'*64,'x')
    def test_cancel(self):
        self.engine.cancel(self.tid);self.assertEqual(self.engine.task(self.tid)['state'],'CANCELLED')
    def test_cancel_terminal_denied(self):
        self.engine.cancel(self.tid)
        with self.assertRaises(WorkflowError):self.engine.cancel(self.tid)
    def test_chain_integrity(self):
        self.draft();self.approve();self.engine.apply(self.tid)
        self.assertTrue(self.engine.audit(self.tid)['ok'])
    def test_chain_tamper_detected(self):
        self.draft()
        with self.engine.db:
            self.engine.db.execute("UPDATE events SET payload_json=? WHERE task_id=? AND kind='PROPOSED'", ('{}',self.tid))
        self.assertFalse(self.engine.audit(self.tid)['ok'])
    def test_unknown_task(self):
        with self.assertRaises(WorkflowError):self.engine.task('missing')
    def test_reopen_persistence(self):
        self.draft();self.engine.close();self.engine=Engine(str(self.root/'store.sqlite'))
        self.assertEqual(self.engine.task(self.tid)['state'],'AWAITING_APPROVAL')
    def test_path_parent_escape_denied(self):
        with self.assertRaises(WorkflowError):safe_target(str(self.project),'../store.sqlite')
    def test_path_absolute_denied(self):
        with self.assertRaises(WorkflowError):safe_target(str(self.project),str(self.file))
    def test_path_dot_denied(self):
        with self.assertRaises(WorkflowError):safe_target(str(self.project),'./hello.py')
    def test_missing_file_denied(self):
        with self.assertRaises(WorkflowError):safe_target(str(self.project),'missing.py')
    def test_symlink_denied(self):
        link=self.project/'alias.py';link.symlink_to(self.file)
        with self.assertRaises(WorkflowError):safe_target(str(self.project),'alias.py')
    def test_symlink_parent_denied(self):
        sub=self.project/'directory';sub.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(WorkflowError):safe_target(str(self.project),'directory/store.sqlite')
    def test_directory_denied(self):
        (self.project/'subdir').mkdir()
        with self.assertRaises(WorkflowError):safe_target(str(self.project),'subdir')
    def test_events_not_cryptographically_authenticated(self):
        self.assertIn('NOT signed',self.engine.audit(self.tid)['warning'])
    def test_fixture_provider(self):
        x=FixtureProvider().complete('hello')
        self.assertEqual(x.text,'FIXTURE: hello');self.assertTrue(x.offline)
    def test_nonloopback_ollama_rejected(self):
        with self.assertRaises(ValueError):OllamaLocal('model','http://example.com/api/chat')
    def test_canonical_digest_stable(self):
        self.assertEqual(digest(canonical({'a':1,'b':2})),digest(canonical({'b':2,'a':1})))

if __name__=='__main__':unittest.main()
