import requests
from .base import SearchOptions, normalize


class DeepSeekProvider:
    name = 'deepseek'
    capabilities = {'max_results': 50, 'max_query_length': 128, 'need_content': True, 'date_filters': False}

    def search(self, options: SearchOptions, api_key: str) -> dict:
        options.validate()
        if len(options.query) > 128:
            raise ValueError('DeepSeek query exceeds 128 characters')
        response = requests.post('https://api.deepseek.com/v1/tools/search',
                                 headers={'Authorization': f'Bearer {api_key}'},
                                 json={'query': options.query, 'count': options.max_results,
                                       'need_content': options.need_content}, timeout=options.timeout_seconds)
        response.raise_for_status()
        return normalize(response.json(), self.name, options)
