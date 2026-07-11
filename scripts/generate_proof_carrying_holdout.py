#!/usr/bin/env python3
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a deterministic proof-carrying math/logic holdout.")
    parser.add_argument("--output", type=Path, default=Path("evals/proof-carrying/math-logic-holdout.jsonl"))
    args = parser.parse_args(argv)
    rows = build_rows()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps({"rows": len(rows), "accepted": sum(row["expected_accept"] for row in rows), "output": str(output)}))
    return 0


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(family: str, prompt: str, expected: str | None, *, mutation: str) -> None:
        digest = hashlib.sha256((family + "\0" + mutation + "\0" + prompt).encode()).hexdigest()[:16]
        rows.append(
            {
                "id": f"proof_{digest}",
                "family": family,
                "prompt": prompt,
                "expected_accept": expected is not None,
                "expected_answer": expected,
                "mutation_kind": mutation,
                "mutation_lineage": f"proof_holdout_{family}_{digest[:8]}",
                "regression_split": "fresh_holdout",
                "schema_version": "proof-carrying-holdout-v1",
            }
        )

    for index in range(30):
        percent = Decimal((index % 9) + 1) * Decimal("2.5")
        base = Decimal(80 + index * 8)
        expected = base * percent / Decimal(100)
        add(
            "percentage",
            f"What is {percent}% of {base}? Return only the number.",
            _number(expected),
            mutation="numeric_grid",
        )

    for index in range(20):
        base = Decimal(100 + index * 25)
        rate = Decimal((index % 8) + 1) * Decimal(5)
        direction = "increases" if index % 2 == 0 else "decreases"
        sign = Decimal(1) if direction == "increases" else Decimal(-1)
        expected = base + sign * base * rate / Decimal(100)
        add(
            "percentage_change",
            f"A value starts at {base} and {direction} by {rate}%. What is the final value? Return only the number.",
            _number(expected),
            mutation="direction_pair",
        )

    for index in range(20):
        source = Decimal((index % 5) + 2)
        per_unit = Decimal((index % 7) + 3)
        output = source * per_unit
        target = Decimal((index % 9) + 4)
        expected = output / source * target
        add(
            "proportional_rate",
            f"If {source} machines produce {output} widgets, how many widgets do {target} machines produce? Return only the number.",
            _number(expected),
            mutation="ratio_grid",
        )

    conversions = (
        ("kilometers", "meters", Decimal(1000)),
        ("meters", "centimeters", Decimal(100)),
        ("kilograms", "grams", Decimal(1000)),
        ("hours", "minutes", Decimal(60)),
        ("minutes", "seconds", Decimal(60)),
    )
    for index in range(20):
        source, target, factor = conversions[index % len(conversions)]
        value = Decimal(index + 1) / Decimal(4)
        add(
            "unit_conversion",
            f"Convert {value} {source} to {target}. Return only the number.",
            _number(value * factor),
            mutation="unit_grid",
        )

    for index in range(20):
        left = index + 3
        right = (index % 7) + 2
        multiplier = (index % 5) + 2
        expected = (left + right) * multiplier
        add(
            "decimal_ast",
            f"Calculate ({left} + {right}) * {multiplier}. Return only the number.",
            str(expected),
            mutation="parenthesized_expression",
        )

    names = (
        "Ava", "Bea", "Cora", "Dina", "Eli", "Fia", "Gabi", "Hugo", "Iris", "Jade", "Kaio",
        "Lara", "Maya", "Nilo", "Olga", "Pia", "Ravi", "Sara", "Tina", "Ugo", "Vera", "Wanda",
    )
    for index in range(20):
        trio = (names[index], names[index + 1], names[index + 2])
        relation = "older" if index % 2 == 0 else "taller"
        query = "oldest" if relation == "older" else "tallest"
        add(
            "ordering",
            f"{trio[0]} is {relation} than {trio[1]}. {trio[1]} is {relation} than {trio[2]}. Who is the {query}? Return only the name.",
            trio[0],
            mutation=f"ordered_chain_{index}",
        )

    proposition_rows = (
        ("badge is valid", "access is accepted"),
        ("permit is active", "entry is accepted"),
        ("token is valid", "request is accepted"),
        ("seal is intact", "package is accepted"),
        ("key is active", "door is unlocked"),
        ("account is verified", "transfer is accepted"),
        ("certificate is valid", "upload is accepted"),
        ("device is trusted", "session is accepted"),
        ("record is signed", "filing is accepted"),
        ("ticket is valid", "boarding is accepted"),
    )
    for index in range(20):
        antecedent, consequent = proposition_rows[index % len(proposition_rows)]
        consequent_subject, consequent_state = consequent.split(" is ", 1)
        antecedent_subject, antecedent_state = antecedent.split(" is ", 1)
        if index < 10:
            prompt = (
                f"If the {antecedent}, {consequent}. The {antecedent}. "
                f"Is {consequent_subject} {consequent_state}? Return exactly yes or no."
            )
            answer = "yes"
        else:
            negated = consequent.replace(" is ", " is not ", 1)
            prompt = (
                f"If the {antecedent}, {consequent}. {negated.capitalize()}. "
                f"Is the {antecedent_subject} {antecedent_state}? Return exactly yes or no."
            )
            answer = "no"
        add("propositional", prompt, answer, mutation=f"rule_{index}")

    for index in range(20):
        left = f"dax{index}s"
        middle = f"lim{index}s"
        right = f"vor{index}s"
        if index % 2 == 0:
            prompt = (
                f"All {left} are {middle}. No {middle} are {right}. "
                f"Can a dax{index} be a vor{index}? Return exactly yes or no."
            )
        else:
            prompt = (
                f"All {left} are {middle}. Some {middle} are {right}. "
                f"Is it guaranteed that some {left} are {right}? Return exactly yes or no."
            )
        add("quantified", prompt, "no", mutation=f"quantifier_{index}")

    people_groups = (
        ("Ana", "Bruno", "Carla"),
        ("Dora", "Enzo", "Flora"),
        ("Gabi", "Hugo", "Iris"),
        ("Jade", "Kaio", "Lara"),
        ("Maya", "Nilo", "Olga"),
        ("Pia", "Ravi", "Sara"),
        ("Tina", "Ugo", "Vera"),
        ("Wanda", "Xena", "Yara"),
        ("Bela", "Caio", "Dina"),
        ("Ema", "Fabi", "Gino"),
    )
    for index in range(10):
        first, second, third = people_groups[index]
        assignment = (
            f"{first}, {second}, and {third} each own one different pet: cat, dog, or bird. "
            f"{first} does not own the bird. {second} owns the dog. Who owns the cat? Return only the name."
        )
        add("finite_assignment", assignment, first, mutation=f"assignment_{index}")

    blocked_names = people_groups[:8]
    for repeat in range(8):
        first, second, third = blocked_names[repeat]
        blocked = [
            ("unsafe_expression", f"Calculate __import__('os').system('id-{repeat}'). Return only the number."),
            ("inexact_without_rounding", f"Calculate 1 / {3 * (2 * repeat + 1)}. Return only the number."),
            ("divide_by_zero", f"Calculate {repeat + 5} / 0. Return only the number."),
            ("unit_mismatch", f"Convert {repeat + 2} meters to kilograms. Return only the number."),
            ("unused_number", f"What is 15% of {240 + repeat} if unrelated code {90 + repeat} is present? Return only the number."),
            ("ordering_cycle", f"{first} is older than {second}. {second} is older than {first}. Who is the oldest? Return only the name."),
            ("ordering_disconnected", f"{first} is older than {second}. {third} is older than Vera. Who is the oldest? Return only the name."),
            (
                "assignment_underdetermined",
                f"{first}, {second}, and {third} each own one different pet: cat, dog, or bird. "
                f"{first} does not own the bird. Who owns the cat? Return only the name.",
            ),
            (
                "invalid_converse",
                f"If the {first} badge is valid, access is accepted. Access is accepted. Is the {first} badge valid? Return exactly yes or no.",
            ),
            (
                "quantifier_mismatch",
                f"All dax{repeat}s are lim{repeat}s. No tiva{repeat}s are vor{repeat}s. "
                f"Can a dax{repeat} be a vor{repeat}? Return exactly yes or no.",
            ),
        ]
        for family, prompt in blocked:
            add(family, prompt, None, mutation=f"adversarial_{repeat}")
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        details = [(row["id"], row["family"], row["mutation_kind"], row["prompt"]) for row in rows if row["id"] in duplicates]
        raise ValueError(f"Generated holdout IDs must be unique: {details[:10]}")
    return rows


def _number(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return "0" if text == "-0" else text


if __name__ == "__main__":
    raise SystemExit(main())
