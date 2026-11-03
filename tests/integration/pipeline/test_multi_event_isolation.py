import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from opinion_gateway.dataset_repository import DatasetRepository
from utils.path_manager import run_context, get_images_dir
from utils.run_state import lock_path


def test_event_assets_copies_and_run_paths_are_isolated(tmp_path):
    repo = DatasetRepository(tmp_path)
    a = repo.register('a', [{'content': 'A'}])
    b = repo.register('b', [{'content': 'B'}])
    def execute(pair):
        event, dataset = pair
        with run_context(tmp_path, event, dataset['dataset_id'], 'run1'):
            target = repo.run_dir(event, dataset['dataset_id'], 'run1')
            assert str(target) in get_images_dir()
            assert target in lock_path().parents
            path = target / 'result.json'
            path.write_text(json.dumps(repo.read(event, dataset['dataset_id'])))
            return path
    with ThreadPoolExecutor(2) as pool:
        paths = list(pool.map(execute, [('a', a), ('b', b)]))
    assert paths[0] != paths[1]
    assert json.loads(paths[0].read_text())[0]['content'] == 'A'
    with pytest.raises(FileNotFoundError):
        repo.read('a', b['dataset_id'])
    rows = repo.read('a', a['dataset_id'])
    rows[0]['content'] = 'changed'
    assert repo.read('a', a['dataset_id'])[0]['content'] == 'A'
    c = repo.register('a', [{'content': 'C'}])
    assert c['data_version'] != a['data_version']
    assert repo.read('a', c['dataset_id'])[0]['content'] == 'C'
    with pytest.raises(ValueError):
        repo.read('../b', a['dataset_id'])


def test_legacy_loader_has_no_stale_global_cache(tmp_path, monkeypatch):
    from utils.mcp_server import get_blog_data
    path = tmp_path / 'legacy.json'
    monkeypatch.setenv('ENHANCED_DATA_PATH', str(path))
    path.write_text('[{"content":"one"}]')
    assert get_blog_data()[0]['content'] == 'one'
    path.write_text('[{"content":"two"}]')
    assert get_blog_data()[0]['content'] == 'two'
