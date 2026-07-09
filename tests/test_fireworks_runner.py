import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from router.core.contracts import TaskEnvelope, TokenUsage
from router.core.fireworks import FireworksClient
from router.core.fireworks_runner import FireworksDirectRunner
from router.core.model_client import ModelClientError, ModelResponse
from router.orchestration.matrix_regression_selector import MatrixRegressionWeights, save_weights
from tests.fake_openai_server import FakeOpenAIServer


class FireworksDirectRunnerTests(unittest.TestCase):
    def test_solver_runs_before_fireworks(self) -> None:
        with FakeOpenAIServer(response_text="should not be called") as server:
            client = FireworksClient(base_url=server.url, model="fake-fireworks", api_key="test", max_retries=0)
            runner = FireworksDirectRunner(client)

            result = runner.run(TaskEnvelope(id="math", input_text="What is 6 * 7? Return only the number."))

        self.assertEqual(result.answer, "42")
        self.assertEqual(result.route, "solver_arithmetic")
        self.assertEqual(result.remote_tokens.total, 0)
        self.assertEqual(len(server.requests), 0)

    def test_calls_fireworks_for_general_task(self) -> None:
        with FakeOpenAIServer(response_text="A concise summary.", prompt_tokens=11, completion_tokens=4) as server:
            client = FireworksClient(base_url=server.url, model="fake-fireworks", api_key="test", max_retries=0)
            runner = FireworksDirectRunner(client)

            result = runner.run(TaskEnvelope(id="summary", input_text="Summarise this: token routing matters."))

        self.assertEqual(result.answer, "A concise summary.")
        self.assertEqual(result.route, "fireworks_direct")
        self.assertEqual(result.remote_tokens.total, 15)
        self.assertEqual(server.requests[0]["payload"]["model"], "fake-fireworks")

    def test_uses_selected_allowed_model_for_task(self) -> None:
        with FakeOpenAIServer(response_text="Fixed implementation.", prompt_tokens=20, completion_tokens=8) as server:
            client = FireworksClient(base_url=server.url, model="fallback-model", api_key="test", max_retries=0)
            runner = FireworksDirectRunner(
                client,
                allowed_models=[
                    "accounts/fireworks/models/llama-v3-8b",
                    "accounts/fireworks/models/llama-v3-70b",
                ],
            )

            result = runner.run(TaskEnvelope(id="code", input_text="Debug this code and provide a corrected implementation."))

        self.assertEqual(result.route, "fireworks_direct")
        self.assertEqual(server.requests[0]["payload"]["model"], "accounts/fireworks/models/llama-v3-70b")
        self.assertEqual(result.metadata["fireworks_model_selection"]["tier"], "strong")
        self.assertEqual(client.model, "fallback-model")

    def test_simple_fireworks_task_sends_reasoning_effort_none(self) -> None:
        with FakeOpenAIServer(response_text="positive", prompt_tokens=12, completion_tokens=2) as server:
            client = FireworksClient(base_url=server.url, model="fallback-model", api_key="test", max_retries=0)
            runner = FireworksDirectRunner(
                client,
                allowed_models=["accounts/fireworks/models/glm-5p1"],
            )

            result = runner.run(TaskEnvelope(id="sentiment", input_text="Classify the sentiment as positive or negative: I love this."))

        self.assertEqual(result.route, "fireworks_direct")
        self.assertEqual(server.requests[0]["payload"]["reasoning_effort"], "none")
        self.assertEqual(server.requests[0]["payload"]["user"], "track1-token-router-v1")
        self.assertEqual(
            result.metadata["fireworks_request_options"],
            {"user": "track1-token-router-v1", "reasoning_effort": "none"},
        )

    def test_gpt_oss_uses_low_reasoning_effort_for_non_strong_task(self) -> None:
        with FakeOpenAIServer(response_text="A concise summary.") as server:
            client = FireworksClient(base_url=server.url, model="fallback-model", api_key="test", max_retries=0)
            runner = FireworksDirectRunner(
                client,
                allowed_models=["accounts/fireworks/models/gpt-oss-120b"],
            )

            runner.run(TaskEnvelope(id="summary", input_text="Summarise this: token routing matters."))

        self.assertEqual(server.requests[0]["payload"]["reasoning_effort"], "low")
        self.assertEqual(server.requests[0]["payload"]["user"], "track1-token-router-v1")

    def test_service_tier_is_sent_only_when_configured(self) -> None:
        with FakeOpenAIServer(response_text="A concise summary.") as server:
            client = FireworksClient(base_url=server.url, model="fallback-model", api_key="test", max_retries=0)
            runner = FireworksDirectRunner(
                client,
                allowed_models=["accounts/fireworks/models/glm-5p1"],
                service_tier="priority",
            )

            result = runner.run(TaskEnvelope(id="summary", input_text="Summarise this: token routing matters."))

        self.assertEqual(result.route, "fireworks_direct")
        self.assertEqual(server.requests[0]["payload"]["service_tier"], "priority")
        self.assertEqual(result.metadata["fireworks_request_options"]["service_tier"], "priority")

    def test_reasoning_option_error_falls_back_without_extra_body(self) -> None:
        client = _RejectReasoningOnceClient()
        runner = FireworksDirectRunner(
            client,  # type: ignore[arg-type]
            allowed_models=["accounts/fireworks/models/glm-5p1"],
        )

        result = runner.run(TaskEnvelope(id="sentiment", input_text="Classify the sentiment as positive or negative: I love this."))

        self.assertEqual(result.answer, "positive")
        self.assertEqual(result.route, "fireworks_direct")
        self.assertEqual(client.extra_bodies, [{"user": "track1-token-router-v1", "reasoning_effort": "none"}, None])
        self.assertIn("reasoning_effort", result.metadata["fireworks_request_options_fallback"])

    def test_model_error_falls_back_to_next_allowed_model(self) -> None:
        with FakeOpenAIServer(
            response_text="Fallback answer.",
            statuses=[404, 200],
            prompt_tokens=9,
            completion_tokens=3,
        ) as server:
            client = FireworksClient(base_url=server.url, model="fallback-model", api_key="test", max_retries=0)
            runner = FireworksDirectRunner(
                client,
                allowed_models=["gemma-4-31b-it", "minimax-m3"],
            )

            result = runner.run(TaskEnvelope(id="summary", input_text="Summarise this: token routing matters."))

        self.assertEqual(result.route, "fireworks_direct")
        self.assertEqual(result.answer, "Fallback answer.")
        self.assertEqual(result.remote_tokens.total, 12)
        self.assertEqual(len(server.requests), 2)
        self.assertNotEqual(server.requests[0]["payload"]["model"], server.requests[1]["payload"]["model"])
        self.assertTrue(result.metadata["fireworks_attempt_errors"])
        self.assertEqual(client.model, "fallback-model")

    def test_unavailable_model_is_skipped_after_first_404(self) -> None:
        with FakeOpenAIServer(
            responses=["First fallback.", "Second fallback."],
            statuses=[404, 200, 200],
            prompt_tokens=9,
            completion_tokens=3,
        ) as server:
            client = FireworksClient(base_url=server.url, model="fallback-model", api_key="test", max_retries=0)
            runner = FireworksDirectRunner(
                client,
                allowed_models=["gemma-4-31b-it", "minimax-m3"],
            )

            first = runner.run(TaskEnvelope(id="summary-1", input_text="Summarise this: token routing matters."))
            second = runner.run(TaskEnvelope(id="summary-2", input_text="Summarise this: local routing matters."))

        requested_models = [request["payload"]["model"] for request in server.requests]
        self.assertEqual(first.answer, "First fallback.")
        self.assertEqual(second.answer, "Second fallback.")
        self.assertEqual(
            requested_models,
            [
                "accounts/fireworks/models/gemma-4-31b-it",
                "accounts/fireworks/models/minimax-m3",
                "accounts/fireworks/models/minimax-m3",
            ],
        )
        self.assertEqual(
            second.metadata["fireworks_unavailable_models"],
            ["accounts/fireworks/models/gemma-4-31b-it"],
        )

    def test_matrix_weights_can_override_nash_selection(self) -> None:
        weights = MatrixRegressionWeights(
            feature_names=[
                "bias",
                "tier_cheap",
                "tier_strong",
                "domain_formatting",
                "domain_classification",
                "domain_math_reasoning",
                "domain_logic",
                "domain_code_generation",
                "capability",
                "correlation",
                "reliability",
                "cost_utility",
                "latency_utility",
                "nash_product",
                "prisoner_payoff",
                "family_gpt_oss",
                "family_deepseek",
                "family_minimax",
                "family_kimi",
                "family_qwen",
                "reasoning_none",
                "reasoning_low",
                "reasoning_medium",
                "reasoning_omitted",
            ],
            coefficients=[
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                10.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
            ],
            ridge_lambda=0.35,
            training_rows=1,
            target_mean=1.0,
        )
        with tempfile.TemporaryDirectory() as tmp:
            weights_path = Path(tmp) / "weights.json"
            save_weights(weights, weights_path)
            with FakeOpenAIServer(response_text="Kimi-selected answer.") as server:
                client = FireworksClient(base_url=server.url, model="fallback-model", api_key="test", max_retries=0)
                runner = FireworksDirectRunner(
                    client,
                    allowed_models=["minimax-m3", "kimi-k2p7-code"],
                    matrix_weights_path=weights_path,
                )

                result = runner.run(TaskEnvelope(id="summary", input_text="Summarise this: token routing matters."))

        self.assertEqual(result.route, "fireworks_direct")
        self.assertEqual(server.requests[0]["payload"]["model"], "accounts/fireworks/models/kimi-k2p7-code")
        self.assertEqual(
            result.metadata["fireworks_matrix_selection"]["selection_rule"],
            "matrix_regression_plus_nash",
        )

    def test_submit_track1_with_fireworks_mode_and_allowed_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "tasks.json"
            output_path = root / "results.json"
            input_path.write_text(
                json.dumps([{"task_id": "t1", "prompt": "Summarise this: token routing matters."}]),
                encoding="utf-8",
            )
            with FakeOpenAIServer(response_text="Token routing matters.") as server:
                env = {
                    **os.environ,
                    "ROUTER_MODE": "fireworks",
                    "FIREWORKS_API_KEY": "test-key",
                    "FIREWORKS_BASE_URL": server.url,
                    "ALLOWED_MODELS": "fake-fireworks,other-model",
                    "FIREWORKS_MAX_RETRIES": "0",
                    "ROUTER_LOG_PATH": str(root / "run.jsonl"),
                }
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "router",
                        "submit-track1",
                        "--input",
                        str(input_path),
                        "--output",
                        str(output_path),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    env=env,
                )
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.stdout, "")
        self.assertEqual(payload, [{"task_id": "t1", "answer": "Token routing matters."}])

class _RejectReasoningOnceClient:
    def __init__(self) -> None:
        self.model = "accounts/fireworks/models/glm-5p1"
        self.extra_bodies: list[dict[str, object] | None] = []

    def complete(
        self,
        _messages: list[dict[str, str]],
        *,
        temperature: float,
        max_tokens: int,
        extra_body: dict[str, object] | None = None,
    ) -> ModelResponse:
        self.extra_bodies.append(extra_body)
        if extra_body:
            raise ModelClientError("Invalid reasoning_effort: none")
        return ModelResponse(text="positive", usage=TokenUsage(prompt=4, completion=1, total=5))


if __name__ == "__main__":
    unittest.main()
