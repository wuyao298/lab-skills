# -*- coding: utf-8 -*-
"""分批读取 .mat，禁止一次性全量加载。"""

from pathlib import Path
from typing import Iterator, List, Optional, Tuple

import numpy as np

__all__ = ["MatReader", "discover_mat_variables", "detect_mat_format"]

_HDF5_SIGNATURE = b"\x89HDF\r\n\x1a\n"


def detect_mat_format(path: str) -> str:
    # MATLAB v7.3 文件 = 512 字节 MATLAB 头 + HDF5 超块；
    # HDF5 签名不在文件开头，必须扫描头部而不是只看前 8 字节。
    with open(path, "rb") as fh:
        head = fh.read(1024)
    return "v7.3 (HDF5)" if _HDF5_SIGNATURE in head else "v5/v7 (MATLAB)"


def discover_mat_variables(path: str) -> List[Tuple[str, Tuple[int, ...], str]]:
    """返回 [(变量名, shape, dtype)]；只读元数据，不读数据。"""
    fmt = detect_mat_format(path)
    variables: List[Tuple[str, Tuple[int, ...], str]] = []
    if fmt == "v7.3 (HDF5)":
        import h5py

        with h5py.File(path, "r") as h5:
            def _walk(name: str, obj: h5py.Dataset) -> None:
                if isinstance(obj, h5py.Dataset):
                    try:
                        if obj.shape is not None and obj.dtype.kind in "iuf":
                            variables.append((name, tuple(int(s) for s in obj.shape), str(obj.dtype)))
                    except Exception:
                        pass

            h5.visititems(_walk)
    else:
        try:
            from scipy.io import whosmat

            for name, shape, dtype in whosmat(path):
                variables.append((name, tuple(shape), str(dtype)))
        except Exception:
            pass
    return variables


class MatReader:
    """分批读取单个数值变量。

    x 轴来源优先级：x_variable > sample_rate（x=index/rate）> index。
    """

    def __init__(
        self,
        path: str,
        variable_name: str,
        x_variable: Optional[str] = None,
        sample_rate: Optional[float] = None,
        t0: float = 0.0,
    ) -> None:
        self.path = str(path)
        self.variable_name = variable_name
        self.x_variable = x_variable
        self.sample_rate = float(sample_rate) if sample_rate else None
        self.t0 = float(t0)
        self.format = detect_mat_format(self.path)
        self._h5 = None
        self._v5_data = None
        self._v5_x = None

    def __enter__(self) -> "MatReader":
        if self.format == "v7.3 (HDF5)":
            import h5py

            self._h5 = h5py.File(self.path, "r")
            if self.variable_name not in self._h5:
                raise KeyError(f"变量不存在：{self.variable_name}")
        else:
            from scipy.io import loadmat

            names = [self.variable_name]
            if self.x_variable:
                names.append(self.x_variable)
            loaded = loadmat(self.path, variable_names=names)
            if self.variable_name not in loaded:
                raise KeyError(f"变量不存在：{self.variable_name}")
            self._v5_data = np.asarray(loaded[self.variable_name]).ravel()
            if self.x_variable and self.x_variable in loaded:
                self._v5_x = np.asarray(loaded[self.x_variable]).ravel()
        return self

    def __exit__(self, *args: object) -> None:
        if self._h5 is not None:
            self._h5.close()
            self._h5 = None

    @property
    def n_points(self) -> int:
        if self._h5 is not None:
            return int(self._h5[self.variable_name].size)
        if self._v5_data is not None:
            return int(self._v5_data.size)
        raise RuntimeError("MatReader 未打开，先使用 with MatReader(...)")

    def read_indices(self, indices: np.ndarray) -> np.ndarray:
        indices = np.sort(np.unique(np.clip(indices.astype(np.int64), 0, self.n_points - 1)))
        if self._h5 is not None:
            ds = self._h5[self.variable_name]
            if ds.ndim == 1:
                data = np.asarray(ds[indices])
            elif ds.shape[0] == 1:
                data = np.asarray(ds[0, indices])
            elif ds.shape[-1] == 1:
                data = np.asarray(ds[indices, 0])
            else:
                raise ValueError(
                    f"变量 {self.variable_name} 是 {ds.shape} 维数组；"
                    "本 Skill 只处理一维或 (1,N)/(N,1) 波形变量"
                )
        else:
            data = np.asarray(self._v5_data)[indices]
        return data.ravel()

    def read_x_indices(self, indices: np.ndarray) -> np.ndarray:
        indices = np.clip(indices.astype(np.int64), 0, self.n_points - 1)
        if self.x_variable:
            if self._h5 is not None:
                return np.asarray(self._h5[self.x_variable][indices]).ravel()
            if self._v5_x is not None:
                return np.asarray(self._v5_x)[indices].ravel()
        base = np.arange(self.n_points, dtype=np.float64)
        x = indices.astype(np.float64) if self.sample_rate is None else indices.astype(np.float64) / self.sample_rate
        return x + self.t0

    def iter_chunks(
        self,
        chunk_size: int,
        start: int = 0,
        end: Optional[int] = None,
        include_x: bool = True,
    ) -> Iterator[Tuple[int, int, np.ndarray, np.ndarray]]:
        """逐块产出 (start, end, y_chunk, x_chunk)。"""
        end = self.n_points if end is None else min(int(end), self.n_points)
        start = max(0, int(start))
        for left in range(start, end, int(chunk_size)):
            right = min(left + int(chunk_size), end)
            idx = np.arange(left, right, dtype=np.int64)
            y = self.read_indices(idx)
            x = self.read_x_indices(idx) if include_x else np.asarray(idx, dtype=np.float64)
            yield left, right, y, x
