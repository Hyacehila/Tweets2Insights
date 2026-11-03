import os
import requests
from .base import SearchOptions
from .tavily import TavilyProvider
from .deepseek import DeepSeekProvider

PROVIDERS = {'tavily': TavilyProvider, 'deepseek': DeepSeekProvider}


def search(query, *, provider='tavily', api_key=None, max_results=5, timeout_seconds=20, need_content=False):
    name = provider.strip().lower()
    if name not in PROVIDERS:
        raise ValueError('unsupported search provider')
    options = SearchOptions(query.strip(), max_results, timeout_seconds, need_content)
    options.validate()
    if name == 'deepseek' and len(options.query) > 128:
        raise ValueError('DeepSeek query exceeds 128 characters')
    key = (api_key or '').strip() or os.getenv(name.upper() + '_API_KEY', '').strip()
    if not key:
        raise EnvironmentError(f'{name} API key required')
    error = ''
    try:
        return PROVIDERS[name]().search(options, key)
    except requests.Timeout:
        error = 'timeout'
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else 0
        error = {401: 'authentication', 402: 'budget', 429: 'rate_limit'}.get(code, 'http_error')
    except requests.RequestException:
        error = 'connection'
    except (ValueError, TypeError):
        error = 'invalid_response'
    return {'query': options.query, 'provider': name, 'results': [], 'raw_response': None,
            'error': error, 'error_type': error}
