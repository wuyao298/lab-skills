# -*- coding: utf-8 -*-
"""matplot-publisher 命令行入口。"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from .io import detect_mat_format, discover_mat_variables
from .pipeline import MatplotPublisher

__all__ = ["main"]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="matplot-publisher",
        description="示波器波形数据科研绘图：感知→理解→决策→验证→执行→固化",
    )
    sub = parser.add_subparsers(dest="command")

    inspect = sub.add_parser("inspect", help="查看 .mat 文件变量（只读元数据）")
    inspect.add_argument("file", help=".mat 文件路径")

    plot = sub.add_parser("plot", help="完整六层流程生成出版级图表")
    plot.add_argument("file", help=".mat 文件路径")
    plot.add_argument("--var", required=True, help="数据变量名，如 ch1_data")
    plot.add_argument("--x", dest="x_variable", help="时间/横轴变量名")
    plot.add_argument("--sample-rate", type=float, help="采样率 Hz；无 --x 时用于生成时间轴")
    plot.add_argument("--points", type=int, default=100_000, help="目标输出点数")
    plot.add_argument("--threshold", type=float, help="脉冲检测阈值（MAD 倍数）")
    plot.add_argument("--focus", help="用户关注点，如 峰值精度 / 整体形态 / 底噪 / t=0.5")
    plot.add_argument("--out", default="output/figure1", help="输出文件基名")
    plot.add_argument("--profile-dir", default="profiles", help="配置档案目录")
    plot.add_argument("--preview-dir", default="preview", help="预览输出目录")
    plot.add_argument("--glyphx", action="store_true", help="额外生成 glyphx HTML 预览")
    plot.add_argument("--yes", action="store_true", help="自动确认（测试/无人值守）")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "inspect":
        path = Path(args.file)
        if not path.exists():
            print(f"文件不存在：{path}")
            return 2
        print(f"文件格式：{detect_mat_format(str(path))}")
        for name, shape, dtype in discover_mat_variables(str(path)):
            print(f"- {name}: shape={shape}, dtype={dtype}")
        return 0

    if args.command == "plot":
        if not Path(args.file).exists():
            print(f"文件不存在：{args.file}")
            return 2
        publisher = MatplotPublisher(
            file_path=args.file,
            variable_name=args.var,
            x_variable=args.x_variable,
            sample_rate=args.sample_rate,
            output_base=args.out,
            profile_dir=args.profile_dir,
            preview_dir=args.preview_dir,
        )
        files = publisher.run_full_pipeline(
            interactive=not args.yes,
            assume_confirmed=args.yes,
            user_hint=args.focus,
            n_out=args.points,
            threshold=args.threshold,
            use_glyphx=args.glyphx,
        )
        for path in files.paths.values():
            print(path)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
