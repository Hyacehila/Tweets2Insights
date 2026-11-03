import asyncio
from opinion_gateway.credentials import get
from opinion_core.labeling.glm_provider import GLMJsonProvider


class ModelFactory:
    def __init__(self, settings):
        self.settings = settings

    async def request(self, instruction, payload):
        key = get(self.settings.model_api_key_env)
        if not key:
            raise EnvironmentError("configured Agent model credential is missing")

        def invoke():
            provider = GLMJsonProvider(api_key=key, model=self.settings.model)
            try:
                return provider.request(instruction, payload)
            finally:
                provider.client.close()

        return await asyncio.to_thread(invoke)
