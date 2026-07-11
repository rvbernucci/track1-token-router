from scripts.fit_e2b_270m_matrix_regression import FEATURE_NAMES, check, fit, load_population


def test_population_and_matrix_regression_contract() -> None:
    rows, audit = load_population()
    assert len(rows) == 3982
    assert audit["invalid_270m_routes_fireworks"] == 18
    assert len(FEATURE_NAMES) == 13
    result = fit(rows, audit)
    check(result)
    assert result["population"]["correct"] > 0
    assert result["population"]["incorrect"] > 0
    assert len(result["artifact"]["coefficients"]) == 14
    assert result["selection"]["selected"] >= 100
    assert result["selection"]["target_precision_met"] is False
    comparison = result["v2_model_comparison"]
    assert comparison["all_post_contract_correct"] == 828
    assert comparison["correct_with_valid_270m_parameters"] == 823
    assert "global_joint" in comparison["variants"]
    assert "per_intent_five_scores" in comparison["variants"]
