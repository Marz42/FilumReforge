"""
Shared condition evaluation utilities.

Used by:
  - WorkflowGraphService (edge condition evaluation)
  - TaskService (routing_rules on TaskTemplateStep.config)

Condition schema (single condition dict):
  {"field": "amount", "operator": "gt", "value": 10000}

Composite conditions:
  {"all": [...]}   – all sub-conditions must be True
  {"any": [...]}   – at least one sub-condition must be True

Else condition:
  {"else": true}
"""
from __future__ import annotations

from typing import Any


def is_else_condition(condition: dict[str, Any]) -> bool:
    return bool(condition.get("else") is True or condition.get("type") == "else")


def _resolve_context_value(context: dict[str, Any], field_path: str) -> Any:
    value: Any = context
    for part in field_path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _safe_compare(actual_value: Any, expected_value: Any, *, compare: str) -> bool:
    try:
        if compare == "gt":
            return actual_value > expected_value
        if compare == "gte":
            return actual_value >= expected_value
        if compare == "lt":
            return actual_value < expected_value
        return actual_value <= expected_value
    except TypeError:
        return False


def evaluate_condition(condition: dict[str, Any], context: dict[str, Any]) -> bool:
    """Evaluate a single condition dict against the given context.

    Empty condition → True (unconditional edge).
    """
    if not condition:
        return True

    all_conditions = condition.get("all")
    if isinstance(all_conditions, list):
        return all(
            evaluate_condition(item, context)
            for item in all_conditions
            if isinstance(item, dict)
        )

    any_conditions = condition.get("any")
    if isinstance(any_conditions, list):
        return any(
            evaluate_condition(item, context)
            for item in any_conditions
            if isinstance(item, dict)
        )

    field_name = condition.get("field")
    if not isinstance(field_name, str) or not field_name:
        return False

    actual_value = _resolve_context_value(context, field_name)
    operator = str(condition.get("operator") or "eq").lower()
    expected_value = condition.get("value")

    if operator == "eq":
        return actual_value == expected_value
    if operator == "neq":
        return actual_value != expected_value
    if operator == "gt":
        return _safe_compare(actual_value, expected_value, compare="gt")
    if operator == "gte":
        return _safe_compare(actual_value, expected_value, compare="gte")
    if operator == "lt":
        return _safe_compare(actual_value, expected_value, compare="lt")
    if operator == "lte":
        return _safe_compare(actual_value, expected_value, compare="lte")
    if operator == "in":
        return isinstance(expected_value, list) and actual_value in expected_value
    if operator == "not_in":
        return isinstance(expected_value, list) and actual_value not in expected_value
    if operator == "contains":
        if isinstance(actual_value, list):
            return expected_value in actual_value
        if isinstance(actual_value, str) and isinstance(expected_value, str):
            return expected_value in actual_value
        return False
    if operator == "exists":
        return actual_value is not None

    return False


def evaluate_routing_rules(
    routing_rules: list[dict[str, Any]],
    context: dict[str, Any],
) -> set[str] | None:
    """Evaluate routing_rules (stored in TaskTemplateStep.config) against context.

    Routing rule formats:
      IF rule: {"condition": {"field": ..., "operator": ..., "value": ...}, "target_step_key": "step_b"}
      ELSE rule: {"else": true, "target_step_key": "step_c"}

    Returns:
      set of target_step_keys matched by the rules, or None if routing_rules is empty.

    Evaluation semantics:
      - Iterate rules in order; collect all IF-matched targets first.
      - If any IF rule matches, return those targets (ignoring ELSE).
      - If no IF rule matches, return ELSE targets.
      - If no rules at all, return None (no restriction – all dependencies are eligible).
    """
    if not routing_rules:
        return None

    matched_keys: list[str] = []
    else_keys: list[str] = []

    for rule in routing_rules:
        if not isinstance(rule, dict):
            continue
        target_step_key = rule.get("target_step_key")
        if not isinstance(target_step_key, str) or not target_step_key:
            continue
        if is_else_condition(rule):
            else_keys.append(target_step_key)
            continue
        condition = rule.get("condition")
        if isinstance(condition, dict) and evaluate_condition(condition, context):
            matched_keys.append(target_step_key)

    selected = matched_keys if matched_keys else else_keys
    return {k for k in selected if k} if selected else set()
