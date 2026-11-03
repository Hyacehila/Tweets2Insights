from src.agents.middlewares import validate_request


class DomainTools:
    """Small explicit tool capability surface for the lead graph."""

    def __init__(self, mcp):
        self.mcp = mcp

    async def plan(self, state, request):
        request = validate_request(state, request)
        return await self.mcp.call("preview_plan", {"request": request})

    async def submit(self, state, request):
        if state.get("execute") is not True:
            raise ValueError("this turn is planning only")
        request = validate_request(state, request)
        return await self.mcp.call("submit_run", {"request": request})
