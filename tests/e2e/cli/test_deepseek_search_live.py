import os
import pytest
from utils.web_search import search_web

pytestmark = [pytest.mark.e2e, pytest.mark.live_api]


def test_deepseek_single_search_live():
    if not os.getenv('DEEPSEEK_API_KEY'):
        pytest.fail('DEEPSEEK_API_KEY required for explicit live acceptance')
    result = search_web('城市 暴雨 应急响应', provider='deepseek', max_results=3)
    assert result['error'] == ''
    assert result['results']
    assert result['evidence_cards'][0]['retrieved_at']
