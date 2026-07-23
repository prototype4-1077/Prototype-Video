"""Zero-cost-by-default gate for paid cartoon generation (paid_i2v).

No paid provider (Replicate/Kling/Wan-cloud/...) may run unless the build carries
an approved generation-budget.json AND the request stays within limits. The local
limited_2_5d renderer never touches this gate. Default budget is zero.
"""
from __future__ import annotations
import json, os

DEFAULT_BUDGET = {
    "schema_version": 1, "provider": None, "model": None, "scenes": [],
    "predicted_request_count": 0, "estimated_cost_per_request": 0,
    "estimated_total_cost": 0, "approved": False,
    "reason": "No paid generation is required for the local proof.",
}


def budget_path(build_dir: str) -> str:
    return os.path.join(build_dir, "generation-budget.json")


def load_budget(build_dir: str) -> dict:
    p = budget_path(build_dir)
    if not os.path.exists(p):
        return dict(DEFAULT_BUDGET)
    data = dict(DEFAULT_BUDGET); data.update(json.load(open(p)))
    return data


def write_default_budget(build_dir: str) -> str:
    p = budget_path(build_dir)
    if not os.path.exists(p):
        json.dump(DEFAULT_BUDGET, open(p, "w"), indent=2)
    return p


class BudgetError(RuntimeError):
    pass


def assert_paid_allowed(build_dir: str, provider: str, model: str,
                        scene_count: int, scene_limit: int = 5) -> dict:
    """Raise BudgetError unless a valid approved budget authorizes this paid run."""
    b = load_budget(build_dir)
    if not b.get("approved"):
        raise BudgetError("paid generation blocked: generation-budget.json not approved (default zero-cost)")
    if not b.get("provider") or not b.get("model"):
        raise BudgetError("paid generation blocked: provider and model must be specified in the budget")
    if provider != b.get("provider") or model != b.get("model"):
        raise BudgetError(f"paid generation blocked: request {provider}/{model} not authorized by budget")
    if not b.get("estimated_total_cost"):
        raise BudgetError("paid generation blocked: estimated_total_cost missing")
    if scene_count > int(scene_limit):
        raise BudgetError(f"paid generation blocked: {scene_count} scenes exceeds paid_i2v_scene_limit={scene_limit}")
    if scene_count > len(b.get("scenes") or []) and b.get("scenes"):
        raise BudgetError("paid generation blocked: scene_count exceeds approved scene list")
    return b
