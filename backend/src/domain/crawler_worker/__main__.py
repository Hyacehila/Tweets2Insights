import json
import sys
from pathlib import Path

from opinion_gateway.connectors import ConnectorUnavailable, WaitingForAuthentication
from opinion_gateway.dataset_repository import atomic_json

from .runner import collect


def main():
    request = json.load(sys.stdin)
    checkpoint=Path(request['_checkpoint_path']) if request.get('_checkpoint_path') else None
    state=json.loads(checkpoint.read_text(encoding='utf-8')) if checkpoint and checkpoint.exists() else None
    try:
        result = collect(request['event'],request['crawl'],checkpoint=state,asset_root=request.get('_asset_root'),
                         save_checkpoint=lambda value:atomic_json(checkpoint,value) if checkpoint else None)
    except (WaitingForAuthentication, ConnectorUnavailable) as exc:
        result = {'status':'waiting_for_auth' if isinstance(exc, WaitingForAuthentication) else 'connector_unavailable', 'error':str(exc)}
    except Exception as exc:  # noqa: BLE001 - return structured diagnostics from the subprocess boundary
        from opinion_gateway.diagnostics import exception_details
        result = {'status':'failed', **exception_details(exc, stage='input')}
    json.dump(result,sys.stdout,ensure_ascii=False,allow_nan=False)


if __name__ == '__main__':
    main()
