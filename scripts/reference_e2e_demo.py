"""Reproducible disposable reference workflow; NOT an enterprise product test."""
from __future__ import annotations
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile


def run(*argv, cwd, env):
    p=subprocess.run([sys.executable,'-m','keelway_core',*argv],cwd=cwd,env=env,capture_output=True,text=True)
    if p.returncode:
        raise RuntimeError(f'Command failed: {argv}; stderr={p.stderr}')
    return json.loads(p.stdout)


def main():
    cwd=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='keelway-ref-demo-') as d:
        root=Path(d);proj=root/'project';proj.mkdir()
        original=proj/'hello.py';original.write_text('print("BEFORE")\n')
        new=root/'new.txt';new.write_text('print("AFTER")\n')
        env=os.environ.copy();env['KEELWAY_REF_DB']=str(root/'events.sqlite')
        task=run('new',str(proj),'Update hello output',cwd=cwd,env=env)['task_id']
        plan=run('propose',task,'hello.py',str(new),cwd=cwd,env=env)
        assert original.read_text()=='print("BEFORE")\n','Proposal unexpectedly wrote file'
        run('approve',task,plan['plan_digest'],'--approver','local-demo-operator','--confirm',cwd=cwd,env=env)
        result=run('apply',task,'--confirm',cwd=cwd,env=env)
        assert original.read_text()=='print("AFTER")\n'
        verified=run('verify','--ack-unsandboxed',task,'--',sys.executable,'-m','py_compile','hello.py',cwd=cwd,env=env)
        state=run('show',task,cwd=cwd,env=env)
        audit=run('audit',task,cwd=cwd,env=env)
        assert result['state']=='VERIFYING' and state['state']=='COMPLETED' and audit['ok'] and verified['exit_code']==0
        print(json.dumps({'name':'disposable local reference flow','state':state['state'],'audit_events':audit['events'],'verification_exit_code':verified['exit_code'],'real_file_changed':True,'enterprise_qualified':False},indent=2))

if __name__=='__main__':main()
