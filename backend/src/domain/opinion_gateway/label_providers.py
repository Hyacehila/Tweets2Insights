"""Decision-model adapters shared by the domain Worker and annotation CLI."""

from opinion_core.labeling.openai_decisions import OpenAIDecisionsProvider
from opinion_core.labeling.system_one import SystemOneProvider

from . import credentials
from .connectors import (
    ConnectorUnavailable,
    DecisionConnector,
    WaitingForAuthentication,
)


def make_label_provider(options, ledger, media_mode="text_only"):
    if options.provider == "connector":
        if not options.connector:
            raise ConnectorUnavailable("decision label connector ID required")
        return DecisionConnector(options.connector, media_mode, ledger)
    if options.provider not in {"openai_decisions", "jev", "aliyun_decision"}:
        raise ValueError("labeling requires a decision-model provider")
    if media_mode != "text_only":
        raise ValueError(
            "image labeling requires an explicit multimodal decision connector"
        )
    key = credentials.get(credentials.KEYS[options.provider])
    if not key:
        raise WaitingForAuthentication(
            f"{options.provider} annotation credential required"
        )
    if options.provider == "openai_decisions":
        return OpenAIDecisionsProvider(options.model, key, ledger)
    endpoint = (
        "https://api.typesafe.ai/v1/systemone"
        if options.provider == "jev"
        else credentials.get("ALIYUN_DECISION_ENDPOINT")
    )
    return SystemOneProvider(options.provider, options.model, key, endpoint, ledger)
