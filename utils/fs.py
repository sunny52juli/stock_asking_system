"""文件系统工具 - 文件名清理、目录操作等."""

from __future__ import annotations

from pathlib import Path


def sanitize_filename(name: str) -> str:
    """清理文件名，移除非法字符.
    
    Args:
        name: 原始文件名
        
    Returns:
        清理后的文件名
    """
    illegal = ["/", "\\", ":", "*", "?", '"', "<", ">", "|", " ", "（", "）", "(", ")", "，", "。", "！", "？"]
    for c in illegal:
        name = name.replace(c, "_")
    while "__" in name:
        name = name.replace("__", "_")
    return name.strip("_")


def ensure_dir(path: str | Path) -> Path:
    """确保目录存在，不存在则创建.
    
    Args:
        path: 目录路径
        
    Returns:
        Path 对象
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
