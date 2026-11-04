"""Retired publisher-decision inputs must not be needed by the legacy loader."""

import json

from config import load_config
from nodes.stage1.data_load import DataLoadNode


def test_original_data_load_needs_no_publisher_decision_file(tmp_path):
    paths = {}
    for name, payload in {
        "blog_data": [{"id": "1", "content": "测试帖子"}],
        "topics": [],
        "sentiment_attributes": [],
        "publisher_objects": [
            "政府机构",
            "新闻媒体",
            "自媒体",
            "企业账号",
            "事业单位",
            "社会组织",
            "个人用户",
        ],
        "belief_system": [],
    }.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        paths[name + "_path"] = str(path)
    shared = {
        "data": {"data_paths": paths},
        "config": {"data_source": {"type": "original"}},
    }
    node = DataLoadNode()
    prepared = node.prep(shared)
    assert "publisher_decision_path" not in prepared
    loaded = node.exec(prepared)
    node.post(shared, prepared, loaded)
    assert loaded["publisher_objects"] == json.loads(
        (tmp_path / "publisher_objects.json").read_text(encoding="utf-8")
    )
    assert "publisher_decisions" not in loaded
    assert "publisher_decisions" not in shared["data"]


def test_old_config_ignores_retired_publisher_decision_path(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "data:\n  publisher_decision_path: deleted.json\n", encoding="utf-8"
    )
    config = load_config(str(path))
    assert not hasattr(config.data, "publisher_decision_path")
