"""Explicit, non-destructive legacy migration CLI."""
import argparse,json
from pathlib import Path
from .legacy_adapter import migrate_file


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',required=True); parser.add_argument('--output',required=True)
    parser.add_argument('--mapping',required=True); parser.add_argument('--schema-version',required=True)
    parser.add_argument('--mapping-version',required=True); parser.add_argument('--timezone')
    args=parser.parse_args()
    entries=json.loads(Path(args.mapping).read_text(encoding='utf-8'))
    result=migrate_file(args.source,args.output,schema_version=args.schema_version,mapping_version=args.mapping_version,
        topic_map={(entry.get('parent'),entry['child']):entry['topic_id'] for entry in entries},source_timezone=args.timezone)
    print(json.dumps({k:v for k,v in result['migration'].items() if k!='raw_records'},ensure_ascii=False))


if __name__=='__main__': main()
