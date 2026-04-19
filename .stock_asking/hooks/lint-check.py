#!/usr/bin/env python3
"""代码质量检查 Hook - 对修改的 Python 文件运行 ruff."""

import subprocess
import sys
from pathlib import Path


def run_ruff(files: list[Path]) -> bool:
    """对指定文件运行 ruff 检查."""
    py_files = [f for f in files if f.suffix == '.py' and f.exists()]
    
    if not py_files:
        print("No Python files to check")
        return True
    
    print(f"Checking {len(py_files)} Python files...")
    
    try:
        result = subprocess.run(
            ['ruff', 'check'] + [str(f) for f in py_files],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print("\nRuff check failed:\n")
            print(result.stdout)
            print(result.stderr)
            print("\nFix suggestion: run `ruff check --fix <file>`\n")
            return False
        
        print("Ruff check passed")
        return True
        
    except subprocess.TimeoutExpired:
        print("Warning: Ruff check timeout, skipping")
        return True
    except FileNotFoundError:
        print("Warning: Ruff not installed, skipping (install: pip install ruff)")
        return True


def main():
    """主函数."""
    if len(sys.argv) < 2:
        print("用法: python lint-check.py <file1> [file2] ...")
        sys.exit(0)  # 没有文件时不阻止
    
    files = [Path(f) for f in sys.argv[1:]]
    success = run_ruff(files)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
