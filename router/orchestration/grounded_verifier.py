from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from router.core.contracts import TaskEnvelope
from router.orchestration.final_validator import apply_answer_contract


GROUNDING_REPORT_SCHEMA_VERSION = "grounded-verification-report-v1"
SOURCE_SPAN_SCHEMA_VERSION = "source-span-v1"


class GroundedTaskKind(str, Enum):
    NER = "ner"
    CONTEXT_QA = "context_qa"
    SENTIMENT = "sentiment"
    SUMMARY = "summary"


@dataclass(frozen=True)
class SourceSpan:
    start: int
    end: int
    evidence_text: str
    normalized_value: str
    role: str
    schema_version: str = SOURCE_SPAN_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SOURCE_SPAN_SCHEMA_VERSION:
            raise ValueError("Unsupported source span schema.")
        if self.start < 0 or self.end <= self.start or self.end - self.start != len(self.evidence_text):
            raise ValueError("Invalid source span offsets.")
        if not self.normalized_value or not self.role:
            raise ValueError("Source spans require normalized value and role.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GroundedVerificationReport:
    accepted: bool
    kind: GroundedTaskKind | None
    candidate: str
    reason: str
    spans: tuple[SourceSpan, ...] = ()
    metadata: Mapping[str, Any] | None = None
    schema_version: str = GROUNDING_REPORT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "accepted": self.accepted,
            "kind": self.kind.value if self.kind else None,
            "candidate": self.candidate,
            "reason": self.reason,
            "spans": [span.to_dict() for span in self.spans],
            "metadata": dict(self.metadata or {}),
        }


@dataclass(frozen=True)
class _SourceDocument:
    text: str
    start: int


_DATE_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Janeiro|Fevereiro|Mar[cç]o|Abril|Maio|Junho|Julho|Agosto|Setembro|Outubro|Novembro|Dezembro)"
    r"\s+\d{1,2},?\s+\d{4}\b|\b\d{4}-\d{2}-\d{2}\b",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"(?<!\w)(?:[$€£R]\$?\s*)?\d[\d,.]*(?:\s*(?:%|USD|EUR|BRL|dollars?|euros?|reais))?(?!\w)", re.IGNORECASE)
_ENTITY_TYPES = {"PERSON", "ORG", "ORGANIZATION", "LOC", "LOCATION", "DATE", "MONEY", "MISC"}


def verify_grounded_candidate(task: TaskEnvelope, candidate: str) -> GroundedVerificationReport:
    kind = _infer_kind(task.input_text)
    if kind is None:
        return _report(False, None, candidate.strip(), "unsupported_grounded_contract")
    if kind is GroundedTaskKind.NER:
        return _verify_ner(task, candidate)
    if kind is GroundedTaskKind.CONTEXT_QA:
        return _verify_context_qa(task, candidate)
    if kind is GroundedTaskKind.SENTIMENT:
        return _verify_sentiment(task, candidate)
    return _verify_summary(task, candidate)


def _infer_kind(prompt: str) -> GroundedTaskKind | None:
    lowered = prompt.casefold()
    if re.search(r"\b(?:summari[sz](?:e|ation|ing)|summary)\b", lowered):
        return GroundedTaskKind.SUMMARY
    if "sentiment" in lowered or "polaridade" in lowered:
        return GroundedTaskKind.SENTIMENT
    if "extract" in lowered and any(token in lowered for token in ("entity", "entities", "json", "person", "organization", "location", "date", "payer", "payee")):
        return GroundedTaskKind.NER
    if any(token in lowered for token in ("use only the context", "based only on the context", "according to the context", "according to the passage")):
        return GroundedTaskKind.CONTEXT_QA
    return None


