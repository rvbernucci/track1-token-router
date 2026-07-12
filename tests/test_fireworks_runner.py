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
from router.orchestration.matrix_regression_selector import FEATURE_NAMES, MatrixRegressionWeights, save_weights
from tests.fake_openai_server import FakeOpenAIServer


class FireworksDirectRunnerTests(unittest.TestCase):
    def test_429_503_and_malformed_json_fail_closed_with_one_answer(self) -> None:
        scenarios = (
            {"status": 429},
            {"status": 503},
            {"invalid_json": True},
        )
        for scenario in scenarios:
            with self.subTest(scenario=scenario), FakeOpenAIServer(**scenario) as server:
                client = FireworksClient(
                    base_url=server.url,
                    model="accounts/fireworks/models/minimax-m3",
                    api_key="test",
                    max_retries=0,
                )
                runner = FireworksDirectRunner(
                    client,
                    allowed_models=["accounts/fireworks/models/minimax-m3"],
                    enable_deterministic_solvers=False,
                )

                result = runner.run(TaskEnvelope(id="chaos", input_text="Summarize this sentence."))

            self.assertEqual(result.id, "chaos")
            self.assertEqual(result.route, "fireworks_error")
            self.assertTrue(result.answer)

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
        self.assertEqual(
            server.requests[0]["payload"]["messages"],
            [{"role": "user", "content": "Summarise this: token routing matters."}],
        )
        self.assertEqual(result.metadata["answer_prompt_version"], "raw-prompt-v1")

    def test_repairs_code_fence_for_code_only_task(self) -> None:
        fenced = "```python\ndef add(a, b):\n    return a + b\n```"
        with FakeOpenAIServer(response_text=fenced, prompt_tokens=11, completion_tokens=8) as server:
            client = FireworksClient(base_url=server.url, model="fake-fireworks", api_key="test", max_retries=0)
            runner = FireworksDirectRunner(client)

            result = runner.run(TaskEnvelope(id="code", input_text="Return only Python code. Define a function add(a, b)."))

        self.assertEqual(result.answer, "def add(a, b):\n    return a + b")
        self.assertTrue(result.metadata["final_answer_repaired"])
        self.assertEqual(result.metadata["final_validation"]["expected_format"], "code")

    def test_repairs_leading_reasoning_before_python_code(self) -> None:
        response = (
            "The user wants a Python function, so I will provide one.\n\n"
            "def unique_preserve_order(items):\n"
            "    seen = set()\n"
            "    result = []\n"
            "    for item in items:\n"
            "        if item not in seen:\n"
            "            seen.add(item)\n"
            "            result.append(item)\n"
            "    return result"
        )
        with FakeOpenAIServer(response_text=response, prompt_tokens=11, completion_tokens=55) as server:
            client = FireworksClient(base_url=server.url, model="fake-fireworks", api_key="test", max_retries=0)
            runner = FireworksDirectRunner(client)

            result = runner.run(
                TaskEnvelope(
                    id="code",
                    input_text=(
                        "Write a Python function unique_preserve_order(items) that removes duplicates "
                        "while preserving first occurrence order."
                    ),
                )
            )

        self.assertTrue(result.answer.startswith("def unique_preserve_order(items):"))
        self.assertNotIn("The user wants", result.answer)
        self.assertTrue(result.metadata["final_answer_repaired"])
        self.assertEqual(result.metadata["final_validation"]["reason"], "python_code_with_extra_text")

    def test_does_not_replace_ambiguous_numeric_answer_with_first_number(self) -> None:
        with FakeOpenAIServer(response_text="The candidates are 12 and 7.") as server:
            client = FireworksClient(base_url=server.url, model="fake-fireworks", api_key="test", max_retries=0)
            runner = FireworksDirectRunner(client, enable_deterministic_solvers=False)

            result = runner.run(
                TaskEnvelope(
                    id="number",
                    input_text="According to the supplied context, provide only the final numeric value.",
                )
            )

        self.assertEqual(result.answer, "The candidates are 12 and 7.")
        self.assertFalse(result.metadata["safe_final_validation"]["valid"])
        self.assertFalse(result.metadata["final_answer_repaired"])

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

    def test_number_task_uses_compact_completion_budget(self) -> None:
        with FakeOpenAIServer(response_text="0") as server:
            client = FireworksClient(base_url=server.url, model="fake-fireworks", api_key="test", max_retries=0)
            runner = FireworksDirectRunner(client, max_tokens=512)

            result = runner.run(
                TaskEnvelope(
                    id="number",
                    input_text="Return only the number of vowels in this invented label: rzxby.",
                )
            )

        self.assertEqual(result.route, "fireworks_direct")
        self.assertEqual(server.requests[0]["payload"]["max_tokens"], 16)
        self.assertEqual(result.metadata["fireworks_completion_token_policy"]["expected_format"], "number")
        self.assertEqual(result.metadata["fireworks_completion_token_policy"]["max_tokens"], 16)
        self.assertEqual(
            result.metadata["fireworks_completion_token_policy"]["policy_version"],
            "compact-contract-v3",
        )

    def test_label_and_access_code_use_small_completion_budgets(self) -> None:
        with FakeOpenAIServer(responses=["positive", "5357"]) as server:
            client = FireworksClient(base_url=server.url, model="fake-fireworks", api_key="test", max_retries=0)
            runner = FireworksDirectRunner(client, max_tokens=512, enable_deterministic_solvers=False)

            label = runner.run(
                TaskEnvelope(
                    id="label",
                    input_text="Classify sentiment as positive, negative, or neutral: I love this.",
                )
            )
            access = runner.run(
                TaskEnvelope(
                    id="access",
                    input_text="Context: Project Fjord uses access code 5357. Return only the code.",
                )
            )

        self.assertEqual(label.metadata["fireworks_completion_token_policy"]["expected_format"], "label")
        self.assertEqual(server.requests[0]["payload"]["max_tokens"], 8)
        self.assertEqual(access.metadata["fireworks_completion_token_policy"]["expected_format"], "free_text")
        self.assertEqual(server.requests[1]["payload"]["max_tokens"], 24)

    def test_strong_math_number_task_gets_reasoning_headroom(self) -> None:
        with FakeOpenAIServer(response_text="144") as server:
            client = FireworksClient(base_url=server.url, model="fake-fireworks", api_key="test", max_retries=0)
            runner = FireworksDirectRunner(client, max_tokens=512)

            result = runner.run(
                TaskEnvelope(
                    id="math",
                    input_text=(
                        "A multi-step word problem includes a percentage change and an average. "
                        "Return only the number."
                    ),
                )
            )

        self.assertEqual(result.route, "fireworks_direct")
        self.assertEqual(server.requests[0]["payload"]["max_tokens"], 48)
        self.assertEqual(result.metadata["fireworks_completion_token_policy"]["domain"], "math_reasoning")

    def test_explanatory_comparison_gets_non_truncating_completion_budget(self) -> None:
        with FakeOpenAIServer(response_text="RAM is volatile working memory; ROM is non-volatile firmware storage.") as server:
            client = FireworksClient(base_url=server.url, model="fake-fireworks", api_key="test", max_retries=0)
            runner = FireworksDirectRunner(client, max_tokens=512, enable_deterministic_solvers=False)

            runner.run(
                TaskEnvelope(
                    id="comparison",
                    input_text="Explain the difference between RAM and ROM and what each is used for.",
                )
            )

        self.assertEqual(server.requests[0]["payload"]["max_tokens"], 224)

    def test_code_task_keeps_larger_completion_budget(self) -> None:
        response = "def slugify_title(value):\n    return value.strip().lower().replace(' ', '-')"
        with FakeOpenAIServer(response_text=response) as server:
            client = FireworksClient(base_url=server.url, model="fake-fireworks", api_key="test", max_retries=0)
            runner = FireworksDirectRunner(client, max_tokens=512)

            result = runner.run(
                TaskEnvelope(
                    id="code",
                    input_text=(
                        "Implement a Python function slugify_title(value) that returns a URL slug. "
                        "Return only Python code."
                    ),
                )
            )

        self.assertEqual(result.answer, response)
        self.assertEqual(server.requests[0]["payload"]["max_tokens"], 384)
        self.assertEqual(result.metadata["fireworks_completion_token_policy"]["expected_format"], "code")

    def test_configured_lower_max_tokens_overrides_completion_policy(self) -> None:
        response = "def slugify_title(value):\n    return value.strip().lower().replace(' ', '-')"
        with FakeOpenAIServer(response_text=response) as server:
            client = FireworksClient(base_url=server.url, model="fake-fireworks", api_key="test", max_retries=0)
            runner = FireworksDirectRunner(client, max_tokens=40)

            runner.run(
                TaskEnvelope(
                    id="code",
                    input_text=(
                        "Implement a Python function slugify_title(value) that returns a URL slug. "
                        "Return only Python code."
                    ),
                )
            )

        self.assertEqual(server.requests[0]["payload"]["max_tokens"], 40)

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

    def test_timeout_error_does_not_cascade_across_allowed_models(self) -> None:
        with FakeOpenAIServer(response_text="too late", delay_s=0.2) as server:
            client = FireworksClient(
                base_url=server.url,
                model="fallback-model",
                api_key="test",
                timeout_s=0.01,
                max_retries=0,
            )
            runner = FireworksDirectRunner(
                client,
                allowed_models=["minimax-m3", "kimi-k2p7-code"],
            )

            result = runner.run(TaskEnvelope(id="summary", input_text="Summarise this: token routing matters."))

        self.assertEqual(result.route, "fireworks_error")
        self.assertEqual(result.answer, "Unable to complete the task.")
        self.assertEqual(len(server.requests), 1)
        self.assertIn("timed out", result.metadata["fireworks_attempt_errors"][0]["error"].lower())

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
            feature_names=FEATURE_NAMES,
            coefficients=_coefficients({"family_kimi": 10.0}),
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

    def test_validation_intent_policy_takes_precedence_over_matrix(self) -> None:
        weights = MatrixRegressionWeights(
            feature_names=FEATURE_NAMES,
            coefficients=_coefficients({"family_kimi": 10.0}),
            ridge_lambda=0.35,
            training_rows=1,
            target_mean=1.0,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            weights_path = root / "weights.json"
            save_weights(weights, weights_path)
            policy_path = root / "policy.json"
            policy_path.write_text(
                json.dumps(
                    {
                        "schema_version": "fireworks-intent-policy-v1",
                        "default_enabled": True,
                        "selection_split": "validation",
                        "locked_test_used_for_selection": False,
                        "selection_rule": "validation only",
                        "default_model": "accounts/fireworks/models/kimi-k2p7-code",
                        "allowed_models": [
                            "accounts/fireworks/models/kimi-k2p7-code",
                            "accounts/fireworks/models/minimax-m3",
                        ],
                        "intent_models": {"logic_puzzle": "accounts/fireworks/models/minimax-m3"},
                        "source": {"comparison_report_sha256": "a" * 64},
                    }
                ),
                encoding="utf-8",
            )
            with FakeOpenAIServer(response_text="Yes") as server:
                client = FireworksClient(base_url=server.url, model="fallback-model", api_key="test", max_retries=0)
                runner = FireworksDirectRunner(
                    client,
                    allowed_models=["minimax-m3", "kimi-k2p7-code"],
                    matrix_weights_path=weights_path,
                    intent_policy_path=policy_path,
                )

                result = runner.run(
                    TaskEnvelope(
                        id="logic",
                        input_text="All daxes are wugs. No wugs are zibs. Can any dax be a zib?",
                    )
                )

        self.assertEqual(server.requests[0]["payload"]["model"], "accounts/fireworks/models/minimax-m3")
        self.assertEqual(
            result.metadata["fireworks_intent_policy_selection"]["selection_rule"],
            "validation_only_intent_policy",
        )
        self.assertEqual(result.metadata["fireworks_matrix_selection"]["model"], "accounts/fireworks/models/kimi-k2p7-code")

    def test_global_champion_takes_precedence_when_allowed(self) -> None:
        weights = MatrixRegressionWeights(
            feature_names=FEATURE_NAMES,
            coefficients=_coefficients({"family_minimax": 10.0}),
            ridge_lambda=0.35,
            training_rows=1,
            target_mean=1.0,
        )
        with tempfile.TemporaryDirectory() as tmp:
            weights_path = Path(tmp) / "weights.json"
            save_weights(weights, weights_path)
            with FakeOpenAIServer(response_text="Kimi answer.") as server:
                client = FireworksClient(base_url=server.url, model="fallback-model", api_key="test", max_retries=0)
                runner = FireworksDirectRunner(
                    client,
                    allowed_models=["minimax-m3", "kimi-k2p7-code"],
                    champion_model="accounts/fireworks/models/kimi-k2p7-code",
                    matrix_weights_path=weights_path,
                )

                result = runner.run(TaskEnvelope(id="summary", input_text="Summarize this: routing saves tokens."))

        self.assertEqual(server.requests[0]["payload"]["model"], "accounts/fireworks/models/kimi-k2p7-code")
        self.assertEqual(
            result.metadata["fireworks_champion_selection"]["selection_rule"],
            "validation_selected_global_champion",
        )

    def test_champion_outside_allowed_models_falls_back_without_invalid_call(self) -> None:
        with FakeOpenAIServer(response_text="Minimax fallback.") as server:
            client = FireworksClient(base_url=server.url, model="fallback-model", api_key="test", max_retries=0)
            runner = FireworksDirectRunner(
                client,
                allowed_models=["minimax-m3"],
                champion_model="accounts/fireworks/models/kimi-k2p7-code",
            )

            result = runner.run(TaskEnvelope(id="summary", input_text="Summarize this: routing saves tokens."))

        self.assertEqual(server.requests[0]["payload"]["model"], "accounts/fireworks/models/minimax-m3")
        self.assertEqual(result.metadata["fireworks_champion_selection"]["reason"], "champion_not_runtime_allowed")

    def test_invalid_intent_policy_falls_back_to_matrix(self) -> None:
        weights = MatrixRegressionWeights(
            feature_names=FEATURE_NAMES,
            coefficients=_coefficients({"family_kimi": 10.0}),
            ridge_lambda=0.35,
            training_rows=1,
            target_mean=1.0,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            weights_path = root / "weights.json"
            save_weights(weights, weights_path)
            policy_path = root / "policy.json"
            policy_path.write_text("{}", encoding="utf-8")
            with FakeOpenAIServer(response_text="A summary.") as server:
                client = FireworksClient(base_url=server.url, model="fallback-model", api_key="test", max_retries=0)
                runner = FireworksDirectRunner(
                    client,
                    allowed_models=["minimax-m3", "kimi-k2p7-code"],
                    matrix_weights_path=weights_path,
                    intent_policy_path=policy_path,
                )

                result = runner.run(TaskEnvelope(id="summary", input_text="Summarize this: routing saves tokens."))

        self.assertEqual(server.requests[0]["payload"]["model"], "accounts/fireworks/models/kimi-k2p7-code")
        self.assertIn("error", result.metadata["fireworks_intent_policy_selection"])

    def test_invalid_strict_output_falls_back_to_next_ranked_model(self) -> None:
        weights = MatrixRegressionWeights(
            feature_names=FEATURE_NAMES,
            coefficients=_coefficients({"family_kimi": 10.0}),
            ridge_lambda=0.35,
            training_rows=1,
            target_mean=1.0,
        )
        with tempfile.TemporaryDirectory() as tmp:
            weights_path = Path(tmp) / "weights.json"
            save_weights(weights, weights_path)
            with FakeOpenAIServer(
                responses=[
                    "I will explain the approach first, but I will not provide code yet.",
                    "def normalize_slug(text):\n    return text.strip().lower().replace(' ', '-')",
                ],
                prompt_tokens=10,
                completion_tokens=5,
            ) as server:
                client = FireworksClient(base_url=server.url, model="fallback-model", api_key="test", max_retries=0)
                runner = FireworksDirectRunner(
                    client,
                    allowed_models=["minimax-m3", "kimi-k2p7-code"],
                    matrix_weights_path=weights_path,
                )

                result = runner.run(
                    TaskEnvelope(
                        id="code",
                        input_text=(
                            "Write a Python function normalize_slug(text) that lowercases text, "
                            "trims spaces, and replaces spaces with hyphens. Return only Python code."
                        ),
                    )
                )

        self.assertEqual(result.answer, "def normalize_slug(text):\n    return text.strip().lower().replace(' ', '-')")
        self.assertEqual(result.remote_tokens.total, 30)
        self.assertEqual(len(server.requests), 2)
        self.assertEqual(server.requests[0]["payload"]["model"], "accounts/fireworks/models/kimi-k2p7-code")
        self.assertEqual(server.requests[1]["payload"]["model"], "accounts/fireworks/models/minimax-m3")
        self.assertEqual(result.metadata["fireworks_model"], "accounts/fireworks/models/minimax-m3")
        self.assertEqual(result.metadata["fireworks_invalid_attempts"][0]["reason"], "invalid_python_code")
        self.assertTrue(result.metadata["final_validation"]["valid"])

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

    def test_submit_track1_remote_failure_exits_nonzero_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "tasks.json"
            output_path = root / "results.json"
            input_path.write_text(
                json.dumps([{"task_id": "remote-failure", "prompt": "Summarise this: token routing matters."}]),
                encoding="utf-8",
            )
            with FakeOpenAIServer(status=503) as server:
                env = {
                    **os.environ,
                    "ROUTER_MODE": "fireworks",
                    "FIREWORKS_API_KEY": "test-key",
                    "FIREWORKS_BASE_URL": server.url,
                    "ALLOWED_MODELS": "minimax-m3",
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
                    check=False,
                    capture_output=True,
                    text=True,
                    env=env,
                )

            self.assertNotEqual(completed.returncode, 0)
            self.assertFalse(output_path.exists())
            self.assertIn("refusing to publish a synthetic answer", completed.stderr)

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


def _coefficients(values: dict[str, float]) -> list[float]:
    return [values.get(name, 0.0) for name in FEATURE_NAMES]


if __name__ == "__main__":
    unittest.main()
