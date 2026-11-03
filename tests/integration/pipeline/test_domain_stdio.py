"""Real local MCP subprocess, without network or model calls; not product E2E."""
import asyncio
import os
import sys
from pathlib import Path
from fastmcp import Client


def test_windows_compatible_stdio_upload(tmp_path):
    async def run():
        config = {'mcpServers': {'opinion': {'command': sys.executable,
                   'args': ['-m', 'opinion_gateway.mcp_server', '--root', str(tmp_path)],
                   'cwd': str(Path.cwd()), 'env': {'PYTHONIOENCODING': 'utf-8'}}}}
        async with Client(config, timeout=20, init_timeout=20) as client:
            tools = await client.list_tools()
            register = next(t.name for t in tools if t.name.endswith('register_dataset'))
            result = await client.call_tool(register, {'event_id': 'stdio', 'records': [
                {'post_id': 'one', 'raw_id': '1', 'platform': 'test', 'content': '本地协议验证'}]})
            assert result.data['count'] == 1
            args = dict(event_id='stdio', dataset_id=result.data['dataset_id'], run_id='run')
            names = {name: next(t.name for t in tools if t.name.endswith(name)) for name in (
                'describe_dataset', 'read_evidence', 'render_report', 'read_artifact')}
            stats = await client.call_tool(names['describe_dataset'], args)
            assert stats.data['count'] == 1
            evidence = await client.call_tool(names['read_evidence'], args)
            assert evidence.data['items'][0]['reference'] == 'P:one'
            report = await client.call_tool(names['render_report'], args)
            assert report.data['status'] == 'completed'
            artifact = await client.call_tool(names['read_artifact'], {**args, 'artifact_id': 'report'})
            assert '[P:one]' in artifact.data['markdown']
    asyncio.run(run())
