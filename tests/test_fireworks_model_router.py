import unittest

from router.core.contracts import TaskEnvelope
from router.orchestration.fireworks_model_router import (
    DOMAIN_CORRELATION_MATRIX,
    normalize_fireworks_model_id,
    rank_fireworks_models,
    select_fireworks_model,
    select_reasoning_effort,
)


FIREWORKS_PARETO_CATALOG = [
    "accounts/fireworks/models/glm-5p2",
    "accounts/fireworks/models/kimi-k2p7-code",
    "accounts/fireworks/models/qwen3p7-plus",
    "accounts/fireworks/models/minimax-m3",
    "accounts/fireworks/models/deepseek-v4-pro",
    "accounts/fireworks/models/kimi-k2p6",
    "accounts/fireworks/models/minimax-m2p7",
    "accounts/fireworks/models/glm-5p1",
    "accounts/fireworks/models/gpt-oss-20b",
    "accounts/fireworks/models/gpt-oss-120b",
    "accounts/fireworks/models/nemotron-3-ultra-nvfp4",
    "accounts/fireworks/models/deepseek-v4-flash",
    "accounts/fireworks/models/qwen3-reranker-8b",
    "accounts/fireworks/models/qwen3-embedding-8b",
]

TRACK1_ALLOWED_SHORT_NAMES = [
    "minimax-m3",
    "kimi-k2p7-code",
    "gemma-4-31b-it",
    "gemma-4-26b-a4b-it",
    "gemma-4-31b-it-nvfp4",
]


