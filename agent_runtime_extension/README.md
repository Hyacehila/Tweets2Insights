# Agent Runtime extension

Updated 2026-11-03. Upstream reference: bytedance/deer-flow commit
`1dd6d056278536af1cb4fc60347f4ca40fcb629b`. No upstream runtime source is bundled or claimed as validated.

`planner.py` compiles a validated RunRequest into the required domain stages. It is the local deterministic
Leader implementation, not a claim of installed upstream natural-language planning.
`bind_tools.py` maps logical role allowlists to exact runtime-discovered MCP names and rejects ambiguity.
Roles cover Leader, Query, Insight, Critic, Media, Forecast, Scenario, Content and Structure.
DomainWorker is the sole domain scheduler. An external Leader submits work and observes status; it does not
run a second retry/search loop over the same job. Roles cannot launch nested delegation or access arbitrary paths.

`extensions_config.example.json` retains the upstream mcpServers registration format.
`roles.example.yaml` is the earlier two-role bootstrap example; generate current bindings from actual discovery:

```powershell
uv run python -m agent_runtime_extension.bind_tools --discovery tools.json --output bound-roles.json
```

The domain service now exposes 17 tools. The main path is register_dataset → preview_plan → submit_run →
job_status/read_job_artifact. Detailed bounded reads use read_domain_artifact. All long operations run in the
separate DomainWorker. Search, model, collection and media providers are selected by the frozen domain request
and operator-installed connectors; source content cannot grant tools or change those selections.

See [application runbook](../doc/modules/domain-application.md) and
[migration record](../doc/modules/architecture-rewrite.md). Full runtime/model/browser validation is deferred.
