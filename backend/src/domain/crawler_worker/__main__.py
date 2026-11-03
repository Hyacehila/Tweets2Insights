import json
import sys
from pathlib import Path
from opinion_gateway.dataset_repository import atomic_json
from .runner import collect
from opinion_gateway.connectors import WaitingForAuthentication, ConnectorUnavailable


def main():
    request = json.load(sys.stdin)
    checkpoint=Path(request['_checkpoint_path']) if request.get('_checkpoint_path') else None
    state=json.loads(checkpoint.read_text(encoding='utf-8')) if checkpoint and checkpoint.exists() else None
    try:
        result = collect(request['event'],request['crawl'],checkpoint=state,
                         save_checkpoint=lambda value:atomic_json(checkpoint,value) if checkpoint else None)
    except WaitingForAuthentication:
        result = {'status':'waiting_for_auth'}
    except ConnectorUnavailable:
        result = {'status':'connector_unavailable'}
    json.dump(result,sys.stdout,ensure_ascii=False,allow_nan=False)


if __name__ == '__main__':
    main()