def _verify_ner(task: TaskEnvelope, candidate: str) -> GroundedVerificationReport:
    source = _extract_source(task.input_text, ("Text", "Input", "Passage", "from"), end_markers=("Return", "Respond", "Output"))
    if source is None:
        return _report(False, GroundedTaskKind.NER, candidate.strip(), "source_not_found")
    if _contains_instruction_injection(source.text):
        return _report(False, GroundedTaskKind.NER, candidate.strip(), "source_instruction_injection_detected")
    mode = _ner_mode(task.input_text)
    contract = apply_answer_contract(_without_source(task, source), candidate)
    typed_root_override = mode == "typed_list" and contract.reason == "json_keys_mismatch"
    if not contract.valid and not typed_root_override:
        return _report(False, GroundedTaskKind.NER, contract.answer, f"answer_contract:{contract.reason}")
    json_candidate = _strip_json_fence(contract.answer or candidate)
    try:
        payload = json.loads(json_candidate)
    except json.JSONDecodeError:
        return _report(False, GroundedTaskKind.NER, json_candidate, "ner_requires_valid_json")

    expected = _requested_entity_schema(task.input_text)
    values: list[tuple[str, str]] = []
    provided_by_role: dict[str, list[str]] = {}
    if mode == "typed_list":
        if not isinstance(payload, list):
            return _report(False, GroundedTaskKind.NER, contract.answer, "typed_entity_list_required")
        for item in payload:
            if not isinstance(item, dict) or set(item) != {"text", "type"}:
                return _report(False, GroundedTaskKind.NER, contract.answer, "invalid_typed_entity_item")
            if not isinstance(item["text"], str) or not isinstance(item["type"], str):
                return _report(False, GroundedTaskKind.NER, contract.answer, "invalid_typed_entity_value")
            entity_type = item["type"].upper()
            if entity_type not in _ENTITY_TYPES:
                return _report(False, GroundedTaskKind.NER, contract.answer, "unsupported_entity_type")
            values.append((entity_type, item["text"]))
            provided_by_role.setdefault(entity_type, []).append(item["text"])
    elif mode == "entity_map":
        if not isinstance(payload, dict) or not payload:
            return _report(False, GroundedTaskKind.NER, contract.answer, "entity_type_map_required")
        for value, entity_type in payload.items():
            if not isinstance(value, str) or not isinstance(entity_type, str) or entity_type.upper() not in _ENTITY_TYPES:
                return _report(False, GroundedTaskKind.NER, contract.answer, "invalid_entity_type_map")
            values.append((entity_type.upper(), value))
            provided_by_role.setdefault(entity_type.upper(), []).append(value)
    else:
        if not isinstance(payload, dict) or set(payload) != set(expected):
            return _report(False, GroundedTaskKind.NER, contract.answer, "ner_schema_key_mismatch")
        list_keys = _list_valued_keys(task.input_text, expected)
        for key in expected:
            raw = payload[key]
            if key in list_keys:
                if not isinstance(raw, list) or any(not isinstance(item, (str, int, float)) or isinstance(item, bool) for item in raw):
                    return _report(False, GroundedTaskKind.NER, contract.answer, f"cardinality_mismatch:{key}")
                values.extend((key, str(item)) for item in raw)
                provided_by_role[key] = [str(item) for item in raw]
            else:
                if not isinstance(raw, (str, int, float)) or isinstance(raw, bool):
                    return _report(False, GroundedTaskKind.NER, contract.answer, f"cardinality_mismatch:{key}")
                values.append((key, str(raw)))
                provided_by_role[key] = [str(raw)]

    normalized_values = [_normalize_value(value) for _, value in values]
    if len(normalized_values) != len(set(normalized_values)):
        return _report(False, GroundedTaskKind.NER, contract.answer, "duplicate_entity_value")

    payment_roles = _payment_role_values(source.text)
    spans: list[SourceSpan] = []
    occupied: list[tuple[int, int]] = []
    for role, value in values:
        matches = _find_value_spans(source, value, role)
        if not matches:
            return _report(False, GroundedTaskKind.NER, contract.answer, f"entity_absent_from_source:{role}")
        selected = matches[0]
        if not _entity_role_supported(role, selected, source, payment_roles):
            return _report(False, GroundedTaskKind.NER, contract.answer, f"ambiguous_or_wrong_entity_role:{role}")
        bounds = (selected.start, selected.end)
        if any(max(bounds[0], prior[0]) < min(bounds[1], prior[1]) for prior in occupied):
            return _report(False, GroundedTaskKind.NER, contract.answer, "overlapping_entities")
        occupied.append(bounds)
        spans.append(selected)

    if mode == "typed_list" and "all named entities" in task.input_text.casefold():
        for role in ("PERSON", "ORG", "LOCATION", "DATE"):
            detected = {_normalize_value(value) for value in _detected_role_values(source.text, role)}
            aliases = {
                "PERSON": ("PERSON",),
                "ORG": ("ORG", "ORGANIZATION"),
                "LOCATION": ("LOC", "LOCATION"),
                "DATE": ("DATE",),
            }[role]
            provided = {
                _normalize_value(value)
                for alias in aliases
                for value in provided_by_role.get(alias, [])
            }
            if detected - provided:
                return _report(False, GroundedTaskKind.NER, contract.answer, f"missing_requested_entity:{role.casefold()}")
    if mode == "structured_object":
        for key in _list_valued_keys(task.input_text, expected):
            detected = {_normalize_value(value) for value in _detected_role_values(source.text, key)}
            provided = {_normalize_value(value) for value in provided_by_role.get(key, [])}
            if detected - provided:
                return _report(False, GroundedTaskKind.NER, contract.answer, f"missing_requested_entity:{key}")
    return _report(
        True,
        GroundedTaskKind.NER,
        json_candidate,
        "all_entities_schema_typed_and_source_grounded",
        spans,
        {"requested_keys": list(expected), "mode": mode},
    )


