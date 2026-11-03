# Backend validation

Updated 2026-11-03. Functional scripts were written before this offline engineering validation, per user instruction.
`test_workflow_contracts.py` checks 41 canonical tools, phase dependencies, sampling population,
System One request/response contracts, probability rejection, PCA training cutoff and decoded constraints,
paired no-op scenarios, forum tool execution, scoped worker artifacts, and local credential status.
It uses synthetic records and mocked external responses; it is not a human-gold Demo or live end-to-end test.
Run: `uv run --project backend pytest backend/tests -q` from the repository root.
Existing domain and legacy tests remain at repository `tests/` and `dashboard/tests/`.
Planned coverage: thread isolation, real MCP discovery, cancellation/reconnect, graph checkpoints,
role limits, uploads, artifacts, API ownership, and frontend-to-worker lifecycle.
No real model, Demo, browser or scientific validation is claimed by the directory's presence.
