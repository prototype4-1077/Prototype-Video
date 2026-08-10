"""Zero-cost contextual-bandit learning for June Oxley NPR look profiles.

The learner deliberately depends only on the Python standard library.  It turns
immutable render observations into a bounded reward, then uses a shared linear
UCB model to rank look profiles for a shot context.  It never edits or promotes
a profile: its output is evidence for the existing human-controlled promotion
gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


CONTRACT_VERSION = 1
RECOMMENDATION_VERSION = 1
_IDENTIFIER = re.compile(r"[a-z][a-z0-9_.-]*\Z")
_SEMVER = re.compile(r"\d+\.\d+\.\d+\Z")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _bounded_number(value: Any, minimum: float, maximum: float, field: str) -> float:
    if not _is_number(value):
        raise ValueError(f"{field} must be a finite number")
    number = float(value)
    if not minimum <= number <= maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}")
    return number


def validate_reward_contract(contract: Mapping[str, Any]) -> None:
    if not isinstance(contract, Mapping):
        raise ValueError("reward contract must be an object")
    if contract.get("contract_version") != CONTRACT_VERSION:
        raise ValueError(f"reward contract_version must be {CONTRACT_VERSION}")
    reward_id = contract.get("reward_id")
    if not isinstance(reward_id, str) or not _IDENTIFIER.fullmatch(reward_id):
        raise ValueError("reward_id must be a lowercase identifier")
    version = contract.get("reward_version")
    if not isinstance(version, str) or not _SEMVER.fullmatch(version):
        raise ValueError("reward_version must use semantic versioning")

    objectives = contract.get("objectives")
    if not isinstance(objectives, list) or not objectives:
        raise ValueError("objectives must be a non-empty list")
    names: set[str] = set()
    total_weight = 0.0
    for objective in objectives:
        if not isinstance(objective, Mapping):
            raise ValueError("each objective must be an object")
        name = objective.get("name")
        if not isinstance(name, str) or not _IDENTIFIER.fullmatch(name) or name in names:
            raise ValueError("objective names must be unique lowercase identifiers")
        names.add(name)
        direction = objective.get("direction")
        if direction not in {"maximize", "minimize"}:
            raise ValueError(f"objective {name} direction must be maximize or minimize")
        minimum = objective.get("minimum")
        maximum = objective.get("maximum")
        if not _is_number(minimum) or not _is_number(maximum) or float(minimum) >= float(maximum):
            raise ValueError(f"objective {name} requires finite minimum < maximum")
        weight = _bounded_number(objective.get("weight"), 0.0, 1.0, f"objective {name} weight")
        total_weight += weight
        gate = objective.get("hard_gate")
        if gate is not None:
            _bounded_number(gate, float(minimum), float(maximum), f"objective {name} hard_gate")
    if not math.isclose(total_weight, 1.0, abs_tol=1e-9):
        raise ValueError("objective weights must sum to 1.0")

    for group_name in ("look_features", "context_features"):
        features = contract.get(group_name)
        if not isinstance(features, list) or not features:
            raise ValueError(f"{group_name} must be a non-empty list")
        feature_names: set[str] = set()
        for feature in features:
            if not isinstance(feature, Mapping):
                raise ValueError(f"each {group_name} entry must be an object")
            name = feature.get("name")
            if not isinstance(name, str) or not _IDENTIFIER.fullmatch(name) or name in feature_names:
                raise ValueError(f"{group_name} names must be unique lowercase identifiers")
            feature_names.add(name)
            path = feature.get("path")
            if group_name == "look_features" and (not isinstance(path, str) or not path):
                raise ValueError(f"look feature {name} requires a dotted path")
            minimum = feature.get("minimum")
            maximum = feature.get("maximum")
            if not _is_number(minimum) or not _is_number(maximum) or float(minimum) >= float(maximum):
                raise ValueError(f"feature {name} requires finite minimum < maximum")

    bandit = contract.get("bandit")
    if not isinstance(bandit, Mapping) or bandit.get("algorithm") != "linear_ucb_v1":
        raise ValueError("bandit algorithm must be linear_ucb_v1")
    if not _is_number(bandit.get("ridge")) or float(bandit["ridge"]) <= 0:
        raise ValueError("bandit ridge must be positive")
    if not _is_number(bandit.get("exploration")) or float(bandit["exploration"]) < 0:
        raise ValueError("bandit exploration must be non-negative")
    if contract.get("promotion_authority") != "human":
        raise ValueError("promotion_authority must remain human")


def load_reward_contract(path: str | Path) -> dict[str, Any]:
    contract = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_reward_contract(contract)
    return contract


def _value_at_path(payload: Mapping[str, Any], dotted_path: str) -> Any:
    value: Any = payload
    for part in dotted_path.split("."):
        if isinstance(value, Mapping):
            if part not in value:
                raise ValueError(f"profile is missing look feature path {dotted_path}")
            value = value[part]
        elif isinstance(value, list) and part.isdigit():
            index = int(part)
            if index >= len(value):
                raise ValueError(f"profile is missing look feature path {dotted_path}")
            value = value[index]
        else:
            raise ValueError(f"profile is missing look feature path {dotted_path}")
    return value


def _normalize(value: Any, feature: Mapping[str, Any], field: str) -> float:
    minimum = float(feature["minimum"])
    maximum = float(feature["maximum"])
    number = _bounded_number(value, minimum, maximum, field)
    return (number - minimum) / (maximum - minimum)


def score_observation(contract: Mapping[str, Any], observation: Mapping[str, Any]) -> dict[str, Any]:
    """Score one render observation and enforce the contract's hard floors."""
    validate_reward_contract(contract)
    if not isinstance(observation, Mapping):
        raise ValueError("observation must be an object")
    metrics = observation.get("metrics")
    if not isinstance(metrics, Mapping):
        raise ValueError("observation metrics must be an object")
    objective_scores: dict[str, float] = {}
    gate_failures: list[str] = []
    reward = 0.0
    for objective in contract["objectives"]:
        name = str(objective["name"])
        if name not in metrics:
            raise ValueError(f"observation is missing metric {name}")
        minimum = float(objective["minimum"])
        maximum = float(objective["maximum"])
        value = _bounded_number(metrics[name], minimum, maximum, f"metric {name}")
        normalized = (value - minimum) / (maximum - minimum)
        if objective["direction"] == "minimize":
            normalized = 1.0 - normalized
        objective_scores[name] = normalized
        reward += float(objective["weight"]) * normalized
        gate = objective.get("hard_gate")
        if gate is not None:
            failed = value < float(gate) if objective["direction"] == "maximize" else value > float(gate)
            if failed:
                gate_failures.append(name)
    passed = not gate_failures
    return {
        "reward": round(reward if passed else 0.0, 9),
        "raw_reward": round(reward, 9),
        "hard_gate_pass": passed,
        "gate_failures": gate_failures,
        "normalized_objectives": {name: round(value, 9) for name, value in objective_scores.items()},
    }


