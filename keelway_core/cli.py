from __future__ import annotations
import argparse
from hashlib import sha256
from pathlib import Path
import json
import os
import subprocess
import sys

from .engine import Engine, WorkflowError
from .provider import OllamaLocal, FixtureProvider

def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog='keelway-ref', description='Local reference workflow; NOT enterprise security qualified')
    p.add_argument('--database', default=os.getenv('KEELWAY_REF_DB', str(Path.home()/'.keelway-reference.sqlite3')))
    sub = p.add_subparsers(dest='command', required=True)
    a = sub.add_parser('new'); a.add_argument('workspace'); a.add_argument('goal')
    a = sub.add_parser('show'); a.add_argument('task_id')
    a = sub.add_parser('propose'); a.add_argument('task_id'); a.add_argument('relative_path'); a.add_argument('content_file')
    a = sub.add_parser('proposal'); a.add_argument('task_id')
    a = sub.add_parser('approve'); a.add_argument('task_id'); a.add_argument('plan_digest'); a.add_argument('--approver', required=True); a.add_argument('--confirm', action='store_true')
    a = sub.add_parser('apply'); a.add_argument('task_id'); a.add_argument('--confirm', action='store_true')
    a = sub.add_parser('verify'); a.add_argument('task_id'); a.add_argument('--ack-unsandboxed', action='store_true'); a.add_argument('--timeout', type=int, default=30); a.add_argument('test_argv', nargs=argparse.REMAINDER)
    a = sub.add_parser('audit'); a.add_argument('task_id')
    a = sub.add_parser('cancel'); a.add_argument('task_id')
    a = sub.add_parser('suggest'); a.add_argument('prompt'); a.add_argument('--provider', choices=['ollama','fixture'], default='ollama'); a.add_argument('--model', default='qwen2.5-coder:7b')
    a = sub.add_parser('doctor')
    args = p.parse_args(argv)
    if args.command == 'doctor':
        print(json.dumps({'python': sys.version.split()[0], 'database': args.database, 'status': 'REFERENCE_ONLY', 'enterprise_security_qualified': False}, indent=2)); return 0
    if args.command == 'suggest':
        try:
            provider = OllamaLocal(args.model) if args.provider=='ollama' else FixtureProvider()
            print(json.dumps(provider.complete(args.prompt).__dict__, indent=2)); return 0
        except Exception as exc:
            print(f'provider failure: {exc}', file=sys.stderr); return 2
    try:
        e = Engine(args.database)
        try:
            if args.command == 'new': result = {'task_id': e.create(args.workspace,args.goal)}
            elif args.command == 'show': result = e.task(args.task_id)
            elif args.command == 'propose': result = e.propose(args.task_id,args.relative_path,Path(args.content_file).read_bytes())
            elif args.command == 'proposal': result = e.proposal(args.task_id)
            elif args.command == 'approve':
                if not args.confirm: raise WorkflowError('explicit --confirm required')
                e.approve(args.task_id,args.plan_digest,args.approver); result={'approved':True}
            elif args.command == 'apply':
                if not args.confirm: raise WorkflowError('explicit --confirm required')
                result = e.apply(args.task_id)
            elif args.command == 'audit': result = e.audit(args.task_id)
            elif args.command == 'cancel': e.cancel(args.task_id); result={'cancelled':True}
            elif args.command == 'verify':
                if not args.ack_unsandboxed: raise WorkflowError('test execution is UNSANDBOXED: explicit --ack-unsandboxed required')
                cmd = args.test_argv
                if cmd and cmd[0]=='--': cmd=cmd[1:]
                if not cmd or cmd[0] not in (sys.executable, 'python', 'python3'):
                    raise WorkflowError('reference verifier only allows explicit python commands; no shell')
                task=e.task(args.task_id)
                if task['state'] != 'VERIFYING': raise WorkflowError('task is not VERIFYING')
                try:
                    r=subprocess.run(cmd,cwd=task['workspace'],capture_output=True,text=True,timeout=args.timeout,check=False)
                    out=r.stdout+'\n'+r.stderr; code=r.returncode
                except subprocess.TimeoutExpired:
                    out='test subprocess timeout'; code=124
                # stdout/stderr deliberately not treated as secret-safe enterprise telemetry.
                result=e.mark_verified(args.task_id,cmd,code,sha256(out.encode()).hexdigest(),out[:8000]);print(out, file=sys.stderr)
            else: raise WorkflowError('unknown command')
            print(json.dumps(result,indent=2)); return 0
        finally: e.close()
    except (WorkflowError, OSError, ValueError) as exc:
        print(json.dumps({'ok':False,'error':str(exc)}),file=sys.stderr); return 2

if __name__=='__main__': raise SystemExit(main())