def _verify_context_qa(task: TaskEnvelope, candidate: str) -> GroundedVerificationReport:
    lowered = task.input_text.casefold()
    if not any(token in lowered for token in ("use only the context", "based only on the context", "according to the context", "according to the passage")):
        return _report(False, GroundedTaskKind.CONTEXT_QA, candidate.strip(), "open_world_question_forbidden")
    source = _extract_source(task.input_text, ("Context", "Passage"), end_markers=("Question",))
    question = _extract_marked_value(task.input_text, "Question", end_markers=("Return", "Answer", "Respond", "Output"))
    if source is None or not question:
        return _report(False, GroundedTaskKind.CONTEXT_QA, candidate.strip(), "context_or_question_missing")
    if _contains_instruction_injection(source.text):
        return _report(False, GroundedTaskKind.CONTEXT_QA, candidate.strip(), "source_instruction_injection_detected")
    if re.search(r"\b(?:today|current|currently|latest|now|real-time)\b", question, re.IGNORECASE):
        return _report(False, GroundedTaskKind.CONTEXT_QA, candidate.strip(), "open_world_temporal_question")
    key = _question_key(question)
    if not key:
        return _report(False, GroundedTaskKind.CONTEXT_QA, candidate.strip(), "unsupported_context_question_shape")
    supports = _context_supports(source, key)
    if not supports:
        return _report(False, GroundedTaskKind.CONTEXT_QA, candidate.strip(), "answer_not_present_in_context")
    distinct = {_normalize_value(value) for value, _ in supports}
    if len(distinct) > 1:
        return _report(False, GroundedTaskKind.CONTEXT_QA, candidate.strip(), "conflicting_context_mentions")
    if len(supports) != 1:
        return _report(False, GroundedTaskKind.CONTEXT_QA, candidate.strip(), "support_not_unique")
    contract = apply_answer_contract(_without_source(task, source), candidate)
    if not contract.valid:
        return _report(False, GroundedTaskKind.CONTEXT_QA, contract.answer, f"answer_contract:{contract.reason}")
    expected, span = supports[0]
    if _normalize_value(contract.answer) != _normalize_value(expected):
        return _report(False, GroundedTaskKind.CONTEXT_QA, contract.answer, "candidate_disagrees_with_unique_support")
    return _report(
        True,
        GroundedTaskKind.CONTEXT_QA,
        contract.answer,
        "unique_context_support",
        (span,),
        {"question_key": key},
    )


def _verify_sentiment(task: TaskEnvelope, candidate: str) -> GroundedVerificationReport:
    source = _extract_source(task.input_text, ("Review", "Feedback", "Text", "Avaliação", "Frase"), end_markers=("Return", "Answer", "Respond", "Provide", "Responda"))
    if source is None:
        return _report(False, GroundedTaskKind.SENTIMENT, candidate.strip(), "sentiment_source_not_found")
    if _contains_instruction_injection(source.text):
        return _report(False, GroundedTaskKind.SENTIMENT, candidate.strip(), "source_instruction_injection_detected")
    language = _detect_language(source.text)
    aspect = _extract_aspect(task.input_text)
    evidence_text = _aspect_evidence(source.text, aspect)
    metadata: dict[str, Any] = {"language": language, "aspect": aspect}
    if evidence_text is None:
        return _report(False, GroundedTaskKind.SENTIMENT, candidate.strip(), "aspect_not_explicitly_supported", metadata=metadata)
    if _has_sarcasm(evidence_text):
        return _report(False, GroundedTaskKind.SENTIMENT, candidate.strip(), "sarcasm_or_irony_detected", metadata=metadata)
    lexical = _sentiment_score(evidence_text, language)
    metadata.update(lexical)
    if lexical["mixed"]:
        return _report(False, GroundedTaskKind.SENTIMENT, candidate.strip(), "mixed_sentiment_escalation", metadata=metadata)
    if lexical["label"] is None or lexical["margin"] < 2:
        return _report(False, GroundedTaskKind.SENTIMENT, candidate.strip(), "sentiment_margin_below_threshold", metadata=metadata)
    candidate_label = _candidate_sentiment_label(_without_source(task, source), candidate)
    metadata["candidate_label"] = candidate_label
    if candidate_label is None:
        return _report(False, GroundedTaskKind.SENTIMENT, candidate.strip(), "candidate_label_invalid", metadata=metadata)
    if candidate_label != lexical["label"]:
        return _report(False, GroundedTaskKind.SENTIMENT, candidate.strip(), "e2b_lexicon_disagreement", metadata=metadata)
    spans: list[SourceSpan] = []
    for term in lexical["evidence_terms"]:
        matches = _find_value_spans(source, term, "sentiment_evidence")
        if matches:
            spans.append(matches[0])
    return _report(
        True,
        GroundedTaskKind.SENTIMENT,
        candidate.strip(),
        "high_margin_e2b_lexicon_agreement",
        _dedupe_spans(spans),
        metadata,
    )


