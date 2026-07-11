from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import re
import resource
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from enum import Enum
from time import perf_counter
from typing import Any, Mapping

from router.core.contracts import TaskEnvelope
from router.orchestration.final_validator import apply_answer_contract


CODE_TASK_SCHEMA_VERSION = "code-task-contract-v1"
CODE_REPORT_SCHEMA_VERSION = "code-verification-report-v1"
MAX_SOURCE_CHARS = 8_000
MAX_AST_NODES = 600
MAX_AST_DEPTH = 40
MAX_LITERAL_ITEMS = 256
MAX_LITERAL_CHARS = 4_096
DEFAULT_TIMEOUT_S = 1.5


class CodeBehavior(str, Enum):
    ADD = "add"
    SQUARE = "square"
    MAX_LIST = "max_list"
    SECOND_LARGEST = "second_largest"
    UNIQUE_PRESERVE_ORDER = "unique_preserve_order"
    NORMALIZE_SLUG = "normalize_slug"
    PALINDROME = "palindrome"


_FAMILY_SIGNATURES: dict[CodeBehavior, tuple[str, tuple[str, ...]]] = {
    CodeBehavior.ADD: ("add", ("a", "b")),
    CodeBehavior.SQUARE: ("square", ("x",)),
    CodeBehavior.MAX_LIST: ("get_max", ("nums",)),
    CodeBehavior.SECOND_LARGEST: ("second_largest", ("numbers",)),
    CodeBehavior.UNIQUE_PRESERVE_ORDER: ("unique_preserve_order", ("items",)),
    CodeBehavior.NORMALIZE_SLUG: ("normalize_slug", ("text",)),
    CodeBehavior.PALINDROME: ("is_palindrome", ("text",)),
}


@dataclass(frozen=True)
class CodeTaskContract:
    language: str
    function_name: str
    parameters: tuple[str, ...]
    behavior: CodeBehavior
    code_only: bool
    schema_version: str = CODE_TASK_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != CODE_TASK_SCHEMA_VERSION:
            raise ValueError("Unsupported CodeTaskContract schema.")
        if self.language != "python":
            raise ValueError("Only Python is supported by this verifier.")
        if not re.fullmatch(r"[A-Za-z_]\w*", self.function_name):
            raise ValueError("Invalid function name.")
        if not self.parameters or any(not re.fullmatch(r"[A-Za-z_]\w*", item) for item in self.parameters):
            raise ValueError("Invalid function parameters.")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["behavior"] = self.behavior.value
        payload["parameters"] = list(self.parameters)
        return payload


@dataclass(frozen=True)
class CodeVerificationReport:
    accepted: bool
    contract: CodeTaskContract | None
    normalized_code: str
    static_passed: bool
    dynamic_passed: bool
    tests_run: int
    tests_passed: int
    properties_run: int
    properties_passed: int
    repeatability_checks_run: int
    repeatability_checks_passed: int
    original_failed: bool | None
    rejection_reasons: tuple[str, ...]
    latency_ms: float
    peak_rss_kib: int
    schema_version: str = CODE_REPORT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["contract"] = self.contract.to_dict() if self.contract else None
        payload["rejection_reasons"] = list(self.rejection_reasons)
        return payload


def infer_code_task_contract(task: TaskEnvelope) -> CodeTaskContract | None:
    text = task.input_text
    lowered = text.casefold()
    if "python" not in lowered and not re.search(r"\bdef\s+[A-Za-z_]\w*\s*\(", text):
        return None
    behavior = _infer_behavior(lowered)
    if behavior is None:
        return None
    default_name, default_parameters = _FAMILY_SIGNATURES[behavior]
    signature = re.search(r"\b([A-Za-z_]\w*)\s*\(([^)]*)\)", text)
    named = re.search(r"(?i)\b(?:named|function)\s+([A-Za-z_]\w*)\b", text)
    function_name = signature.group(1) if signature else named.group(1) if named else default_name
    if signature:
        parameters = tuple(
            item.strip().split(":", 1)[0].strip()
            for item in signature.group(2).split(",")
            if item.strip()
        )
    else:
        parameters = default_parameters
    if not parameters or any(not re.fullmatch(r"[A-Za-z_]\w*", item) for item in parameters):
        return None
    if function_name != default_name:
        # Families are behavior templates, but the prompt may intentionally rename simple add/square functions.
        if behavior not in {CodeBehavior.ADD, CodeBehavior.SQUARE}:
            return None
    return CodeTaskContract(
        language="python",
        function_name=function_name,
        parameters=parameters,
        behavior=behavior,
        code_only=bool(re.search(r"(?i)\b(?:return|write|provide)\s+only\b", text)),
    )


