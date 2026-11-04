"""Native OpenAI Decisions API adapter; one post and five choice questions per call."""

import base64
import json
import math

import requests

from .media import DecisionInput, MediaPolicy
from .system_one import choice_questions


class OpenAIDecisionsProvider:
    endpoint = "https://api.openai.com/v1/decisions"

    def __init__(
        self,
        model,
        api_key,
        ledger,
        *,
        media_mode="text_image",
        max_images_per_post=3,
        image_loader=None,
    ):
        if model != "gpt-6-luna":
            raise ValueError("OpenAI Decisions currently requires gpt-6-luna")
        if not api_key:
            raise ValueError("OpenAI annotation credential is not configured")
        self.model, self.api_key, self.ledger = model, api_key, ledger
        self.media_policy = MediaPolicy(
            "openai_decisions", model, media_mode, max_images_per_post
        )
        self.inputs = DecisionInput(self.media_policy, image_loader)
        self.version = f"openai_decisions:{model}:choice-v2:{self.media_policy.version}"

    def prepare_input(self, post):
        return self.inputs.prepare(post)

    def predict(self, posts, schema):
        if len(posts) != 1:
            raise ValueError("OpenAI Decisions adapter requires batch_size=1")
        state, images = self.inputs.consume(posts[0])
        content = [
            {"type": "input_text", "text": json.dumps(state, ensure_ascii=False)}
        ]
        content.extend(
            {
                "type": "input_image",
                "image_url": "data:image/jpeg;base64,"
                + base64.b64encode(data).decode("ascii"),
            }
            for data in images
        )
        definitions = choice_questions(schema)
        questions = [
            {
                "name": name,
                "type": "choice",
                "instructions": question["instructions"],
                "choices": [
                    {"value": value, "description": description}
                    for value, description in question["criteria"].items()
                ],
            }
            for name, question in definitions.items()
        ]
        call = self.ledger.reserve("label", self.version)
        try:
            response = requests.post(
                self.endpoint,
                headers={"Authorization": "Bearer " + self.api_key},
                json={
                    "model": self.model,
                    "input": [{"role": "user", "content": content}],
                    "questions": questions,
                },
                timeout=(10, 90),
                allow_redirects=False,
            )
            if response.status_code != 200:
                raise RuntimeError(f"OpenAI Decisions HTTP {response.status_code}")
            result = response.json()
            self.ledger.settle(call, result.get("usage", {}))
        except Exception:
            self.ledger.settle(call, status="uncertain")
            raise
        answers = result.get("answers")
        if not isinstance(answers, list) or len(answers) != len(questions):
            raise ValueError("missing OpenAI decision answers")
        by_name = {answer["name"]: answer for answer in answers}
        if set(by_name) != set(definitions):
            raise ValueError("unexpected or duplicate OpenAI decision names")
        fields = {}
        sentiment = dict(
            zip(
                list(definitions["sentiment"]["criteria"])[:-1],
                [-1.0, -0.5, 0.0, 0.5, 1.0],
            )
        )
        for name, question in definitions.items():
            answer = by_name[name]
            if answer.get("type") == "refusal":
                fields[name] = {"refusal": True}
                continue
            rows = answer.get("probabilities")
            if answer.get("type") != "choice" or not isinstance(rows, list):
                raise ValueError("expected OpenAI choice probabilities")
            probabilities = {item["value"]: item["probability"] for item in rows}
            if (
                len(probabilities) != len(rows)
                or set(probabilities) != set(question["criteria"])
                or any(
                    type(v) not in (int, float)
                    or not math.isfinite(v)
                    or not 0 <= v <= 1
                    for v in probabilities.values()
                )
                or abs(sum(probabilities.values()) - 1) > 0.01
                or answer.get("choice") not in probabilities
            ):
                raise ValueError("invalid OpenAI decision probability distribution")
            choice = answer["choice"]
            if probabilities[choice] < max(probabilities.values()):
                raise ValueError("choice differs from maximum probability")
            fields[name] = {
                "value": sentiment.get(choice) if name == "sentiment" else choice,
                "confidence": answer.get("confidence"),
                "probabilities": probabilities,
                "probability": probabilities[choice],
                "target_id": schema.targets[0].id,
            }
        return {
            "records": [{"post_id": posts[0].post_id, "fields": fields}],
            "usage": result.get("usage", {}),
            "cost": None,
        }