def _verify_summary(task: TaskEnvelope, candidate: str) -> GroundedVerificationReport:
    source = _extract_source(task.input_text, ("Text", "Passage", "Source"), end_markers=("Return", "Respond", "Output"))
    if source is None:
        return _report(False, GroundedTaskKind.SUMMARY, candidate.strip(), "summary_source_not_found")
    if re.search(r"(?i)\babstractive\b", task.input_text[: source.start]):
        return _report(False, GroundedTaskKind.SUMMARY, candidate.strip(), "abstractive_summary_requires_remote_model")
    if _contains_instruction_injection(source.text):
        return _report(False, GroundedTaskKind.SUMMARY, candidate.strip(), "source_instruction_injection_detected")
    contract = apply_answer_contract(_without_source(task, source), candidate)
    if not contract.valid:
        return _report(False, GroundedTaskKind.SUMMARY, contract.answer, f"answer_contract:{contract.reason}")
    answer = contract.answer.strip()
    required_terms = _summary_required_terms(task.input_text[: source.start])
    missing = [term for term in required_terms if _normalize_value(term) not in _normalize_value(answer)]
    if missing:
        return _report(False, GroundedTaskKind.SUMMARY, answer, "required_summary_term_missing", metadata={"missing_terms": missing})
    if "include all numbers" in task.input_text.casefold():
        source_numbers = {_normalize_value(match.group(0)) for match in _NUMBER_RE.finditer(source.text)}
        answer_numbers = {_normalize_value(match.group(0)) for match in _NUMBER_RE.finditer(answer)}
        if not source_numbers <= answer_numbers:
            return _report(False, GroundedTaskKind.SUMMARY, answer, "required_number_dropped")
    if "include all named entities" in task.input_text.casefold():
        source_entities = {_normalize_value(value) for value in _named_entities(source.text)}
        answer_entities = {_normalize_value(value) for value in _named_entities(answer)}
        if not source_entities <= answer_entities:
            return _report(False, GroundedTaskKind.SUMMARY, answer, "required_entity_dropped")

    spans: list[SourceSpan] = []
    whole = _find_value_spans(source, answer, "extractive_summary")
    if whole:
        spans.append(whole[0])
    else:
        previous_end = -1
        for sentence in _sentences(answer):
            matches = _find_value_spans(source, sentence, "extractive_summary_sentence")
            ordered = [span for span in matches if span.start > previous_end]
            if not ordered:
                return _report(False, GroundedTaskKind.SUMMARY, answer, "abstractive_summary_not_provably_grounded")
            selected = ordered[0]
            previous_end = selected.end
            spans.append(selected)

    for value in [*(_NUMBER_RE.findall(answer)), *_named_entities(answer)]:
        matches = _find_value_spans(source, value, "summary_fact")
        if not matches:
            return _report(False, GroundedTaskKind.SUMMARY, answer, "unsupported_summary_fact")
        spans.append(matches[0])
    return _report(
        True,
        GroundedTaskKind.SUMMARY,
        answer,
        "extractive_summary_with_grounded_facts",
        _dedupe_spans(spans),
        {"required_terms": required_terms},
    )