def verify_code_candidate(
    task: TaskEnvelope,
    candidate: str,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> CodeVerificationReport:
    started = perf_counter()
    contract = infer_code_task_contract(task)
    if contract is None:
        return _report(started, None, candidate.strip(), False, False, rejection=("unsupported_or_ambiguous_contract",))
    normalized = _normalize_candidate(task, candidate)
    static_reasons = _static_rejections(normalized, contract)
    if static_reasons:
        return _report(started, contract, normalized, False, False, rejection=tuple(static_reasons))
    original_code = _extract_original_code(task.input_text, normalized)
    dynamic = _run_worker(normalized, contract, timeout_s=timeout_s, original_code=original_code)
    reasons = tuple(str(item) for item in dynamic.get("rejection_reasons", []))
    dynamic_passed = bool(dynamic.get("passed"))
    return CodeVerificationReport(
        accepted=dynamic_passed and not reasons,
        contract=contract,
        normalized_code=normalized,
        static_passed=True,
        dynamic_passed=dynamic_passed,
        tests_run=int(dynamic.get("tests_run", 0)),
        tests_passed=int(dynamic.get("tests_passed", 0)),
        properties_run=int(dynamic.get("properties_run", 0)),
        properties_passed=int(dynamic.get("properties_passed", 0)),
        repeatability_checks_run=int(dynamic.get("repeatability_checks_run", 0)),
        repeatability_checks_passed=int(dynamic.get("repeatability_checks_passed", 0)),
        original_failed=dynamic.get("original_failed") if isinstance(dynamic.get("original_failed"), bool) else None,
        rejection_reasons=reasons,
        latency_ms=(perf_counter() - started) * 1000,
        peak_rss_kib=int(dynamic.get("peak_rss_kib", 0)),
    )


def _infer_behavior(lowered: str) -> CodeBehavior | None:
    if "second-largest" in lowered or "second largest" in lowered or "second_largest" in lowered:
        return CodeBehavior.SECOND_LARGEST
    if "unique_preserve_order" in lowered or ("remove" in lowered and "duplicates" in lowered and "preserv" in lowered):
        return CodeBehavior.UNIQUE_PRESERVE_ORDER
    if "normalize_slug" in lowered or ("lowercase" in lowered and "hyphen" in lowered):
        return CodeBehavior.NORMALIZE_SLUG
    if "palindrome" in lowered or "is_palindrome" in lowered:
        return CodeBehavior.PALINDROME
    if "get_max" in lowered or ("maximum" in lowered and "list" in lowered) or "max of a list" in lowered:
        return CodeBehavior.MAX_LIST
    if re.search(r"\bsquare\s*\(", lowered) or "returns x squared" in lowered or "return x squared" in lowered:
        return CodeBehavior.SQUARE
    if re.search(r"\badd\s*\(", lowered) or "returns their sum" in lowered or "return their sum" in lowered:
        return CodeBehavior.ADD
    return None


def _normalize_candidate(task: TaskEnvelope, candidate: str) -> str:
    contract = apply_answer_contract(task, candidate)
    if contract.valid and contract.answer:
        return contract.answer.strip()
    stripped = candidate.strip()
    fenced = re.fullmatch(r"```(?:python|py)?\s*(.*?)\s*```", stripped, re.DOTALL | re.IGNORECASE)
    return fenced.group(1).strip() if fenced else stripped


def _static_rejections(source: str, contract: CodeTaskContract) -> list[str]:
    reasons: list[str] = []
    if not source or len(source) > MAX_SOURCE_CHARS:
        return ["source_size_limit"]
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ["invalid_python_syntax"]
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_AST_NODES or _ast_depth(tree) > MAX_AST_DEPTH:
        reasons.append("ast_complexity_limit")
    functions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    non_docstring = [
        node
        for node in tree.body
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str))
    ]
    if non_docstring:
        reasons.append("module_level_side_effect")
    if not functions or len(functions) != 1 or isinstance(functions[0], ast.AsyncFunctionDef):
        reasons.append("requires_exactly_one_sync_function")
        return list(dict.fromkeys(reasons))
    function = functions[0]
    if function.name != contract.function_name:
        reasons.append("function_name_mismatch")
    parameters = tuple(argument.arg for argument in function.args.args)
    if (
        parameters != contract.parameters
        or function.args.posonlyargs
        or function.args.vararg
        or function.args.kwarg
        or function.args.kwonlyargs
        or function.args.defaults
        or function.args.kw_defaults
    ):
        reasons.append("function_signature_mismatch")
    if function.decorator_list:
        reasons.append("decorators_forbidden")
    if not function.body or all(isinstance(node, (ast.Pass, ast.Expr)) for node in function.body):
        reasons.append("placeholder_body")
    for node in nodes:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.With, ast.AsyncWith, ast.Lambda)):
            reasons.append(f"forbidden_ast:{type(node).__name__}")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            reasons.append("dunder_access_forbidden")
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)) and len(node.value) > MAX_LITERAL_CHARS:
            reasons.append("literal_size_limit")
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)) and len(node.elts) > MAX_LITERAL_ITEMS:
            reasons.append("literal_size_limit")
        if isinstance(node, ast.Dict) and len(node.keys) > MAX_LITERAL_ITEMS:
            reasons.append("literal_size_limit")
        if isinstance(node, ast.Attribute) and (node.attr.startswith("__") or node.attr in _FORBIDDEN_ATTRIBUTES):
            reasons.append(f"forbidden_attribute:{node.attr}")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id not in _ALLOWED_CALLS | {contract.function_name}:
                reasons.append(f"forbidden_call:{node.func.id}")
            if isinstance(node.func, ast.Attribute) and node.func.attr not in _ALLOWED_METHODS:
                reasons.append(f"forbidden_method:{node.func.attr}")
    return list(dict.fromkeys(reasons))


