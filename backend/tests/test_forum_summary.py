from opinion_core.evidence.forum import compact_context


def test_forum_context_samples_whole_interval_and_keeps_denominators():
    windows = [
        {
            "start": str(i),
            "end": str(i + 1),
            "raw_n": 3,
            "joint_n": 1,
            "fields": {
                "sentiment": {
                    "mean": None,
                    "valid_n": 0,
                    "coverage": 0,
                    "statuses": {"abstained": 3},
                    "mass": list(range(100)),
                }
            },
            "summary": list(range(500)),
        }
        for i in range(100)
    ]
    value = compact_context({"windows": windows, "filtered_n": 300})
    assert value["window_total"] == 100
    assert value["window_preview_truncated"] is True
    assert len(value["windows"]) == 12
    assert value["windows"][0]["start"] == "0"
    assert value["windows"][-1]["start"] == "99"
    field = value["windows"][-1]["fields"]["sentiment"]
    assert field == {
        "mean": None,
        "valid_n": 0,
        "coverage": 0,
        "statuses": {"abstained": 3},
    }
    assert "summary" not in value["windows"][-1]
    assert windows[-1]["fields"]["sentiment"]["mass"] == list(range(100))