def _extract_source(prompt: str, markers: tuple[str, ...], *, end_markers: tuple[str, ...]) -> _SourceDocument | None:
    match = None
    for marker in markers:
        candidate = re.search(rf"(?i)\b{re.escape(marker)}\s*:\s*", prompt)
        if candidate and (match is None or candidate.start() < match.start()):
            match = candidate
    if match is None:
        return None
    start = match.end()
    end = len(prompt)
    for marker in end_markers:
        if marker.casefold() == "question":
            pattern = rf"(?i)\b{re.escape(marker)}\s*:"
        else:
            pattern = rf"(?i)(?:\n|\s{{2,}}|(?<=[.!?])\s+){re.escape(marker)}\b\s*:?"
        stop = re.search(pattern, prompt[start:])
        if stop:
            end = min(end, start + stop.start())
    raw = prompt[start:end]
    leading = len(raw) - len(raw.lstrip())
    raw = raw.lstrip()
    start += leading
    if raw[:1] in {"'", '"'}:
        quote = raw[0]
        closing = raw.rfind(quote)
        if closing > 0:
            raw = raw[1:closing]
            start += 1
    raw = raw.rstrip()
    return _SourceDocument(raw, start) if raw else None


def _extract_marked_value(prompt: str, marker: str, *, end_markers: tuple[str, ...]) -> str | None:
    source = _extract_source(prompt, (marker,), end_markers=end_markers)
    return source.text if source else None


def _without_source(task: TaskEnvelope, source: _SourceDocument) -> TaskEnvelope:
    end = source.start + len(source.text)
    sanitized = task.input_text[: source.start] + "<SOURCE>" + task.input_text[end:]
    return TaskEnvelope(id=task.id, input_text=sanitized, files=task.files, metadata=task.metadata)


def _find_value_spans(source: _SourceDocument, value: str, role: str) -> list[SourceSpan]:
    value = str(value).strip()
    if not value:
        return []
    spans: list[SourceSpan] = []
    for match in re.finditer(re.escape(value), source.text, re.IGNORECASE):
        evidence = source.text[match.start() : match.end()]
        spans.append(SourceSpan(source.start + match.start(), source.start + match.end(), evidence, _normalize_value(value), role))
    if spans:
        return spans
    normalized = _normalize_value(value)
    candidates: Iterable[re.Match[str]] = list(_DATE_RE.finditer(source.text)) + list(_NUMBER_RE.finditer(source.text))
    for match in candidates:
        evidence = match.group(0)
        if _normalize_value(evidence) == normalized:
            spans.append(SourceSpan(source.start + match.start(), source.start + match.end(), evidence, normalized, role))
    return spans


def _normalize_value(value: str) -> str:
    value = re.sub(r"\s+", " ", str(value).strip().casefold())
    date = _normalize_date(value)
    if date:
        return date
    numeric = re.fullmatch(r"(?:[$€£r]\$?\s*)?([\d,.]+)(?:\s*(?:usd|eur|brl|dollars?|euros?|reais|%))?", value)
    if numeric:
        return numeric.group(1).replace(",", "")
    return value.strip(" .,:;!?\"'")


def _normalize_date(value: str) -> str | None:
    iso = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value)
    if iso:
        return value
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
        "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
    }
    folded = _fold_ascii(value).replace(",", "")
    match = re.fullmatch(r"([a-z]+)\s+(\d{1,2})\s+(\d{4})", folded)
    if not match or match.group(1) not in months:
        return None
    return f"{int(match.group(3)):04d}-{months[match.group(1)]:02d}-{int(match.group(2)):02d}"


def _ner_mode(prompt: str) -> str:
    lowered = prompt.casefold()
    if "json array" in lowered and all(token in lowered for token in ('"text"', '"type"')):
        return "typed_list"
    if "keys are the extracted entities" in lowered and "values" in lowered and "entity type" in lowered:
        return "entity_map"
    return "structured_object"


def _requested_entity_schema(prompt: str) -> tuple[str, ...]:
    prefix = re.split(r"(?i)\b(?:Text|Input|Passage|from)\s*:", prompt, maxsplit=1)[0]
    schema = re.search(r"(?i)\bschema\s*:\s*\{(.+)\}", prefix, re.DOTALL)
    if schema:
        return tuple(dict.fromkeys(re.findall(r"[\"']([A-Za-z_][\w-]*)[\"']\s*:", schema.group(1))))
    match = re.search(r"(?i)\bextract\s+(.+?)\s+from\s*:", prompt, re.DOTALL)
    if match:
        raw = re.sub(r"(?i)\b(?:all|the)\b", " ", match.group(1))
        keys = [item.casefold() for item in re.findall(r"[A-Za-z_]+", raw) if item.casefold() not in {"and"}]
        return tuple(dict.fromkeys(keys))
    arrays = re.search(r"(?i)\barrays?\s+for\s+(.+?)\s*:", prefix)
    if arrays:
        return tuple(item.casefold() for item in re.findall(r"[A-Za-z_]+", arrays.group(1)) if item.casefold() != "and")
    return ()