_ALLOWED_CALLS = {
    "abs", "all", "any", "bool", "dict", "enumerate", "float", "int", "len", "list", "max", "min",
    "range", "reversed", "set", "sorted", "str", "sum", "tuple", "zip",
}
_ALLOWED_METHODS = {"add", "append", "count", "items", "join", "keys", "lower", "replace", "reverse", "sort", "strip", "values"}
_FORBIDDEN_ATTRIBUTES = {"system", "popen", "fork", "spawn", "socket", "connect", "unlink", "write_text", "write_bytes"}


def _ast_depth(node: ast.AST, depth: int = 0) -> int:
    children = list(ast.iter_child_nodes(node))
    return depth if not children else max(_ast_depth(child, depth + 1) for child in children)


def _extract_original_code(prompt: str, candidate: str) -> str | None:
    if not re.search(r"(?i)\b(?:bug|debug|fix|broken|corrected)\b", prompt):
        return None
    fenced = re.findall(r"```(?:python|py)?\s*(.*?)\s*```", prompt, re.DOTALL | re.IGNORECASE)
    for block in reversed(fenced):
        if re.search(r"(?m)^\s*def\s+[A-Za-z_]\w*\s*\(", block):
            original = block.strip()
            return original if original != candidate else None
    starts = [match.start() for match in re.finditer(r"(?m)\bdef\s+[A-Za-z_]\w*\s*\(", prompt)]
    if not starts:
        return None
    original = prompt[starts[-1] :].strip()
    original = re.split(r"(?i)\s+(?:find|identify|fix|correct)\s+(?:the|it)\b", original, maxsplit=1)[0].strip()
    return original if original and original != candidate else None


