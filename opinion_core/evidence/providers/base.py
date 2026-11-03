from typing import Protocol
from dataclasses import dataclass
import hashlib
from datetime import datetime, timezone
from urllib.parse import urlparse


@dataclass(frozen=True)
class SearchOptions:
    query: str
    max_results: int = 5
    timeout_seconds: int = 20
    need_content: bool = False

    def validate(self):
        if not self.query.strip() or not 1 <= self.max_results <= 20 or self.timeout_seconds <= 0:
            raise ValueError('require query, max_results 1..20 and positive timeout')


class SearchProvider(Protocol):
    name: str
    capabilities: dict
    def search(self, options: SearchOptions, api_key: str) -> dict: ...


def normalize(body, provider, options):
    if not isinstance(body, dict) or not isinstance(body.get('results'), list):
        raise ValueError('invalid provider response')
    cards = []
    retrieved = datetime.now(timezone.utc).isoformat()
    for item in body['results'][:options.max_results]:
        if not isinstance(item, dict):
            continue
        url = str(item.get('url') or '')
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username or parsed.password:
            continue
        is_deepseek = provider == 'deepseek'
        snippet = str((item.get('snippet') if is_deepseek else item.get('content', item.get('snippet'))) or '')
        content = str((item.get('content') if is_deepseek else item.get('raw_content')) or '')
        fingerprint = hashlib.sha256(' '.join((content or snippet or url).split()).encode()).hexdigest()
        cards.append({'title': str(item.get('title') or ''), 'url': url, 'snippet': snippet,
                      'summary': str(item.get('summary') or ''), 'content': content,
                      'date': item.get('date' if is_deepseek else 'published_date') or None,
                      'source': str(item.get('site_name' if is_deepseek else 'source') or ''),
                      'provider': provider, 'retrieved_at': retrieved, 'fingerprint': fingerprint,
                      'score': item.get('rerank_score' if is_deepseek else 'score'),
                      'score_scale': '0..3 relevance' if is_deepseek else 'provider relevance',
                      'authority': item.get('authority') if is_deepseek else None})
    return {'query': options.query, 'provider': provider, 'results': cards,
            'raw_response': body, 'retrieved_at': retrieved, 'error': '', 'error_type': ''}
