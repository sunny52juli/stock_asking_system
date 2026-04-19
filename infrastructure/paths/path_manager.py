#!/usr/bin/env python3
"""
from utils.path_manager import PathManager, ensure_project_path
from utils.path_manager import ensure_project_path
路径管理器 - 统一的项目路径管理

解决问题：
- 项目中多处使用不同方式添加系统路径
- 路径处理不一致导致导入问题

使用方法：

    # 方式1：使用类
    pm = PathManager()
    print(pm.project_root)

    # 方式2：使用便捷函数（推荐）
    ensure_project_path()  # 确保项目路径在 sys.path 中
"""

import sys
from pathlib import Path
from typing import Optional

# 计算项目根目录（此文件位于 src/ 下）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class PathManager:
    """
    项目路径管理器

    提供统一的路径管理接口，避免各模块重复添加路径。

    属性：
        project_root: 项目根目录
        core_dir: src 模块目录
        config_dir: config 配置目录
        datamodule_dir: datamodule 数据模块目录
        data2parquet_dir: data2parquet 数据接口目录
    """

    _instance: Optional['PathManager'] = None
    _initialized: bool = False

    def __new__(cls) -> 'PathManager':
        """单例模式确保只有一个实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化路径管理器"""
        if PathManager._initialized:
            return

        self._project_root = _PROJECT_ROOT
        self._ensure_path()
        PathManager._initialized = True

    @property
    def project_root(self) -> Path:
        """获取项目根目录"""
        return self._project_root

    @property
    def core_dir(self) -> Path:
        """获取 src 模块目录"""
        return self._project_root / "src"

    @property
    def config_dir(self) -> Path:
        """获取 config 配置目录"""
        return self._project_root / "config"

    @property
    def datamodule_dir(self) -> Path:
        """获取 datamodule 数据模块目录"""
        return self._project_root / "datamodule"

    @property
    def data2parquet_dir(self) -> Path:
        """获取 data2parquet 数据接口目录"""
        return self._project_root / "data2parquet"

    @property
    def dataloader_dir(self) -> Path:
        """获取 dataloader 目录（data2parquet 的别名）"""
        return self._project_root / "dataloader"

    @property
    def factor_backtest_dir(self) -> Path:
        """获取因子回测系统目录"""
        return self._project_root / "factor_backtest_system"

    @property
    def stock_asking_dir(self) -> Path:
        """获取股票查询系统目录"""
        return self._project_root / "stock_asking_system"

    def _ensure_path(self) -> None:
        """确保项目根目录在 sys.path 中"""
        root_str = str(self._project_root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)

    def get_path(self, *parts: str) -> Path:
        """
        获取项目内的路径

        Args:
            *parts: 路径部分

        Returns:
            完整路径

        Example:
            pm = PathManager()
            config_path = pm.get_path("config", "api.py")
        """
        return self._project_root.joinpath(*parts)

    def ensure_dir_exists(self, dir_path: Path) -> Path:
        """
        确保目录存在，不存在则创建

        Args:
            dir_path: 目录路径

        Returns:
            目录路径
        """
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path


# 全局单例实例
_path_manager: PathManager | None = None


def get_path_manager() -> PathManager:
    """
    获取路径管理器单例

    Returns:
        PathManager 实例
    """
    global _path_manager
    if _path_manager is None:
        _path_manager = PathManager()
    return _path_manager


def ensure_project_path() -> Path:
    """
    确保项目路径在 sys.path 中（便捷函数）

    这是最推荐的使用方式，在模块开头调用：

        ensure_project_path()

    Returns:
        项目根目录路径
    """
    pm = get_path_manager()
    return pm.project_root


def get_project_root() -> Path:
    """
    获取项目根目录（便捷函数）

    Returns:
        项目根目录路径
    """
    return get_path_manager().project_root


# 模块导入时自动确保路径
ensure_project_path()