def _run_worker(
    source: str,
    contract: CodeTaskContract,
    *,
    timeout_s: float,
    original_code: str | None,
) -> dict[str, Any]:
    payload = {"source": source, "contract": contract.to_dict(), "original_code": original_code}
    with tempfile.TemporaryDirectory(prefix="code-verifier-") as tmp:
        try:
            completed = subprocess.run(
                [sys.executable, "-I", "-S", "-c", _WORKER],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                cwd=tmp,
                env={"PATH": os.environ.get("PATH", ""), "PYTHONHASHSEED": "0", "LANG": "C.UTF-8"},
                timeout=timeout_s,
                check=False,
                preexec_fn=_resource_limits,
            )
        except subprocess.TimeoutExpired:
            return {"passed": False, "rejection_reasons": ["execution_timeout"]}
    if completed.returncode != 0:
        return {"passed": False, "rejection_reasons": [f"worker_exit:{completed.returncode}"]}
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"passed": False, "rejection_reasons": ["malformed_worker_output"]}
    if not isinstance(result, dict):
        return {"passed": False, "rejection_reasons": ["invalid_worker_output"]}
    if sys.platform == "darwin" and isinstance(result.get("peak_rss_kib"), int):
        result["peak_rss_kib"] //= 1024
    return result


def _resource_limits() -> None:
    limits = [
        (resource.RLIMIT_CPU, 1),
        (resource.RLIMIT_AS, 256 * 1024 * 1024),
        (resource.RLIMIT_FSIZE, 1 * 1024 * 1024),
        (resource.RLIMIT_NOFILE, 16),
    ]
    if hasattr(resource, "RLIMIT_NPROC"):
        limits.append((resource.RLIMIT_NPROC, 1))
    for kind, requested in limits:
        try:
            _, hard = resource.getrlimit(kind)
            effective = requested if hard == resource.RLIM_INFINITY else min(requested, hard)
            resource.setrlimit(kind, (effective, effective))
        except (OSError, ValueError):
            continue


def _report(
    started: float,
    contract: CodeTaskContract | None,
    code: str,
    static: bool,
    dynamic: bool,
    *,
    rejection: tuple[str, ...],
) -> CodeVerificationReport:
    return CodeVerificationReport(
        accepted=False,
        contract=contract,
        normalized_code=code,
        static_passed=static,
        dynamic_passed=dynamic,
        tests_run=0,
        tests_passed=0,
        properties_run=0,
        properties_passed=0,
        repeatability_checks_run=0,
        repeatability_checks_passed=0,
        original_failed=None,
        rejection_reasons=rejection,
        latency_ms=(perf_counter() - started) * 1000,
        peak_rss_kib=0,
    )


