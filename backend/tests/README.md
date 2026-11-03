# Backend tests

`test_workflow_contracts.py` uses synthetic records and mocked provider responses to check:

- 41 analysis tools, phase dependencies and sampling population.
- System One request/response contracts and probability rejection.
- PCA training cutoffs, decoded constraints and paired no-op scenarios.
- Forum tool execution, scoped Worker artifacts and local credential status.

Run from the repository root:

```bash
uv run --project backend pytest backend/tests -q
```

Existing domain and legacy tests live in `tests/` and `dashboard/tests/`.
See the [testing guide](../../doc/testing/testing_workflow.md) for commands and
[implementation record](../../doc/upgrade-status.md) for results and planned coverage.
