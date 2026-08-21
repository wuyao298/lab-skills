# -*- coding: utf-8 -*-
"""配置档案管理：保存 / 匹配 / 复用。"""

import glob
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from .models import DataProfile, DecisionChain, ExecutionPlan, PlanRegion

__all__ = ["ProfileManager"]


class ProfileManager:
    def __init__(self, profile_dir: str = "profiles") -> None:
        self.profile_dir = Path(profile_dir)
        self.profile_dir.mkdir(parents=True, exist_ok=True)

    def _next_id(self, base_id: str) -> str:
        existing = [Path(p).name for p in glob.glob(str(self.profile_dir / f"{base_id.split('_v')[0]}_v*.yaml"))]
        if not existing:
            return f"{base_id}_v1.0"
        versions = []
        for name in existing:
            stem = Path(name).stem
            if "_v" in stem:
                try:
                    versions.append(float(stem.rsplit("_v", 1)[1]))
                except ValueError:
                    pass
        return f"{base_id}_v{max(versions) + 0.1:.1f}" if versions else f"{base_id}_v1.1"

    def save(self, chain: DecisionChain) -> str:
        base = f"{chain.profile.morphology}_{datetime.now().strftime('%Y%m%d')}"
        profile_id = self._next_id(base)
        config = {
            "profile": {
                "id": profile_id,
                "created": datetime.now().isoformat(timespec="seconds"),
                "morphology": chain.profile.morphology,
                "dense_ratio": sum(b - a for a, b in chain.profile.dense_regions) / max(1, chain.profile.n_points),
            },
            "decision": chain.plan.to_dict(),
            "validation": chain.validation.to_dict(),
            "status": "approved" if chain.validation.passed else "review",
            "user_feedback": chain.validation.confirmed,
        }
        with open(self.profile_dir / f"{profile_id}.yaml", "w", encoding="utf-8") as fh:
            yaml.safe_dump(config, fh, allow_unicode=True, sort_keys=False)
        return profile_id

    def export(self, chain: DecisionChain, path: str) -> str:
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        config = {
            "profile": chain.profile.to_dict(),
            "decision": chain.plan.to_dict(),
            "validation": chain.validation.to_dict(),
            "user_feedback": chain.validation.confirmed,
        }
        with open(dest, "w", encoding="utf-8") as fh:
            yaml.safe_dump(config, fh, allow_unicode=True, sort_keys=False)
        return str(dest)

    def match(self, profile: DataProfile) -> Optional[str]:
        best_id: Optional[str] = None
        best_score = 0.0
        for path in glob.glob(str(self.profile_dir / "*.yaml")):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    cfg: Dict[str, Any] = yaml.safe_load(fh) or {}
            except Exception:
                continue
            prof = cfg.get("profile") or {}
            score = 0.0
            if prof.get("morphology") == profile.morphology:
                score += 0.7
            else:
                score += 0.2
            stored_dense = float(prof.get("dense_ratio", 0.0))
            current_dense = sum(b - a for a, b in profile.dense_regions) / max(1, profile.n_points)
            score += 0.3 * max(0.0, 1.0 - abs(stored_dense - current_dense))
            if score > best_score:
                best_score = score
                best_id = prof.get("id")
        return best_id if best_score >= 0.8 else None

    def load_plan(self, profile_id: str) -> Optional[ExecutionPlan]:
        path = self.profile_dir / f"{profile_id}.yaml"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as fh:
            cfg: Dict[str, Any] = yaml.safe_load(fh) or {}
        d = cfg.get("decision") or {}
        if not d:
            return None
        regions = []
        for item in d.get("regions", []):
            regions.append(
                PlanRegion(
                    start=int(item["start"]),
                    end=int(item["end"]),
                    weight=int(item["weight"]),
                    strategy=str(item["strategy"]),
                    algorithm=str(item["algorithm"]),
                    n_out=int(item["n_out"]),
                    label=str(item.get("label", "")),
                )
            )
        plan = ExecutionPlan(
            n_points=int(d.get("n_points", 0)),
            target_n_out=int(d.get("target_n_out", 0)),
            estimated_n_out=int(d.get("estimated_n_out", 0)),
            chunk_size=int(d.get("chunk_size", 5_000_000)),
            overlap_ratio=float(d.get("overlap_ratio", 0.1)),
            pulse_threshold=float(d.get("pulse_threshold", 3.0)),
            regions=regions,
            algorithms=[str(a) for a in d.get("algorithms", [])],
            summary=str(d.get("summary", "")),
        )
        return plan
