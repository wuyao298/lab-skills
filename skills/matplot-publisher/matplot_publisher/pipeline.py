# -*- coding: utf-8 -*-
"""六层决策框架编排器。"""

import re
import time
from pathlib import Path
from typing import Callable, Optional

from .crystallization import crystallize, match_profile
from .decision import decide
from .execution import downsample, execute
from .interpretation import interpret
from .io import MatReader
from .models import DecisionChain, ExecutionPlan, OutputFiles, ValidationResult, WeightTable
from .perception import perceive
from .profile_manager import ProfileManager
from .validation import validate

__all__ = ["MatplotPublisher"]

ConfirmCallback = Callable[[ValidationResult], str]


class MatplotPublisher:
    """matplot-publisher 主类：感知 → 理解 → 决策 → 验证 → 执行 → 固化。"""

    def __init__(
        self,
        file_path: str,
        variable_name: str,
        x_variable: Optional[str] = None,
        sample_rate: Optional[float] = None,
        output_base: str = "output/figure1",
        profile_dir: str = "profiles",
        preview_dir: str = "preview",
    ) -> None:
        self.file_path = file_path
        self.variable_name = variable_name
        self.x_variable = x_variable
        self.sample_rate = sample_rate
        self.output_base = output_base
        self.profile_dir = profile_dir
        self.preview_dir = preview_dir
        self.profile_manager = ProfileManager(profile_dir)

    def _open_reader(self) -> MatReader:
        reader = MatReader(
            self.file_path,
            self.variable_name,
            x_variable=self.x_variable,
            sample_rate=self.sample_rate,
        )
        reader.__enter__()
        return reader

    def perceive(self, reader: MatReader):
        return perceive(reader)

    def interpret(self, profile, user_hint: Optional[str] = None) -> WeightTable:
        return interpret(profile, user_hint)

    def decide(self, weights: WeightTable, n_out: int = 100_000, threshold: Optional[float] = None) -> ExecutionPlan:
        n_points = max((r.end + 1 for r in weights.regions), default=0)
        return decide(weights, n_points, n_out, threshold)

    def validate(self, reader: MatReader, plan: ExecutionPlan, use_glyphx: bool = False) -> ValidationResult:
        return validate(reader, plan, self.preview_dir, use_glyphx=use_glyphx)

    def execute(self, validation: ValidationResult) -> OutputFiles:
        assert validation.x_down is not None and validation.y_down is not None
        return execute(
            validation.x_down,
            validation.y_down,
            self.output_base,
            formats=("pdf", "png"),
            label=self.variable_name,
        )

    def crystallize(self, chain: DecisionChain) -> str:
        return crystallize(chain, self.profile_dir)

    # ------------------------------------------------------------------
    def run_full_pipeline(
        self,
        interactive: bool = True,
        user_hint: Optional[str] = None,
        assume_confirmed: bool = False,
        confirm_callback: Optional[ConfirmCallback] = None,
        n_out: int = 100_000,
        threshold: Optional[float] = None,
        use_glyphx: bool = False,
    ) -> OutputFiles:
        reader = self._open_reader()
        try:
            profile = self.perceive(reader)
            print(profile.summary)

            matched = match_profile(profile, self.profile_dir)
            if matched:
                print(f"💾 检测到匹配档案 {matched}，可直接复用。")
                if interactive and not assume_confirmed:
                    answer = input("是否复用该方案并直接进入执行层？[y/N] ").strip().lower()
                    if answer in ("y", "yes"):
                        return self._run_reuse(reader, matched)

            weights = self.interpret(profile, user_hint)
            if weights.needs_clarification and interactive and not assume_confirmed:
                hint = self._clarify(weights)
                weights = self.interpret(profile, hint)
                user_hint = hint
            print(weights.summary)

            plan = self.decide(weights, n_out, threshold)
            print(plan.summary)

            validation = self.validate(reader, plan, use_glyphx=use_glyphx)
            print(validation.report)
            for path in validation.preview_paths:
                print(f"🔍 预览图：{path}")

            if not validation.passed:
                print("⚠️ 保真度未达标，建议先 /adjust n_out 提高预算；仍可确认出图。")

            plan, validation, user_hint = self._confirm_loop(
                reader,
                plan,
                validation,
                interactive=interactive,
                assume_confirmed=assume_confirmed,
                confirm_callback=confirm_callback,
                n_out=n_out,
                user_hint=user_hint,
                use_glyphx=use_glyphx,
            )

            files = self.execute(validation)
            chain = DecisionChain(profile=profile, weights=weights, plan=plan, validation=validation, files=files)
            profile_id = self.crystallize(chain)
            chain.profile_id = profile_id
            print(f"✅ 出版级图表已生成：{files.pdf_path}，{files.png_path}")
            print(f"   耗时 {files.elapsed_seconds:.1f}s，压缩率 {validation.compression_ratio:.2%}")
            print(f"💾 方案已归档：{profile_id}")
            return files
        finally:
            reader.__exit__(None, None, None)

    # ------------------------------------------------------------------
    def _run_reuse(self, reader: MatReader, profile_id: str) -> OutputFiles:
        plan = self.profile_manager.load_plan(profile_id)
        if plan is None:
            print(f"⚠️ 无法加载 {profile_id}，回退完整流程。")
            return self.run_full_pipeline(interactive=False, assume_confirmed=True)
        x_down, y_down = downsample(reader, plan)
        files = execute(
            x_down,
            y_down,
            self.output_base,
            formats=("pdf", "png"),
            label=self.variable_name,
        )
        print(f"♻️ 复用 {profile_id} 完成：{files.pdf_path}，{files.png_path}")
        return files

    def _clarify(self, weights: WeightTable) -> str:
        print(weights.question)
        for _ in range(3):
            ans = input("请选择 A 或 B：").strip().lower()
            if ans in ("a", "峰值", "峰值精度", "peak"):
                return "峰值精度"
            if ans in ("b", "整体", "整体形态", "shape"):
                return "整体形态"
        return "峰值精度"

    def _confirm_loop(
        self,
        reader: MatReader,
        plan: ExecutionPlan,
        validation: ValidationResult,
        interactive: bool,
        assume_confirmed: bool,
        confirm_callback: Optional[ConfirmCallback],
        n_out: int,
        user_hint: Optional[str],
        use_glyphx: bool,
    ):
        if not interactive or assume_confirmed:
            validation.confirmed = True
            return plan, validation, user_hint

        while True:
            print("❓ 请确认：输入 `确认` 进入正式出图；或 `adjust n_out=150000`、`adjust threshold=4`、`preserve [a:b]`、`export_config`。")
            if confirm_callback is not None:
                ans = confirm_callback(validation)
            else:
                try:
                    ans = input("> ").strip()
                except EOFError:
                    ans = "确认"
            low = ans.lower()
            if low in ("确认", "confirm", "y", "yes"):
                validation.confirmed = True
                return plan, validation, user_hint
            if low in ("skip_validation", "/skip_validation"):
                validation.confirmed = True
                return plan, validation, user_hint
            reuse_match = re.search(r"(?:/reuse|reuse)\s+([A-Za-z0-9_.-]+)", low)
            if reuse_match:
                loaded = self.profile_manager.load_plan(reuse_match.group(1))
                if loaded is None:
                    print(f"档案不存在：{reuse_match.group(1)}")
                    continue
                xd, yd = downsample(reader, loaded)
                validation.x_down, validation.y_down = xd, yd
                validation.confirmed = True
                return loaded, validation, user_hint
            if "adjust" in low and "n_out" in low:
                value = self._parse_int(ans, "n_out", n_out)
                plan = self.decide_from_n_points(reader, plan, user_hint, value)
                validation = self.validate(reader, plan, use_glyphx=use_glyphx)
                print(plan.summary)
                print(validation.report)
                continue
            if "adjust" in low and "threshold" in low:
                value = self._parse_float(ans, "threshold", 3.0)
                profile = perceive(reader, mad_multiplier=value)
                weights = self.interpret(profile, user_hint)
                plan = decide(weights, profile.n_points, plan.target_n_out, value)
                validation = self.validate(reader, plan, use_glyphx=use_glyphx)
                print(plan.summary)
                print(validation.report)
                continue
            if "preserve" in low:
                user_hint = (user_hint or "") + " " + ans
                profile = perceive(reader)
                weights = self.interpret(profile, user_hint)
                plan = decide(weights, profile.n_points, plan.target_n_out, plan.pulse_threshold)
                validation = self.validate(reader, plan, use_glyphx=use_glyphx)
                print(weights.summary)
                print(plan.summary)
                print(validation.report)
                continue
            if "export_config" in low:
                self._export_current(plan, validation)
                continue
            print("无效命令。可用：确认 / adjust n_out=X / adjust threshold=X / preserve [a:b] / export_config")

    def decide_from_n_points(self, reader: MatReader, plan: ExecutionPlan, user_hint: Optional[str], value: int):
        profile = perceive(reader)
        weights = self.interpret(profile, user_hint)
        return decide(weights, profile.n_points, value, plan.pulse_threshold)

    def _export_current(self, plan: ExecutionPlan, validation: ValidationResult) -> None:
        from .models import DataProfile, DecisionChain, OutputFiles

        chain = DecisionChain(
            profile=DataProfile(
                file_path=self.file_path,
                file_format="",
                variable_name=self.variable_name,
                x_variable=self.x_variable,
                sample_rate=self.sample_rate,
                n_points=plan.n_points,
                n_sampled=0,
                morphology="",
                kurtosis=0.0,
                skewness=0.0,
            ),
            weights=WeightTable(morphology="", focus=""),
            plan=plan,
            validation=validation,
            files=OutputFiles(),
        )
        dest = self.profile_manager.export(chain, f"{self.profile_dir}/exported_plan.yaml")
        print(f"📄 当前方案已导出：{dest}")

    @staticmethod
    def _parse_int(text: str, key: str, default: int) -> int:
        m = re.search(rf"{key}\s*[=: ]\s*(\d+)", text)
        return int(m.group(1)) if m else default

    @staticmethod
    def _parse_float(text: str, key: str, default: float) -> float:
        m = re.search(rf"{key}\s*[=: ]\s*([0-9.]+)", text)
        return float(m.group(1)) if m else default