def _list_valued_keys(prompt: str, keys: tuple[str, ...]) -> set[str]:
    lowered = prompt.casefold()
    if "arrays for" in lowered:
        return set(keys)
    return {key for key in keys if re.search(rf"[\"']{re.escape(key)}[\"']\s*:\s*\[", prompt, re.IGNORECASE)}


def _payment_role_values(source: str) -> dict[str, str]:
    match = re.search(
        r"(?i)\b(?:on\s+)?(?P<date>(?:[A-Z][a-zç]+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})),?\s+"
        r"(?P<payer>[A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*){0,4})\s+paid\s+"
        r"(?P<amount>(?:[$€£R]\$?\s*)?\d[\d,.]*(?:\s*(?:USD|EUR|BRL|dollars?|euros?|reais))?)\s+to\s+"
        r"(?P<payee>[A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*){0,4})\b",
        source,
    )
    return {key: value.strip() for key, value in match.groupdict().items()} if match else {}


def _entity_role_supported(role: str, span: SourceSpan, source: _SourceDocument, payment: Mapping[str, str]) -> bool:
    normalized_role = role.upper().rstrip("S")
    key = role.casefold().rstrip("s")
    if key in payment:
        return _normalize_value(span.evidence_text) == _normalize_value(payment[key])
    if normalized_role in {"DATE"} or key == "date":
        return bool(_DATE_RE.fullmatch(span.evidence_text))
    if normalized_role in {"MONEY"} or key == "amount":
        return bool(_NUMBER_RE.fullmatch(span.evidence_text))
    if normalized_role in {"ORG", "ORGANIZATION"} or key in {"organization", "org"}:
        return _looks_organization(span.evidence_text)
    if normalized_role in {"LOC", "LOCATION"} or key in {"location", "city"}:
        local_start = span.start - source.start
        prefix = source.text[max(0, local_start - 16) : local_start]
        return bool(re.search(r"(?i)\b(?:in|at|from|to|near|em|para|de)\s+$", prefix))
    if normalized_role == "PERSON" or key in {"person", "people", "payer", "payee", "customer"}:
        return _looks_person(span.evidence_text)
    return normalized_role == "MISC"


def _looks_organization(value: str) -> bool:
    return bool(re.search(r"(?i)\b(?:corp(?:oration)?|labs?|university|alliance|initiative|foundation|instituto|ltd|inc|group|holdings?)\b", value))


def _looks_person(value: str) -> bool:
    cleaned = re.sub(r"(?i)^(?:Dr\.?|Mr\.?|Ms\.?|CEO)\s+", "", value).strip()
    return bool(re.fullmatch(r"[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'-]+(?:\s+[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'-]+)+", cleaned)) and not _looks_organization(cleaned)


def _detected_role_values(source: str, role: str) -> list[str]:
    key = role.casefold().rstrip("s")
    if key in {"organization", "org"}:
        patterns = (
            r"\b[A-Z][\w'-]*(?:\s+(?:of\s+)?[A-Z][\w'-]+)*\s+(?:Corp(?:oration)?|Labs?|Alliance|Initiative|Foundation|Ltd|Inc|Group|Holdings?)\b",
            r"\bUniversity\s+of\s+[A-Z][\w'-]+\b",
        )
        return list(dict.fromkeys(match.group(0) for pattern in patterns for match in re.finditer(pattern, source)))
    if key in {"location", "city"}:
        return list(
            dict.fromkeys(
                match.group(1)
                for match in re.finditer(r"(?i)\b(?:in|at|from|to|near|em|para)\s+([A-Z][\w'-]+)", source)
            )
        )
    if key in {"person", "people"}:
        matches = re.finditer(r"\b(?:Dr\.?\s+|CEO\s+)?([A-Z][\w'-]+\s+[A-Z][\w'-]+)\b", source)
        return list(dict.fromkeys(match.group(1) for match in matches if not _looks_organization(match.group(1))))
    if key == "date":
        return [match.group(0) for match in _DATE_RE.finditer(source)]
    if key in {"amount", "money"}:
        return [match.group(0) for match in _NUMBER_RE.finditer(source)]
    return []


