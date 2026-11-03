import requests
from .base import SearchOptions, normalize


class TavilyProvider:
    name = 'tavily'
    capabilities = {'max_results': 20, 'need_content': True, 'date_filters': False}

    def search(self, options: SearchOptions, api_key: str) -> dict:
        options.validate()
        payload = {'api_key': api_key, 'query': options.query, 'max_results': options.max_results,
                   'include_answer': False, 'include_images': False}
        if options.need_content:
            payload['include_raw_content'] = True
        response = requests.post('https://api.tavily.com/search', json=payload, timeout=options.timeout_seconds)
        response.raise_for_status()
        return normalize(response.json(), self.name, options)