def _validate_context(contract: Mapping[str, Any], context: Mapping[str, Any]) -> list[float]:
    if not isinstance(context, Mapping):
        raise ValueError("context must be an object")
    values = []
    expected = {str(feature["name"]) for feature in contract["context_features"]}
    if set(context) != expected:
        raise ValueError("context must exactly match the reward contract context features")
    for feature in contract["context_features"]:
        name = str(feature["name"])
        values.append(_normalize(context[name], feature, f"context {name}"))
    return values


def profile_features(contract: Mapping[str, Any], profile: Mapping[str, Any]) -> list[float]:
    validate_reward_contract(contract)
    if not isinstance(profile, Mapping):
        raise ValueError("look profile must be an object")
    values = []
    for feature in contract["look_features"]:
        name = str(feature["name"])
        raw = _value_at_path(profile, str(feature["path"]))
        values.append(_normalize(raw, feature, f"look feature {name}"))
    return values


def contextual_features(
    contract: Mapping[str, Any],
    profile: Mapping[str, Any],
    context: Mapping[str, Any],
) -> list[float]:
    """Build intercept, main effects, and look/context interactions."""
    look = profile_features(contract, profile)
    shot = _validate_context(contract, context)
    return [1.0, *look, *shot, *(left * right for left in look for right in shot)]


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Solve a dense positive-definite system with pivoted Gauss-Jordan elimination."""
    size = len(vector)
    if size == 0 or len(matrix) != size or any(len(row) != size for row in matrix):
        raise ValueError("linear system dimensions do not match")
    augmented = [list(map(float, row)) + [float(vector[index])] for index, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("bandit design matrix is singular")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = augmented[column][column]
        augmented[column] = [value / scale for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor:
                augmented[row] = [
                    left - factor * right
                    for left, right in zip(augmented[row], augmented[column])
                ]
    return [augmented[row][-1] for row in range(size)]


def rank_look_profiles(
    contract: Mapping[str, Any],
    profiles: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Rank immutable profiles using all scored observations and linear UCB."""
    validate_reward_contract(contract)
    if not profiles:
        raise ValueError("at least one look profile is required")
    candidates: dict[str, Mapping[str, Any]] = {}
    for profile in profiles:
        digest = canonical_sha256(profile)
        if digest in candidates:
            raise ValueError("look profiles must be unique")
        profile_features(contract, profile)
        candidates[digest] = profile
    current_vectors = {
        digest: contextual_features(contract, profile, context)
        for digest, profile in candidates.items()
    }
    dimension = len(next(iter(current_vectors.values())))
    ridge = float(contract["bandit"]["ridge"])
    design = [[ridge if row == column else 0.0 for column in range(dimension)] for row in range(dimension)]
    target = [0.0] * dimension
    observation_counts = {digest: 0 for digest in candidates}
    for observation in observations:
        if not isinstance(observation, Mapping):
            raise ValueError("each observation must be an object")
        digest = observation.get("look_profile_sha256")
        if digest not in candidates:
            raise ValueError("observation references an unknown look profile")
        vector = contextual_features(contract, candidates[str(digest)], observation.get("context"))
        scored = score_observation(contract, observation)
        reward = float(scored["reward"])
        observation_counts[str(digest)] += 1
        for row, left in enumerate(vector):
            target[row] += reward * left
            for column, right in enumerate(vector):
                design[row][column] += left * right
    theta = _solve(design, target)
    exploration = float(contract["bandit"]["exploration"])
    ranked = []
    for digest, vector in current_vectors.items():
        mean = sum(weight * value for weight, value in zip(theta, vector))
        covariance_projection = _solve(design, vector)
        variance = max(0.0, sum(left * right for left, right in zip(vector, covariance_projection)))
        confidence = exploration * math.sqrt(variance)
        profile = candidates[digest]
        ranked.append({
            "look_profile_sha256": digest,
            "look_id": profile.get("look_id"),
            "style_version": profile.get("style_version"),
            "observations": observation_counts[digest],
            "predicted_reward": round(mean, 9),
            "exploration_bonus": round(confidence, 9),
            "ucb_score": round(mean + confidence, 9),
        })
    ranked.sort(key=lambda item: (-item["ucb_score"], item["look_profile_sha256"]))
    return ranked