def _question_key(question: str) -> str | None:
    normalized = re.sub(r"\s+", " ", question.strip())
    match = re.fullmatch(r"(?i)(?:what|who|where)\s+(?:is|was)\s+(?:the\s+)?(.+?)\?", normalized)
    return match.group(1).strip() if match else None


def _context_supports(source: _SourceDocument, key: str) -> list[tuple[str, SourceSpan]]:
    supports: list[tuple[str, SourceSpan]] = []
    pattern = re.compile(
        rf"(?i)(?:\bthe\s+)?{re.escape(key)}\s+(?:is|was|will\s+be|remains)\s+(.+?)(?=[.;!?](?:\s|$)|$)"
    )
    for match in pattern.finditer(source.text):
        value = match.group(1).strip()
        begin, end = match.span(1)
        span = SourceSpan(source.start + begin, source.start + end, source.text[begin:end], _normalize_value(value), "context_support")
        supports.append((value, span))
    key_value = re.compile(rf"(?im)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$")
    for match in key_value.finditer(source.text):
        value = match.group(1).strip()
        begin, end = match.span(1)
        supports.append((value, SourceSpan(source.start + begin, source.start + end, source.text[begin:end], _normalize_value(value), "context_support")))
    return supports


def _detect_language(text: str) -> str:
    folded = _fold_ascii(text.casefold())
    portuguese = len(set(re.findall(r"[a-z]+", folded)) & {"o", "a", "foi", "muito", "mas", "nao", "atendimento", "produto", "rapido", "ruim"})
    return "pt" if portuguese >= 2 or re.search(r"[ãõçáéíóúâêô]", text.casefold()) else "en"


def _extract_aspect(prompt: str) -> str | None:
    match = re.search(r"(?i)(?:toward|towards|about|for)\s+(?:the\s+)?[\"']([^\"']+)[\"'](?:\s+aspect)?", prompt)
    return match.group(1).strip().casefold() if match else None


def _aspect_evidence(text: str, aspect: str | None) -> str | None:
    if not aspect:
        return text
    parts = re.split(r"(?i)\b(?:but|however|yet|mas|por[eé]m)\b|[.;]", text)
    selected = [part.strip() for part in parts if aspect in part.casefold()]
    return " ".join(selected) if selected else None


def _has_sarcasm(text: str) -> bool:
    return bool(
        re.search(r"(?i)\b(?:oh|yeah)\s+(?:great|wonderful|perfect|right)\b", text)
        or re.search(r"(?i)\bthanks?.{0,30}\breally\s+helpful\b", text)
        or re.search(r"(?i)/s\b|\b(?:sarcasm|ironicamente)\b", text)
    )


def _contains_instruction_injection(text: str) -> bool:
    return bool(
        re.search(
            r"(?i)\b(?:ignore|disregard|override|forget|ignora|ignore)\b.{0,80}\b"
            r"(?:instruction|instructions|instru[cç][aã]o|instru[cç][oõ]es|system|prompt|task|tarefa)\b",
            text,
        )
        or re.search(r"(?i)\bsystem\s+(?:warning|message|instruction)\b|\[\s*system\s*\]", text)
        or re.search(
            r"(?i)\b(?:respond|responda|output|write|escreva)\s+(?:just\s+|only\s+|apenas\s+)"
            r"(?:with\s+)?(?:the\s+)?(?:word|palavra|\{|'|\")",
            text,
        )
    )


