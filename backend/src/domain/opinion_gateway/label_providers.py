"""Decision-model adapters shared by the domain Worker and annotation CLI."""

from opinion_core.labeling.media import MediaPolicy
from opinion_core.labeling.openai_decisions import OpenAIDecisionsProvider
from opinion_core.labeling.system_one import SystemOneProvider

from . import credentials
from .connectors import (
    ConnectorUnavailable,
    DecisionConnector,
    WaitingForAuthentication,
    connector_supports_images,
)


def media_policy_for(options, mode):
    return MediaPolicy(
        options.provider,
        options.model,
        mode,
        options.max_images_per_post,
        connector_supports_images(options.connector)
        if options.provider == "connector"
        else False,
    )


def make_label_provider(options, ledger, media_mode="text_image", image_loader=None):
    if options.provider == "connector":
        if not options.connector:
            raise ConnectorUnavailable("decision label connector ID required")
        return DecisionConnector(
            options.connector,
            media_mode,
            ledger,
            max_images_per_post=options.max_images_per_post,
        )
    if options.provider not in {"openai_decisions", "jev", "aliyun_decision"}:
        raise ValueError("labeling requires a decision-model provider")
    media_options = {
        "media_mode": media_mode,
        "max_images_per_post": options.max_images_per_post,
        "image_loader": image_loader,
    }
    key = credentials.get(credentials.KEYS[options.provider])
    if not key:
        raise WaitingForAuthentication(
            f"{options.provider} annotation credential required"
        )
    if options.provider == "openai_decisions":
        return OpenAIDecisionsProvider(options.model, key, ledger, **media_options)
    endpoint = (
        "https://api.typesafe.ai/v1/systemone"
        if options.provider == "jev"
        else credentials.get("ALIYUN_DECISION_ENDPOINT")
    )
    return SystemOneProvider(
        options.provider, options.model, key, endpoint, ledger, **media_options
    )
