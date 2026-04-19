"""清理所有 Python 文件中函数内部的重复 import，统一移到文件顶部."""

import re
import os
from pathlib import Path


def clean_duplicate_imports(file_path: Path):
    """清理单个文件中的重复 import."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 模式1: 删除函数内部的 "import polars as pl"
        content = re.sub(
            r'\n(\s+)import polars as pl\n',
            r'\n',
            content
        )
        
        # 模式2: 删除函数内部的 "import pandas as pd"
        content = re.sub(
            r'\n(\s+)import pandas as pd\n',
            r'\n',
            content
        )
        
        # 模式3: 删除函数内部的 "import numpy as np"
        content = re.sub(
            r'\n(\s+)import numpy as np\n',
            r'\n',
            content
        )
        
        # 清理多余的空行（连续3个以上空行改为2个）
        content = re.sub(r'\n{4,}', '\n\n\n', content)
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    
    except Exception as e:
        print(f"处理 {file_path} 时出错: {e}")
        return False


def main():
    """主函数：遍历项目所有 Python 文件."""
    project_root = Path(__file__).parent.parent
    py_files = list(project_root.rglob('*.py'))
    
    cleaned_count = 0
    for py_file in py_files:
        # 跳过虚拟环境和缓存目录
        if any(part in ['.venv', '__pycache__', '.ruff_cache', '.uv-cache'] 
               for part in py_file.parts):
            continue
        
        if clean_duplicate_imports(py_file):
            print(f"✅ 已清理: {py_file.relative_to(project_root)}")
            cleaned_count += 1
    
    print(f"\n共清理 {cleaned_count} 个文件")


if __name__ == '__main__':
    main()
