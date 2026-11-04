"""Operator-installed adapters. Agent requests select IDs and cannot supply commands."""
import json
import os
from pathlib import Path
import subprocess


class ConnectorUnavailable(RuntimeError):
    pass


class WaitingForAuthentication(RuntimeError):
    pass


def invoke_connector(group, name, payload, timeout=120):
    path = os.environ.get('T2I_CONNECTORS_FILE')
    if not path:
        raise ConnectorUnavailable('configure T2I_CONNECTORS_FILE with an operator-owned connector registry')
    registry = json.loads(Path(path).read_text(encoding='utf-8'))
    definition = registry.get(group,{}).get(name)
    if not definition or not isinstance(definition.get('command'),list) or not definition['command']:
        raise ConnectorUnavailable(f'no configured {group} connector for {name}')
    result = subprocess.run(definition['command'],input=json.dumps(payload,ensure_ascii=False),
                            capture_output=True,text=True,encoding='utf-8',timeout=timeout,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if result.returncode != 0:
        # Never persist stderr, which can contain authorization headers or session secrets.
        raise RuntimeError(f'connector process failed with exit code {result.returncode}')
    if len(result.stdout) > 50_000_000:
        raise ValueError('connector response exceeds size limit')
    response = json.loads(result.stdout)
    if not isinstance(response,dict):
        raise ValueError('connector must return a JSON object')
    if response.get('status') == 'waiting_for_auth':
        raise WaitingForAuthentication(f'{group}:{name} needs a configured local session')
    return response


def connector_supports_images(name):
    path = os.environ.get('T2I_CONNECTORS_FILE')
    if not path:
        return False
    registry = json.loads(Path(path).read_text(encoding='utf-8'))
    return 'image' in registry.get('label', {}).get(name, {}).get('modalities', ['text'])


class DecisionConnector:
    def __init__(self, name, mode='text_only', ledger=None, *, max_images_per_post=3):
        from opinion_core.labeling.media import MediaPolicy
        self.media_policy = MediaPolicy('connector', name, mode, max_images_per_post, connector_supports_images(name))
        self.name,self.mode,self.ledger = name,self.media_policy.effective_mode,ledger
        # Operators must change the connector ID/version when implementation or model changes.
        self.version = f'connector:{name}:{self.media_policy.version}'

    def predict(self, posts, schema):
        reservation = self.ledger.reserve('label',self.version) if self.ledger else None
        try:
            records=[p.model_dump(mode='json') for p in posts]
            for row, post in zip(records, posts):
                row['media_refs'] = self.media_policy.references(post)
                row.pop('raw_asset_ref', None)
            if self.mode=='image_only':
                for row in records:
                    row['content']=''
            result = invoke_connector('label',self.name,{'operation':'label','mode':self.mode,
                'schema':schema.model_dump(mode='json'),'posts':records})
            if self.ledger:
                self.ledger.settle(reservation,result.get('usage'),result.get('cost'))
            return result
        except Exception:
            if self.ledger:
                self.ledger.settle(reservation,status='uncertain')
            raise
