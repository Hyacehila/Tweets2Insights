from contextlib import asynccontextmanager
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


@asynccontextmanager
async def open_checkpointer(state_root):
    async with AsyncSqliteSaver.from_conn_string(
        str(state_root / "checkpoints.sqlite")
    ) as saver:
        await saver.setup()
        yield saver
