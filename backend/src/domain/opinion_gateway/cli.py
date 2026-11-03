"""Operator entry point. Paths are accepted here, never by agent-facing tools."""
import argparse
import json
from pathlib import Path
from .application import ApplicationService


def main(argv=None):
    parser=argparse.ArgumentParser(prog='analysis',description='Tweets2Insights domain architecture')
    parser.add_argument('--root',default='.opinion-assets')
    commands=parser.add_subparsers(dest='command',required=True)
    register=commands.add_parser('register'); register.add_argument('--event',required=True); register.add_argument('--file',required=True)
    for name in ('plan','submit'):
        p=commands.add_parser(name); p.add_argument('--request',required=True)
    p=commands.add_parser('jobs'); p.add_argument('--event',required=True)
    for name in ('status','cancel','retry','resume','result'):
        p=commands.add_parser(name); p.add_argument('--event',required=True); p.add_argument('--job',required=True)
    p=commands.add_parser('export'); p.add_argument('--event',required=True); p.add_argument('--run',required=True)
    p.add_argument('--artifact',required=True); p.add_argument('--output',required=True)
    p=commands.add_parser('worker'); p.add_argument('--once',action='store_true')
    commands.add_parser('serve')
    args=parser.parse_args(argv)
    if args.command=='worker':
        from .domain_worker import main as worker
        return worker(['--root',args.root]+(['--once'] if args.once else []))
    if args.command=='serve':
        from .mcp_server import create_server
        create_server(args.root).run(); return 0
    service=ApplicationService(args.root)
    if args.command=='register':
        result=service.register_dataset(args.event,json.loads(Path(args.file).read_text(encoding='utf-8')))
    elif args.command in ('plan','submit'):
        request=json.loads(Path(args.request).read_text(encoding='utf-8'))
        result=(service.preview_plan if args.command=='plan' else service.submit_run)(request)
    elif args.command=='jobs':
        result=service.list_jobs(args.event)
    elif args.command=='export':
        service.read_domain_artifact(args.event,args.run,args.artifact)
        result=service.assets.read(args.event,args.run,args.artifact)
        target=Path(args.output); target.mkdir(parents=True,exist_ok=True)
        for field,filename in [('markdown','report.md'),('html','report.html')]:
            if field in result: (target/filename).write_text(result[field],encoding='utf-8')
        if result.get('images'):
            images=target/'images'; images.mkdir(exist_ok=True)
            for name,svg in result['images'].items():
                if name not in {'sentiment.svg','stance.svg'}: raise ValueError('invalid chart name')
                (images/name).write_text(svg,encoding='utf-8')
        (target/'artifact.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        result={'output':str(target.resolve())}
    else:
        handler={'status':service.job_status,'cancel':service.cancel_job,'retry':service.retry_job,
                 'resume':service.resume_job,'result':service.read_job_artifact}[args.command]
        result=handler(args.event,args.job)
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
