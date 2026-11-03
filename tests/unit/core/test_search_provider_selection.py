import pytest
import requests
from opinion_core.evidence.providers import search
from utils.web_search import search_web


@pytest.mark.parametrize('provider', ['tavily', 'deepseek'])
def test_only_selected_provider_normalizes_and_preserves_evidence(provider, monkeypatch):
    calls = []
    body = {'results': [{'title': 'Title', 'url': 'https://example.com/p', 'content': 'page',
                         'snippet': 'short', 'summary': 'long', 'score': .8, 'rerank_score': 2.4,
                         'date': None, 'site_name': None}]}
    class Response:
        def raise_for_status(self): pass
        def json(self): return body
    def post(url, **kwargs):
        calls.append(url)
        assert provider in url
        if provider == 'deepseek':
            assert kwargs['json']['count'] == 3
            assert kwargs['headers']['Authorization'] == 'Bearer test-key'
        return Response()
    monkeypatch.setattr(requests, 'post', post)
    result = search('test', provider=provider, api_key='test-key', max_results=3)
    assert len(calls) == 1
    assert result['raw_response'] == body
    card = result['results'][0]
    assert card['provider'] == provider and card['retrieved_at'] and card['fingerprint']
    assert card['score'] == (2.4 if provider == 'deepseek' else .8)
    assert card['date'] is None and card['source'] == ''
    legacy = search_web('test', provider=provider, api_key='test-key', max_results=3)
    assert set(legacy['results'][0]) == {'title', 'url', 'snippet', 'date', 'source'}


def test_timeout_does_not_fallback_or_expose_key(monkeypatch):
    calls = []
    def post(url, **kwargs):
        calls.append(url)
        raise requests.Timeout('request with secret-key')
    monkeypatch.setattr(requests, 'post', post)
    result = search('x', provider='deepseek', api_key='secret-key')
    assert len(calls) == 1 and result['results'] == []
    assert result['error_type'] == 'timeout'
    assert 'secret-key' not in str(result)


def test_provider_key_isolation_and_limits(monkeypatch):
    monkeypatch.setenv('TAVILY_API_KEY', 'tavily-only')
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    with pytest.raises(EnvironmentError):
        search('x', provider='deepseek')
    with pytest.raises(ValueError):
        search('x' * 129, provider='deepseek', api_key='test')


def test_deepseek_config_reaches_shared(tmp_path, monkeypatch):
    from config import load_config, config_to_shared, validate_config
    path = tmp_path / 'config.yaml'
    path.write_text('stage2:\n  search_provider: deepseek\n')
    config = load_config(str(path))
    monkeypatch.setenv('GLM_API_KEY', 'test-only')
    monkeypatch.setenv('ENHANCED_DATA_PATH', str(path))
    validate_config(config)
    shared = config_to_shared(config)
    assert shared['config']['web_search']['provider'] == 'deepseek'


@pytest.mark.parametrize('status, expected', [(401, 'authentication'), (402, 'budget'), (429, 'rate_limit'), (500, 'http_error')])
def test_http_failures_are_classified_without_retry(status, expected, monkeypatch):
    calls = []
    def post(*args, **kwargs):
        calls.append(args)
        response = requests.Response()
        response.status_code = status
        raise requests.HTTPError('private response', response=response)
    monkeypatch.setattr(requests, 'post', post)
    assert search('x', provider='deepseek', api_key='test')['error_type'] == expected
    assert len(calls) == 1


def test_missing_fields_and_unsafe_urls(monkeypatch):
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'results': [{}, {'url': 'file:///secret'}, {'url': 'https://example.com'}]}
    monkeypatch.setattr(requests, 'post', lambda *a, **kw: Response())
    result = search('x', provider='deepseek', api_key='test')
    assert len(result['results']) == 1
    assert result['results'][0]['score'] is None
