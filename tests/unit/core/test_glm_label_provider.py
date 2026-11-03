from types import SimpleNamespace
from opinion_core.labeling.glm_provider import GLMJsonProvider, GLMSchemaBuilder


def test_client_disables_hidden_retries_and_captures_usage(monkeypatch):
    captured = {}
    class Client:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.chat = SimpleNamespace(completions=self)
        def create(self, **kwargs):
            captured['request'] = kwargs
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"records":[]}'))],
                                   usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5))
    monkeypatch.setattr('zai.ZaiClient', Client)
    provider = GLMJsonProvider(api_key='not-a-real-key', model='glm-4.5-air')
    result = provider.predict([], SimpleNamespace(model_dump=lambda **k: {'targets': []}))
    assert captured['max_retries'] == 0
    assert result['usage'] == {'input_tokens':10, 'output_tokens':5}
    assert captured['request']['messages'][0]['role'] == 'system'
    assert 'not-a-real-key' not in str(result)
