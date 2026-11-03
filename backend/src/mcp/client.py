import json
import os
import sys
from fastmcp import Client


class DomainToolClient:
    def __init__(self, settings):
        self.settings = settings

    def configuration(self):
        path = self.settings.repository_root / "extensions_config.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        servers = {}
        substitutions = {
            "$PYTHON": sys.executable,
            "$T2I_ASSET_ROOT": str(self.settings.asset_root),
            "$PROJECT_ROOT": str(self.settings.repository_root),
        }
        for name, entry in raw.get("mcpServers", {}).items():
            if not entry.get("enabled", True):
                continue
            if entry.get("transport", "stdio") != "stdio":
                raise ValueError("only configured local stdio supported")
            servers[name] = {
                "command": substitutions.get(entry["command"], entry["command"]),
                "args": [substitutions.get(a, a) for a in entry.get("args", [])],
                "cwd": str(self.settings.repository_root / "backend"),
                "env": {
                    "PYTHONIOENCODING": "utf-8",
                    **{
                        k: os.environ[k]
                        for k in entry.get("env_allowlist", [])
                        if k in os.environ
                    },
                },
            }
        if not servers:
            raise ValueError("no enabled MCP server")
        return {"mcpServers": servers}

    async def call(self, logical, arguments):
        async with Client(self.configuration(), timeout=60, init_timeout=60) as client:
            tools = await client.list_tools()
            matches = [
                tool.name
                for tool in tools
                if tool.name == logical or tool.name.endswith("_" + logical)
            ]
            if len(matches) != 1:
                raise ValueError("missing or ambiguous MCP tool: " + logical)
            response = await client.call_tool(matches[0], arguments)
            return response.data

    async def discover(self):
        async with Client(self.configuration(), timeout=30, init_timeout=60) as client:
            return [
                {"name": tool.name, "description": tool.description}
                for tool in await client.list_tools()
            ]
