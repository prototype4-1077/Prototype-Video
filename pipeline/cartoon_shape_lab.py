"""Deterministic, zero-cost candidate generation for the June Shape Lab.

This module deliberately has no Blender or third-party dependencies.  It owns the
versioned search-space contract, reproducible candidate manifests, and generic
Pareto-frontier selection.  Rendering and metric collection are later stages.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import random
import re
from typing import Any, Iterable, Mapping, Sequence


SEARCH_SPACE_CONTRACT_VERSION = 1
CANDIDATE_CONTRACT_VERSION = 1
GENERATOR_VERSION = "stdlib_uniform_ticks_v1"
MIN_PARAMETER_COUNT = 12
MAX_PARAMETER_COUNT = 18
_IDENTIFIER = re.compile(r"[a-z][a-z0-9_.-]*\Z")
_SEMVER = re.compile(r"\d+\.\d+\.\d+\Z")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _decimal(value: Any, field: str) -> Decimal:
    if not _is_number(value):
        raise ValueError(f"{field} must be a finite number")
    return Decimal(str(value))


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _parameter_map(search_space: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(parameter["name"]): parameter for parameter in search_space["parameters"]}


def _tick_count(parameter: Mapping[str, Any]) -> int:
    minimum = Decimal(str(parameter["minimum"]))
    maximum = Decimal(str(parameter["maximum"]))
    step = Decimal(str(parameter["step"]))
    ticks = (maximum - minimum) / step
    if ticks != ticks.to_integral_value():
        raise ValueError(f"parameter {parameter['name']} range must be divisible by step")
    return int(ticks)


def _value_on_grid(parameter: Mapping[str, Any], value: Any) -> bool:
    number = Decimal(str(value))
    minimum = Decimal(str(parameter["minimum"]))
    step = Decimal(str(parameter["step"]))
    ticks = (number - minimum) / step
    return ticks == ticks.to_integral_value()


def validate_search_space(search_space: Mapping[str, Any]) -> None:
    """Validate a complete June Shape Lab search-space mapping."""
    if not isinstance(search_space, Mapping):
        raise ValueError("search space must be an object")
    if search_space.get("contract_version") != SEARCH_SPACE_CONTRACT_VERSION:
        raise ValueError(f"search-space contract_version must be {SEARCH_SPACE_CONTRACT_VERSION}")
    for field in ("search_space_id", "character_id", "asset_id"):
        value = search_space.get(field)
        if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
            raise ValueError(f"{field} must be a lowercase identifier")
    for field in ("search_space_version", "asset_version"):
        value = search_space.get(field)
        if not isinstance(value, str) or not _SEMVER.fullmatch(value):
            raise ValueError(f"{field} must use semantic versioning")
    if search_space.get("character_id") != "june_oxley":
        raise ValueError("June Shape Lab must target june_oxley")
    if search_space.get("generator") != GENERATOR_VERSION:
        raise ValueError(f"generator must be {GENERATOR_VERSION}")

    objectives = search_space.get("objectives")
    if not isinstance(objectives, list) or not objectives:
        raise ValueError("objectives must be a non-empty list")
    objective_names: set[str] = set()
    for objective in objectives:
        if not isinstance(objective, Mapping):
            raise ValueError("each objective must be an object")
        name = objective.get("name")
        if not isinstance(name, str) or not _IDENTIFIER.fullmatch(name):
            raise ValueError("objective names must be lowercase identifiers")
        if name in objective_names:
            raise ValueError(f"duplicate objective: {name}")
        objective_names.add(name)
        if objective.get("direction") not in {"maximize", "minimize"}:
            raise ValueError(f"objective {name} direction must be maximize or minimize")

    parameters = search_space.get("parameters")
    if not isinstance(parameters, list) or not MIN_PARAMETER_COUNT <= len(parameters) <= MAX_PARAMETER_COUNT:
        raise ValueError(f"parameters must contain {MIN_PARAMETER_COUNT} to {MAX_PARAMETER_COUNT} entries")
    names: set[str] = set()
    for parameter in parameters:
        if not isinstance(parameter, Mapping):
            raise ValueError("each parameter must be an object")
        name = parameter.get("name")
        if not isinstance(name, str) or not _IDENTIFIER.fullmatch(name):
            raise ValueError("parameter names must be lowercase dotted identifiers")
        if name in names:
            raise ValueError(f"duplicate parameter: {name}")
        names.add(name)
        group = parameter.get("group")
        if not isinstance(group, str) or not _IDENTIFIER.fullmatch(group):
            raise ValueError(f"parameter {name} group must be a lowercase identifier")
        kind = parameter.get("kind")
        if kind == "float":
            minimum = _decimal(parameter.get("minimum"), f"parameter {name} minimum")
            maximum = _decimal(parameter.get("maximum"), f"parameter {name} maximum")
            default = _decimal(parameter.get("default"), f"parameter {name} default")
            step = _decimal(parameter.get("step"), f"parameter {name} step")
            if minimum >= maximum or step <= 0:
                raise ValueError(f"parameter {name} requires minimum < maximum and step > 0")
            if not minimum <= default <= maximum:
                raise ValueError(f"parameter {name} default is outside its bounds")
            _tick_count(parameter)
            if not _value_on_grid(parameter, default):
                raise ValueError(f"parameter {name} default must lie on its step grid")
        elif kind == "integer":
            values = (parameter.get("minimum"), parameter.get("maximum"), parameter.get("default"))
            if not all(isinstance(value, int) and not isinstance(value, bool) for value in values):
                raise ValueError(f"integer parameter {name} bounds and default must be integers")
            if values[0] >= values[1] or not values[0] <= values[2] <= values[1]:
                raise ValueError(f"integer parameter {name} has invalid bounds or default")
        elif kind == "choice":
            choices = parameter.get("choices")
            if not isinstance(choices, list) or not choices:
                raise ValueError(f"choice parameter {name} requires choices")
            if any(isinstance(value, (dict, list)) for value in choices):
                raise ValueError(f"choice parameter {name} choices must be scalar values")
            if len({_canonical_json(value) for value in choices}) != len(choices):
                raise ValueError(f"choice parameter {name} choices must be unique")
            if parameter.get("default") not in choices:
                raise ValueError(f"choice parameter {name} default must be one of its choices")
        else:
            raise ValueError(f"parameter {name} has unsupported kind: {kind!r}")


def load_search_space(path: str | Path) -> dict[str, Any]:
    search_space = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_search_space(search_space)
    return search_space


def default_parameters(search_space: Mapping[str, Any]) -> dict[str, Any]:
    validate_search_space(search_space)
    return {str(parameter["name"]): parameter["default"] for parameter in search_space["parameters"]}


def _sample_value(parameter: Mapping[str, Any], generator: random.Random) -> Any:
    kind = parameter["kind"]
    if kind == "float":
        minimum = Decimal(str(parameter["minimum"]))
        step = Decimal(str(parameter["step"]))
        value = minimum + step * generator.randrange(_tick_count(parameter) + 1)
        return float(value)
    if kind == "integer":
        return generator.randint(int(parameter["minimum"]), int(parameter["maximum"]))
    return generator.choice(parameter["choices"])


def _candidate_payload(
    search_space: Mapping[str, Any],
    parameters: Mapping[str, Any],
    *,
    seed: int,
    sample_index: int,
    baseline: bool,
) -> dict[str, Any]:
    return {
        "contract_version": CANDIDATE_CONTRACT_VERSION,
        "search_space": {
            "id": search_space["search_space_id"],
            "version": search_space["search_space_version"],
        },
        "target": {
            "character_id": search_space["character_id"],
            "asset_id": search_space["asset_id"],
            "asset_version": search_space["asset_version"],
        },
        "generator": {
            "name": GENERATOR_VERSION,
            "seed": seed,
            "sample_index": sample_index,
            "baseline": baseline,
        },
        "parameters": dict(parameters),
        "state": "proposed",
    }


def _candidate_id(payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()[:16]
    return f"june-shape-{digest}"


def make_candidate(
    search_space: Mapping[str, Any],
    parameters: Mapping[str, Any],
    *,
    seed: int,
    sample_index: int,
    baseline: bool = False,
) -> dict[str, Any]:
    validate_search_space(search_space)
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed must be an integer")
    if not isinstance(sample_index, int) or isinstance(sample_index, bool) or sample_index < 0:
        raise ValueError("sample_index must be a non-negative integer")
    payload = _candidate_payload(
        search_space,
        parameters,
        seed=seed,
        sample_index=sample_index,
        baseline=baseline,
    )
    candidate = {"candidate_id": _candidate_id(payload), **payload}
    validate_candidate(search_space, candidate)
    return candidate


def sample_candidates(
    search_space: Mapping[str, Any],
    *,
    seed: int,
    count: int,
    include_baseline: bool = True,
) -> list[dict[str, Any]]:
    """Generate ``count`` reproducible candidates, optionally starting at defaults."""
    validate_search_space(search_space)
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        raise ValueError("count must be a positive integer")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed must be an integer")
    generator = random.Random(seed)
    candidates = []
    for index in range(count):
        baseline = bool(include_baseline and index == 0)
        values = default_parameters(search_space) if baseline else {
            str(parameter["name"]): _sample_value(parameter, generator)
            for parameter in search_space["parameters"]
        }
        candidates.append(
            make_candidate(
                search_space,
                values,
                seed=seed,
                sample_index=index,
                baseline=baseline,
            )
        )
    return candidates


def validate_candidate(search_space: Mapping[str, Any], candidate: Mapping[str, Any]) -> None:
    validate_search_space(search_space)
    if not isinstance(candidate, Mapping):
        raise ValueError("candidate must be an object")
    if candidate.get("contract_version") != CANDIDATE_CONTRACT_VERSION:
        raise ValueError(f"candidate contract_version must be {CANDIDATE_CONTRACT_VERSION}")
    expected_space = {"id": search_space["search_space_id"], "version": search_space["search_space_version"]}
    if candidate.get("search_space") != expected_space:
        raise ValueError("candidate search_space does not match the loaded contract")
    expected_target = {
        "character_id": search_space["character_id"],
        "asset_id": search_space["asset_id"],
        "asset_version": search_space["asset_version"],
    }
    if candidate.get("target") != expected_target:
        raise ValueError("candidate target does not match the loaded contract")
    generator = candidate.get("generator")
    if not isinstance(generator, Mapping) or generator.get("name") != GENERATOR_VERSION:
        raise ValueError("candidate has an unsupported generator")
    seed = generator.get("seed")
    sample_index = generator.get("sample_index")
    baseline = generator.get("baseline")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("candidate generator seed must be an integer")
    if not isinstance(sample_index, int) or isinstance(sample_index, bool) or sample_index < 0:
        raise ValueError("candidate sample_index must be a non-negative integer")
    if not isinstance(baseline, bool):
        raise ValueError("candidate baseline flag must be boolean")
    if candidate.get("state") != "proposed":
        raise ValueError("new candidate state must be proposed")

    values = candidate.get("parameters")
    if not isinstance(values, Mapping):
        raise ValueError("candidate parameters must be an object")
    definitions = _parameter_map(search_space)
    if set(values) != set(definitions):
        raise ValueError("candidate parameters must exactly match the search-space parameters")
    for name, parameter in definitions.items():
        value = values[name]
        kind = parameter["kind"]
        if kind == "float":
            number = _decimal(value, f"candidate parameter {name}")
            minimum = Decimal(str(parameter["minimum"]))
            maximum = Decimal(str(parameter["maximum"]))
            if not minimum <= number <= maximum or not _value_on_grid(parameter, number):
                raise ValueError(f"candidate parameter {name} is outside bounds or off-grid")
        elif kind == "integer":
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"candidate parameter {name} must be an integer")
            if not int(parameter["minimum"]) <= value <= int(parameter["maximum"]):
                raise ValueError(f"candidate parameter {name} is outside bounds")
        elif value not in parameter["choices"]:
            raise ValueError(f"candidate parameter {name} is not an allowed choice")

    payload = {key: value for key, value in candidate.items() if key != "candidate_id"}
    if candidate.get("candidate_id") != _candidate_id(payload):
        raise ValueError("candidate_id does not match the immutable candidate payload")


def write_candidate_manifest(candidate: Mapping[str, Any], output_dir: str | Path) -> Path:
    """Create an append-only candidate manifest, accepting exact idempotent replays."""
    candidate_id = candidate.get("candidate_id")
    if not isinstance(candidate_id, str) or not re.fullmatch(r"june-shape-[0-9a-f]{16}", candidate_id):
        raise ValueError("candidate_id is invalid")
    payload = {key: value for key, value in candidate.items() if key != "candidate_id"}
    if candidate_id != _candidate_id(payload):
        raise ValueError("candidate_id does not match the immutable candidate payload")
    destination = Path(output_dir) / candidate_id / "candidate.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(candidate, indent=2, sort_keys=True) + "\n"
    if destination.exists():
        if destination.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"immutable candidate manifest already differs: {destination}")
        return destination
    try:
        with destination.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    except FileExistsError:
        if destination.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"immutable candidate manifest already differs: {destination}")
    return destination


def objective_directions(search_space: Mapping[str, Any]) -> dict[str, str]:
    validate_search_space(search_space)
    return {str(item["name"]): str(item["direction"]) for item in search_space["objectives"]}


def _validated_scores(record: Mapping[str, Any], directions: Mapping[str, str]) -> Mapping[str, Any]:
    scores = record.get("scores")
    if not isinstance(scores, Mapping):
        raise ValueError("frontier records must contain a scores object")
    missing = set(directions) - set(scores)
    if missing:
        raise ValueError("frontier record is missing scores: " + ", ".join(sorted(missing)))
    for name in directions:
        if not _is_number(scores[name]):
            raise ValueError(f"score {name} must be a finite number")
    return scores


def dominates(
    challenger: Mapping[str, Any],
    incumbent: Mapping[str, Any],
    directions: Mapping[str, str],
) -> bool:
    """Return whether challenger is no worse everywhere and better somewhere."""
    if not directions or any(direction not in {"maximize", "minimize"} for direction in directions.values()):
        raise ValueError("directions must map objectives to maximize or minimize")
    challenger_scores = _validated_scores(challenger, directions)
    incumbent_scores = _validated_scores(incumbent, directions)
    strictly_better = False
    for name, direction in directions.items():
        left = float(challenger_scores[name])
        right = float(incumbent_scores[name])
        if direction == "maximize":
            if left < right:
                return False
            strictly_better = strictly_better or left > right
        else:
            if left > right:
                return False
            strictly_better = strictly_better or left < right
    return strictly_better


def pareto_frontier(
    records: Iterable[Mapping[str, Any]],
    directions: Mapping[str, str],
) -> list[Mapping[str, Any]]:
    """Return non-dominated records in their original deterministic order."""
    materialized = list(records)
    for record in materialized:
        _validated_scores(record, directions)
    return [
        record
        for index, record in enumerate(materialized)
        if not any(
            other_index != index and dominates(other, record, directions)
            for other_index, other in enumerate(materialized)
        )
    ]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate immutable June Shape Lab candidates")
    parser.add_argument("search_space", help="Versioned June Shape Lab search-space JSON")
    parser.add_argument("--output-dir", required=True, help="Append-only candidate directory")
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--no-baseline", action="store_true", help="Do not reserve candidate zero for defaults")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    search_space = load_search_space(args.search_space)
    candidates = sample_candidates(
        search_space,
        seed=args.seed,
        count=args.count,
        include_baseline=not args.no_baseline,
    )
    paths = [write_candidate_manifest(candidate, args.output_dir) for candidate in candidates]
    print(json.dumps({
        "search_space_id": search_space["search_space_id"],
        "search_space_version": search_space["search_space_version"],
        "seed": args.seed,
        "candidate_count": len(candidates),
        "candidate_ids": [candidate["candidate_id"] for candidate in candidates],
        "manifests": [str(path) for path in paths],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