def _sentiment_score(text: str, language: str) -> dict[str, Any]:
    lexicons = {
        "en": {
            "positive": {"excellent": 2, "amazing": 2, "fantastic": 2, "smooth": 1, "spotless": 2, "helpful": 1, "fast": 1, "attentive": 1, "welcoming": 1, "reliable": 1, "love": 2, "loved": 2, "good": 1, "great": 2, "easy": 1, "satisfied": 2},
            "negative": {"terrible": 2, "horrible": 2, "awful": 2, "broken": 2, "slow": 1, "disappointing": 2, "disappointed": 2, "drains": 2, "crashed": 2, "failed": 2, "poor": 1, "dirty": 2, "rude": 2, "hate": 2, "useless": 2, "worst": 3, "confusing": 1},
            "neutral": {"average", "adequate", "neutral", "standard", "ordinary"},
            "negations": {"not", "never", "no", "hardly"},
            "intensifiers": {"very", "extremely", "incredibly", "really"},
        },
        "pt": {
            "positive": {"excelente": 2, "otimo": 2, "maravilhoso": 2, "maravilhosa": 2, "bom": 1, "rapido": 1, "educado": 1, "confiavel": 1, "adorei": 2, "facil": 1, "satisfeito": 2},
            "negative": {"horrivel": 2, "pessimo": 2, "ruim": 1, "lento": 1, "quebrado": 2, "decepcionante": 2, "falhou": 2, "dificil": 1, "rude": 2, "odiei": 2, "demorou": 1, "demora": 1},
            "neutral": {"medio", "adequado", "neutro", "normal", "comum"},
            "negations": {"nao", "nunca", "nem"},
            "intensifiers": {"muito", "extremamente", "realmente"},
        },
    }
    lexicon = lexicons[language]
    original_tokens = re.findall(r"[^\W\d_]+", text.casefold(), re.UNICODE)
    tokens = [_fold_ascii(token) for token in original_tokens]
    positive = negative = 0
    evidence: list[str] = []
    for index, token in enumerate(tokens):
        polarity = "positive" if token in lexicon["positive"] else "negative" if token in lexicon["negative"] else None
        if polarity is None:
            continue
        weight = int(lexicon[polarity][token])
        if index and tokens[index - 1] in lexicon["intensifiers"]:
            weight += 1
        if set(tokens[max(0, index - 2) : index]) & lexicon["negations"]:
            polarity = "negative" if polarity == "positive" else "positive"
        if polarity == "positive":
            positive += weight
        else:
            negative += weight
        evidence.append(original_tokens[index])
    neutral = bool(set(tokens) & lexicon["neutral"])
    mixed = positive > 0 and negative > 0
    score = positive - negative
    label = "positive" if score > 0 else "negative" if score < 0 else "neutral" if neutral else None
    margin = abs(score) if score else 2 if neutral and not mixed else 0
    return {
        "label": label,
        "margin": margin,
        "positive_score": positive,
        "negative_score": negative,
        "mixed": mixed,
        "evidence_terms": evidence,
    }


def _candidate_sentiment_label(task: TaskEnvelope, candidate: str) -> str | None:
    contract = apply_answer_contract(task, candidate)
    value = contract.answer if contract.valid else candidate.strip()
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        values = [item for key, item in payload.items() if key.casefold() in {"label", "sentiment", "sentimento", "polaridade"}]
        if len(values) != 1 or not isinstance(values[0], str):
            return None
        value = values[0]
    normalized = _fold_ascii(value.casefold().strip(" .,:;!?\"'"))
    mapping = {"positive": "positive", "positivo": "positive", "positiva": "positive", "negative": "negative", "negativo": "negative", "negativa": "negative", "neutral": "neutral", "neutro": "neutral", "neutra": "neutral"}
    return mapping.get(normalized)


def _summary_required_terms(instruction: str) -> list[str]:
    match = re.search(r"(?i)\bmust\s+include\s+(.+?)(?:[.;]|$)", instruction)
    if not match:
        match = re.search(r"(?i)\binclude\s+the\s+terms?\s+(.+?)(?:[.;]|$)", instruction)
    if not match:
        return []
    quoted = re.findall(r"[\"']([^\"']+)[\"']", match.group(1))
    if quoted:
        return quoted
    return [part.strip() for part in re.split(r"(?i),|\band\b", match.group(1)) if part.strip()]


def _named_entities(text: str) -> list[str]:
    return re.findall(r"\b(?:[A-Z]{2,}|[A-Z][\w'-]+(?:\s+(?:of\s+)?[A-Z][\w'-]+)+)\b", text)


def _sentences(text: str) -> list[str]:
    return [match.group(0).strip() for match in re.finditer(r"[^.!?]+(?:[.!?]+|$)", text) if match.group(0).strip()]


def _fold_ascii(value: str) -> str:
    return "".join(character for character in unicodedata.normalize("NFKD", value) if not unicodedata.combining(character))


def _strip_json_fence(value: str) -> str:
    stripped = value.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else stripped


def _dedupe_spans(spans: Iterable[SourceSpan]) -> tuple[SourceSpan, ...]:
    unique: dict[tuple[int, int, str], SourceSpan] = {}
    for span in spans:
        unique[(span.start, span.end, span.role)] = span
    return tuple(sorted(unique.values(), key=lambda item: (item.start, item.end, item.role)))


def _report(
    accepted: bool,
    kind: GroundedTaskKind | None,
    candidate: str,
    reason: str,
    spans: Iterable[SourceSpan] = (),
    metadata: Mapping[str, Any] | None = None,
) -> GroundedVerificationReport:
    return GroundedVerificationReport(accepted, kind, candidate.strip(), reason, _dedupe_spans(spans), metadata or {})
