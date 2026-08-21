# -*- coding: utf-8 -*-
"""六层决策框架的数据对象。"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class DataProfile:
    """感知层输出：数据画像。"""

    file_path: str
    file_format: str
    variable_name: str
    x_variable: Optional[str]
    sample_rate: Optional[float]
    n_points: int
    n_sampled: int
    morphology: str
    kurtosis: float
    skewness: float
    peak_indices: List[int] = field(default_factory=list)
    dense_regions: List[Tuple[int, int]] = field(default_factory=list)
    energy_map: Dict[str, float] = field(default_factory=dict)
    anomaly_indices: List[int] = field(default_factory=list)
    missing_segments: List[Tuple[int, int]] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["file_format"] = self.file_format
        return data


@dataclass
class WeightedRegion:
    """理解层输出：一个带权重的索引区间。"""

    start: int
    end: int
    weight: int
    label: str
    reason: str = ""
    preserve: bool = False


@dataclass
class WeightTable:
    """理解层输出：关注度权重表。"""

    morphology: str
    focus: str
    regions: List[WeightedRegion] = field(default_factory=list)
    needs_clarification: bool = False
    question: str = ""
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "morphology": self.morphology,
            "focus": self.focus,
            "regions": [asdict(r) for r in self.regions],
            "summary": self.summary,
        }


@dataclass
class PlanRegion:
    """决策层输出：单个区域的处理方案。"""

    start: int
    end: int
    weight: int
    strategy: str
    algorithm: str
    n_out: int
    label: str = ""


@dataclass
class ExecutionPlan:
    """决策层输出：执行方案说明书。"""

    n_points: int
    target_n_out: int
    estimated_n_out: int
    chunk_size: int
    overlap_ratio: float
    pulse_threshold: float
    regions: List[PlanRegion] = field(default_factory=list)
    algorithms: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_points": self.n_points,
            "target_n_out": self.target_n_out,
            "estimated_n_out": self.estimated_n_out,
            "chunk_size": self.chunk_size,
            "overlap_ratio": self.overlap_ratio,
            "pulse_threshold": self.pulse_threshold,
            "regions": [asdict(r) for r in self.regions],
            "algorithms": self.algorithms,
            "summary": self.summary,
        }


@dataclass
class ValidationResult:
    """验证层输出：预览 + 保真度报告 + 确认信号。"""

    preview_paths: List[str] = field(default_factory=list)
    peak_deviation: float = float("inf")
    slope_deviation: float = float("inf")
    envelope_iou: float = 0.0
    compression_ratio: float = 0.0
    passed: bool = False
    confirmed: bool = False
    report: str = ""
    x_down: Optional[Any] = field(default=None, repr=False)
    y_down: Optional[Any] = field(default=None, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("x_down", None)
        data.pop("y_down", None)
        return data


@dataclass
class OutputFiles:
    """执行层输出。"""

    pdf_path: Optional[str] = None
    png_path: Optional[str] = None
    paths: Dict[str, str] = field(default_factory=dict)
    elapsed_seconds: float = 0.0


@dataclass
class DecisionChain:
    """固化层输入：完整决策链。"""

    profile: DataProfile
    weights: WeightTable
    plan: ExecutionPlan
    validation: ValidationResult
    files: OutputFiles
    profile_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile": self.profile.to_dict(),
            "weights": self.weights.to_dict(),
            "plan": self.plan.to_dict(),
            "validation": self.validation.to_dict(),
            "files": asdict(self.files),
            "profile_id": self.profile_id,
        }
