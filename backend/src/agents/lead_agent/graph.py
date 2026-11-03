"""Graph export for an optional LangGraph development server; it owns checkpoint persistence."""

from src.config import load_settings
from src.models import ModelFactory
from src.mcp import DomainToolClient
from src.tools import DomainTools
from src.skills import SkillLoader
from .factory import make_lead_agent


def build_graph():
    settings = load_settings()
    return make_lead_agent(
        settings,
        ModelFactory(settings),
        DomainTools(DomainToolClient(settings)),
        SkillLoader(settings),
    )


graph = build_graph()