_WORKER = r'''
import json
import resource
import sys

payload = json.loads(sys.stdin.read())
source = payload["source"]
contract = payload["contract"]
namespace = {"__builtins__": {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict, "enumerate": enumerate,
    "float": float, "int": int, "len": len, "list": list, "max": max, "min": min, "range": range,
    "reversed": reversed, "set": set, "sorted": sorted, "str": str, "sum": sum, "tuple": tuple, "zip": zip,
}}
reasons = []
try:
    exec(compile(source, "<candidate>", "exec"), namespace, namespace)
    function = namespace[contract["function_name"]]
except Exception as exc:
    print(json.dumps({"passed": False, "rejection_reasons": ["load_error:" + type(exc).__name__]}))
    raise SystemExit(0)

tests = []
properties = []
behavior = contract["behavior"]
if behavior == "add":
    tests = [((2, 3), 5), ((-4, 9), 5), ((0, 0), 0)]
    properties = [((x, y), x + y) for x in range(-12, 13, 3) for y in range(-7, 8, 2)]
elif behavior == "square":
    tests = [((3,), 9), ((-4,), 16), ((0,), 0)]
    properties = [((x,), x * x) for x in range(-30, 31)]
elif behavior == "max_list":
    tests = [(([1, 9, 3],), 9), (([-8, -2, -5],), -2), (([4],), 4)]
    properties = [((values,), max(values)) for values in ([x, -x, x // 2] for x in range(1, 40))]
elif behavior == "second_largest":
    tests = [(([1, 3, 2],), 2), (([5, 5, 4],), 4), (([-1, -3, -2],), -2)]
    properties = [((values,), sorted(set(values))[-2]) for values in ([x, x, x - 1, x - 2] for x in range(-20, 21))]
elif behavior == "unique_preserve_order":
    tests = [(([1, 2, 1, 3],), [1, 2, 3]), (([],), []), ((["a", "a", "b"],), ["a", "b"])]
    sequences = [
        [3, 1, 3, 2, 1], [2, 0, 2, 1, 0], [9, -1, 9, 4, -1],
        ["z", "a", "z", "b"], ["beta", "alpha", "beta"],
    ]
    sequences += [[(n - x) % 5 for x in range(n)] for n in range(1, 40)]
    properties = [((values,), list(dict.fromkeys(values))) for values in sequences]
elif behavior == "normalize_slug":
    tests = [((" Hello World ",), "hello-world"), (("A B C",), "a-b-c"), (("already",), "already")]
    properties = [((" ".join(["Word"] * n),), "-".join(["word"] * n)) for n in range(1, 30)]
elif behavior == "palindrome":
    tests = [(("racecar",), True), (("hello",), False), (("",), True)]
    properties = [((text,), True) for text in ["a", "aa", "aba", "abba", "abcba", "abccba"]]
    properties += [((text,), False) for text in ["ab", "abc", "abca", "route", "router"]]

# Seeded cases are generated by the verifier, never from candidate behavior.
for seed in (7, 29, 101):
    left = (seed * 1103515245 + 12345) % 2001 - 1000
    right = (seed * 214013 + 2531011) % 2001 - 1000
    if behavior == "add":
        properties.append(((left, right), left + right))
    elif behavior == "square":
        properties.append(((left,), left * left))
    elif behavior == "max_list":
        values = [right, left, -left, 0]
        properties.append(((values,), max(values)))
    elif behavior == "second_largest":
        values = [left, left, left - 1, left - 2]
        properties.append(((values,), left - 1))
    elif behavior == "unique_preserve_order":
        values = [left, right, left, 0, right]
        properties.append(((values,), list(dict.fromkeys(values))))
    elif behavior == "normalize_slug":
        text = " Seed " + str(abs(left)) + " Value "
        properties.append(((text,), "seed-" + str(abs(left)) + "-value"))
    elif behavior == "palindrome":
        text = str(abs(left))
        properties.append(((text + text[::-1],), True))

tests_run = tests_passed = properties_run = properties_passed = 0
repeatability_checks_run = repeatability_checks_passed = 0
for index, (args, expected) in enumerate(tests):
    tests_run += 1
    try:
        first = function(*args)
        second = function(*args)
        repeatability_checks_run += 1
        if first == second:
            repeatability_checks_passed += 1
        else:
            reasons.append("nondeterministic_example:" + str(index))
        if first == expected:
            tests_passed += 1
        else:
            reasons.append("example_mismatch:" + str(index))
    except Exception as exc:
        reasons.append("example_error:" + str(index) + ":" + type(exc).__name__)
for index, (args, expected) in enumerate(properties):
    properties_run += 1
    try:
        first = function(*args)
        second = function(*args)
        repeatability_checks_run += 1
        if first == second:
            repeatability_checks_passed += 1
        else:
            reasons.append("nondeterministic_property:" + str(index))
        if first == expected:
            properties_passed += 1
        else:
            reasons.append("property_mismatch:" + str(index))
    except Exception as exc:
        reasons.append("property_error:" + str(index) + ":" + type(exc).__name__)

original_failed = None
if payload.get("original_code"):
    original_namespace = {"__builtins__": namespace["__builtins__"]}
    try:
        exec(compile(payload["original_code"], "<original>", "exec"), original_namespace, original_namespace)
        original = original_namespace[contract["function_name"]]
        original_failed = any(original(*args) != expected for args, expected in tests)
    except Exception:
        original_failed = True
    if not original_failed:
        reasons.append("original_not_proven_broken")

passed = tests_run > 0 and tests_passed == tests_run and properties_passed == properties_run and not reasons
print(json.dumps({
    "passed": passed,
    "tests_run": tests_run,
    "tests_passed": tests_passed,
    "properties_run": properties_run,
    "properties_passed": properties_passed,
    "repeatability_checks_run": repeatability_checks_run,
    "repeatability_checks_passed": repeatability_checks_passed,
    "original_failed": original_failed,
    "rejection_reasons": sorted(set(reasons)),
    "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
}))
'''
