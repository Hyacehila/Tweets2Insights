import asyncio
from opinion_gateway.agent_models import active_config, api_key_for, is_local
from opinion_core.labeling.openai_provider import OpenAIJsonProvider


class ModelFactory:
    def __init__(self, settings):
        self.settings = settings

    async def request(self, instruction, payload):
        config = active_config(self.settings.agent_model_config)
        key = api_key_for(config)
        if not key and not is_local(config):
            raise EnvironmentError("configured Agent model credential is missing")

        def invoke():
            provider = OpenAIJsonProvider(config, key)
            try:
                return provider.request(instruction, payload)
            finally:
                provider.client.close()

        return await asyncio.to_thread(invoke)
