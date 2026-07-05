from __future__ import annotations

from router.core.contracts import TaskEnvelope


M1_SYSTEM_PROMPT = """You are M1, the fast local answer generator.
Answer the user's task directly and naturally.
Preserve the exact output format requested by the task.
Do not mention routing, models, prompts, or internal architecture.
Do not wrap the answer in JSON or XML unless the task itself explicitly asks for that format.
Prefer concise answers when the task is simple."""


def build_m1_messages(task: TaskEnvelope) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": M1_SYSTEM_PROMPT},
        {"role": "user", "content": task.input_text},
    ]