class FireworksModelRouterTests(unittest.TestCase):
    def test_ranks_models_by_inferred_size(self) -> None:
        ranked = rank_fireworks_models(
            [
                "accounts/fireworks/models/llama-v3-70b",
                "accounts/fireworks/models/llama-v3-8b",
                "accounts/fireworks/models/tiny-router",
            ]
        )

        self.assertEqual(ranked[0], "accounts/fireworks/models/tiny-router")
        self.assertEqual(ranked[-1], "accounts/fireworks/models/llama-v3-70b")

    def test_known_pricing_beats_parameter_count_for_ranking(self) -> None:
        ranked = rank_fireworks_models(
            [
                "accounts/fireworks/models/glm-5p1",
                "accounts/fireworks/models/gpt-oss-120b",
                "accounts/fireworks/models/deepseek-v4-pro",
            ]
        )

        self.assertEqual(ranked[0], "accounts/fireworks/models/gpt-oss-120b")

    def test_normalizes_track1_allowed_short_names(self) -> None:
        ranked = rank_fireworks_models(TRACK1_ALLOWED_SHORT_NAMES)

        self.assertIn("accounts/fireworks/models/minimax-m3", ranked)
        self.assertIn("accounts/fireworks/models/kimi-k2p7-code", ranked)
        self.assertIn("accounts/fireworks/models/gemma-4-31b-it", ranked)
        self.assertEqual(
            normalize_fireworks_model_id("gemma-4-31b-it-nvfp4"),
            "accounts/fireworks/models/gemma-4-31b-it-nvfp4",
        )

    def test_track1_allowed_catalog_can_route_with_short_names(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(input_text="Return exactly this string and nothing else: ACK-742"),
            TRACK1_ALLOWED_SHORT_NAMES,
        )

        self.assertTrue(selection.model.startswith("accounts/fireworks/models/"))
        self.assertIn(selection.model, rank_fireworks_models(TRACK1_ALLOWED_SHORT_NAMES))

    def test_track1_allowed_catalog_uses_minimax_for_strong_reasoning(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(
                input_text=(
                    "A plan costs 80. It receives a 15 percent discount and then a 5 fee is added. "
                    "Return only the final number."
                )
            ),
            TRACK1_ALLOWED_SHORT_NAMES,
        )

        self.assertEqual(selection.domain, "math_reasoning")
        self.assertEqual(selection.tier, "strong")
        self.assertEqual(selection.model, "accounts/fireworks/models/minimax-m3")

    def test_track1_allowed_catalog_still_uses_gemma_for_medium_language_tasks(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(input_text="Summarise this: Local verification reduces remote token spend."),
            TRACK1_ALLOWED_SHORT_NAMES,
        )

        self.assertEqual(selection.domain, "summarization")
        self.assertTrue(selection.model.endswith("gemma-4-31b-it-nvfp4"))

    def test_gemma_does_not_send_reasoning_effort(self) -> None:
        self.assertIsNone(select_reasoning_effort("accounts/fireworks/models/gemma-4-31b-it", "cheap"))

    def test_sentiment_uses_cheapest_model(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(input_text="Classify the sentiment as positive, negative, or neutral."),
            [
                "accounts/fireworks/models/llama-v3-70b",
                "accounts/fireworks/models/llama-v3-8b",
            ],
        )

        self.assertEqual(selection.tier, "cheap")
        self.assertEqual(selection.model, "accounts/fireworks/models/llama-v3-8b")
        self.assertEqual(selection.domain, "classification")

    def test_return_exactly_is_formatting_domain(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(input_text="Return exactly this string and nothing else: ACK-742"),
            ["accounts/fireworks/models/gpt-oss-20b"],
        )

        self.assertEqual(selection.tier, "cheap")
        self.assertEqual(selection.domain, "formatting")

    def test_known_does_not_trigger_now_keyword(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(input_text="Which planet is known as the Red Planet? Return only the planet name."),
            TRACK1_ALLOWED_SHORT_NAMES,
        )

        self.assertEqual(selection.tier, "medium")
        self.assertEqual(selection.domain, "current_factual")

    def test_lowercase_version_is_formatting_not_current_factual(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(input_text="Return only the lowercase version of this text: FIREWORKS_ROUTE_ABC"),
            TRACK1_ALLOWED_SHORT_NAMES,
        )

        self.assertEqual(selection.tier, "cheap")
        self.assertEqual(selection.domain, "formatting")

    def test_accurate_does_not_trigger_rate_keyword(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(
                input_text=(
                    "Summarize in at most 7 words: "
                    "A routing agent should choose the cheapest accurate model for each task."
                )
            ),
            TRACK1_ALLOWED_SHORT_NAMES,
        )

        self.assertEqual(selection.tier, "medium")
        self.assertEqual(selection.domain, "summarization")

    def test_ordering_logic_with_return_only_is_logic_domain(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(input_text="Ava is taller than Bea. Bea is taller than Cora. Who is the shortest? Return only the name."),
            TRACK1_ALLOWED_SHORT_NAMES,
        )

        self.assertEqual(selection.tier, "strong")
        self.assertEqual(selection.domain, "logic")

    def test_modus_ponens_with_return_exactly_is_logic_domain(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(input_text="If the alarm is armed, the door locks. The alarm is armed. Return exactly yes or no."),
            TRACK1_ALLOWED_SHORT_NAMES,
        )

        self.assertEqual(selection.tier, "strong")
        self.assertEqual(selection.domain, "logic")

    def test_if_word_problem_with_numbers_stays_math_reasoning(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(
                input_text=(
                    "If 3 identical machines produce 18 widgets per hour, "
                    "how many widgets per hour do 2 machines produce? Return only the number."
                )
            ),
            TRACK1_ALLOWED_SHORT_NAMES,
        )

        self.assertEqual(selection.tier, "strong")
        self.assertEqual(selection.domain, "math_reasoning")

    def test_direct_arithmetic_is_math_reasoning_not_formatting(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(input_text="Compute 17 * 6 + 4. Return only the number."),
            TRACK1_ALLOWED_SHORT_NAMES,
        )

        self.assertEqual(selection.tier, "medium")
        self.assertEqual(selection.domain, "math_reasoning")

    def test_json_numeric_minmax_is_math_reasoning_not_formatting(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(input_text="Return only minified JSON. Given values [17, 4, 23, 9], return min and max."),
            TRACK1_ALLOWED_SHORT_NAMES,
        )

        self.assertEqual(selection.tier, "medium")
        self.assertEqual(selection.domain, "math_reasoning")

    def test_field_extraction_preempts_formatting_and_arithmetic_looking_codes(self) -> None:
        cases = [
            "Return only the title from this record. Title: Quiet Routers Win. Author: R. Silva. Year: 2026.",
            "Return only the invoice code from this sentence: Please reconcile invoice INV-2026-884 before Friday.",
        ]
        for prompt in cases:
            with self.subTest(prompt=prompt):
                selection = select_fireworks_model(TaskEnvelope(input_text=prompt), TRACK1_ALLOWED_SHORT_NAMES)

                self.assertEqual(selection.tier, "medium")
                self.assertEqual(selection.domain, "extraction")

    def test_define_function_is_code_generation_domain(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(input_text="Return only Python code. Define a function is_palindrome(text)."),
            ["accounts/fireworks/models/minimax-m3"],
        )

        self.assertEqual(selection.tier, "strong")
        self.assertEqual(selection.domain, "code_generation")

    def test_write_python_function_is_code_generation_domain(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(input_text="Write a Python function add(a, b) that returns the sum."),
            TRACK1_ALLOWED_SHORT_NAMES,
        )

        self.assertEqual(selection.tier, "strong")
        self.assertEqual(selection.domain, "code_generation")

    def test_fix_this_python_code_is_code_debug_domain(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(input_text="Fix this Python code: def add(a, b): return a - b"),
            TRACK1_ALLOWED_SHORT_NAMES,
        )

        self.assertEqual(selection.tier, "strong")
        self.assertEqual(selection.domain, "code_debug")

    def test_syllogism_is_logic_domain(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(input_text="All daxes are lims. No lims are vors. Can a dax be a vor?"),
            ["accounts/fireworks/models/gpt-oss-120b"],
        )

        self.assertEqual(selection.tier, "strong")
        self.assertEqual(selection.domain, "logic")

    def test_quantified_guarantee_question_is_logic_not_formatting(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(
                input_text=(
                    "All merls are tivas. Some tivas are roons. "
                    "Is it guaranteed that some merls are roons? Return exactly yes or no."
                )
            ),
            TRACK1_ALLOWED_SHORT_NAMES,
        )

        self.assertEqual(selection.tier, "strong")
        self.assertEqual(selection.domain, "logic")

    def test_code_generation_uses_strongest_model(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(input_text="Write a function that parses nested JSON and handles edge cases."),
            [
                "accounts/fireworks/models/llama-v3-8b",
                "accounts/fireworks/models/llama-v3-70b",
            ],
        )

        self.assertEqual(selection.tier, "strong")
        self.assertEqual(selection.model, "accounts/fireworks/models/llama-v3-70b")

    def test_code_generation_uses_cheapest_sufficient_pareto_candidate(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(input_text="Write a function that parses nested JSON and handles edge cases."),
            [
                "accounts/fireworks/models/gpt-oss-120b",
                "accounts/fireworks/models/glm-5p1",
                "accounts/fireworks/models/deepseek-v4-pro",
                "accounts/fireworks/models/kimi-k2p6",
            ],
        )

        self.assertEqual(selection.tier, "strong")
        self.assertEqual(selection.domain, "code_generation")
        self.assertEqual(selection.model, "accounts/fireworks/models/kimi-k2p6")
        self.assertIn("accounts/fireworks/models/kimi-k2p6", selection.pareto_frontier)

    def test_full_catalog_routes_code_to_cheapest_sufficient_generation_model(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(input_text="Write a function that parses nested JSON and handles edge cases."),
            FIREWORKS_PARETO_CATALOG,
        )

        self.assertEqual(selection.tier, "strong")
        self.assertEqual(selection.domain, "code_generation")
        self.assertEqual(selection.model, "accounts/fireworks/models/minimax-m3")
        self.assertIn("accounts/fireworks/models/kimi-k2p7-code", selection.pareto_frontier)

    def test_game_theory_summary_marks_selected_model_as_equilibrium(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(input_text="Write a function that parses nested JSON and handles edge cases."),
            FIREWORKS_PARETO_CATALOG,
        )

        self.assertEqual(selection.game_theory["selection_rule"], "pareto_filtered_nash_welfare")
        self.assertEqual(selection.game_theory["equilibrium_model"], selection.model)
        self.assertEqual(selection.game_theory["equilibrium_type"], "pure_strategy_nash_equilibrium")
        self.assertGreater(selection.game_theory["selected_nash_product"], 0.0)

    def test_correlation_matrix_penalizes_expensive_overescalation(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(input_text="Write a function that parses nested JSON and handles edge cases."),
            FIREWORKS_PARETO_CATALOG,
        )
        minimax = next(candidate for candidate in selection.candidates if candidate["model"].endswith("minimax-m3"))
        kimi = next(candidate for candidate in selection.candidates if candidate["model"].endswith("kimi-k2p7-code"))

        self.assertEqual(DOMAIN_CORRELATION_MATRIX["code_generation"]["code_generation"], 1.0)
        self.assertEqual(minimax["correlation"], 1.0)
        self.assertEqual(kimi["correlation"], 1.0)
        self.assertGreater(minimax["nash_product"], kimi["nash_product"])
        self.assertEqual(minimax["game_label"], "cooperate_token_efficient")
        self.assertEqual(kimi["game_label"], "defect_expensive_overescalation")

    def test_embedding_and_reranker_models_never_enter_response_frontier(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(input_text="Classify the sentiment as positive, negative, or neutral."),
            FIREWORKS_PARETO_CATALOG,
        )

        auxiliary = {
            candidate["model"]: candidate
            for candidate in selection.candidates
            if candidate["kind"] in {"embedding", "reranker"}
        }
        self.assertEqual(selection.model, "accounts/fireworks/models/gpt-oss-20b")
        self.assertEqual(
            sorted(auxiliary),
            [
                "accounts/fireworks/models/qwen3-embedding-8b",
                "accounts/fireworks/models/qwen3-reranker-8b",
            ],
        )
        self.assertTrue(all(not candidate["supports_chat"] for candidate in auxiliary.values()))
        self.assertTrue(all(candidate["dominated"] for candidate in auxiliary.values()))
        self.assertTrue(all(candidate["game_label"] == "non_chat_auxiliary_strategy" for candidate in auxiliary.values()))
        self.assertNotIn("accounts/fireworks/models/qwen3-embedding-8b", selection.pareto_frontier)
        self.assertNotIn("accounts/fireworks/models/qwen3-reranker-8b", selection.pareto_frontier)

    def test_auxiliary_only_allowed_models_raise_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "chat-capable"):
            select_fireworks_model(
                TaskEnvelope(input_text="Classify the sentiment as positive, negative, or neutral."),
                [
                    "accounts/fireworks/models/qwen3-reranker-8b",
                    "accounts/fireworks/models/qwen3-embedding-8b",
                ],
            )

    def test_logic_can_use_low_cost_reasoning_model_on_pareto_frontier(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(input_text="Solve this deductive logic puzzle. All conditions must be satisfied."),
            [
                "accounts/fireworks/models/gpt-oss-120b",
                "accounts/fireworks/models/glm-5p1",
                "accounts/fireworks/models/deepseek-v4-pro",
            ],
        )

        self.assertEqual(selection.model, "accounts/fireworks/models/gpt-oss-120b")
        self.assertEqual(selection.domain, "logic")
        self.assertLess(selection.estimated_cost_usd, 0.001)

    def test_fast_variant_is_available_but_not_selected_when_standard_is_cheaper(self) -> None:
        selection = select_fireworks_model(
            TaskEnvelope(input_text="Summarise this: token routing matters."),
            [
                "accounts/fireworks/models/glm-5p2",
                "accounts/fireworks/routers/glm-5p2-fast",
            ],
        )

        self.assertEqual(selection.model, "accounts/fireworks/models/glm-5p2")
        self.assertEqual(selection.service_path, "standard")
        fast = next(candidate for candidate in selection.candidates if candidate["service_path"] == "fast")
        self.assertFalse(fast["dominated"])

    def test_reasoning_effort_none_for_simple_non_gpt_oss_tasks(self) -> None:
        self.assertEqual(select_reasoning_effort("accounts/fireworks/models/glm-5p1", "cheap"), "none")
        self.assertEqual(select_reasoning_effort("accounts/fireworks/models/kimi-k2p6", "medium"), "none")

    def test_gpt_oss_uses_supported_reasoning_effort_values(self) -> None:
        self.assertEqual(select_reasoning_effort("accounts/fireworks/models/gpt-oss-120b", "cheap"), "low")
        self.assertEqual(select_reasoning_effort("accounts/fireworks/models/gpt-oss-120b", "strong"), "low")


if __name__ == "__main__":
    unittest.main()
