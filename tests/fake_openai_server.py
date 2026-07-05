from __future__ import annotations

from router.dev.fake_provider import FakeOpenAIProvider, FakeProviderConfig


class FakeOpenAIServer(FakeOpenAIProvider):
    def __init__(
        self,
        *,
        response_text: str = "local answer",
        responses: list[str] | None = None,
        status: int = 200,
        delay_s: float = 0.0,
        invalid_json: bool = False,
        prompt_tokens: int = 5,
        completion_tokens: int = 2,
    ) -> None:
        super().__init__(
            config=FakeProviderConfig(
                response_text=response_text,
                responses=tuple(responses or ()),
                status=status,
                delay_s=delay_s,
                invalid_json=invalid_json,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        )