def build_recommendation(
    contract: Mapping[str, Any],
    profiles: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    ranking = rank_look_profiles(contract, profiles, observations, context)
    return {
        "contract_version": RECOMMENDATION_VERSION,
        "recommendation_type": "contextual_npr_look_experiment",
        "reward_contract_sha256": canonical_sha256(contract),
        "context": dict(context),
        "observation_count": len(observations),
        "recommended_experiment": ranking[0],
        "ranking": ranking,
        "authority_boundary": "Recommendation only. Human approval and all hard visual gates remain required for promotion.",
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rank June NPR looks with a zero-cost contextual bandit")
    parser.add_argument("reward_contract")
    parser.add_argument("--profile", action="append", required=True, help="Candidate look-profile JSON; repeatable")
    parser.add_argument("--observations", required=True, help="JSON array of immutable render observations")
    parser.add_argument("--context", required=True, help="Shot-context JSON object")
    parser.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    contract = load_reward_contract(args.reward_contract)
    profiles = [json.loads(Path(path).read_text(encoding="utf-8")) for path in args.profile]
    observations = json.loads(Path(args.observations).read_text(encoding="utf-8"))
    context = json.loads(Path(args.context).read_text(encoding="utf-8"))
    if not isinstance(observations, list):
        raise ValueError("observations file must contain a JSON array")
    recommendation = build_recommendation(contract, profiles, observations, context)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(recommendation, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(recommendation, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
