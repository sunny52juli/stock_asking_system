"""清理所有 Python 文件中函数内部带缩进的 import，统一移到文件顶部."""

import re
from pathlib import Path


def clean_indented_imports(file_path: Path):
    """清理单个文件中带缩进的 import."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if not lines:
            return False
        
        original_lines = lines.copy()
        
        # 收集所有带缩进的 import 语句
        indented_imports = []
        cleaned_lines = []
        
        for line in lines:
            # 匹配带缩进的 from ... import 或 import ...
            if re.match(r'^\s{4,}(from\s+\S+\s+import|import\s+)', line):
                # 提取 import 语句（去除缩进）
                import_stmt = line.strip()
                if import_stmt and not import_stmt.startswith('#'):
                    indented_imports.append(import_stmt)
                    continue  # 跳过这一行
            cleaned_lines.append(line)
        
        # 如果有需要移动的 import
        if indented_imports:
            # 找到文件顶部的 import 区域结束位置
            insert_pos = 0
            for i, line in enumerate(cleaned_lines):
                stripped = line.strip()
                # 跳过 shebang、encoding、docstring、空行、注释
                if (stripped.startswith('#!') or 
                    stripped.startswith('# -*-') or
                    stripped.startswith('"""') or
                    stripped.startswith("'''") or
                    stripped == '' or
                    stripped.startswith('#')):
                    insert_pos = i + 1
                    continue
                # 遇到第一个非 import 的代码行，停止
                if not (stripped.startswith('from ') or stripped.startswith('import ')):
                    break
                insert_pos = i + 1
            
            # 在适当位置插入去重后的 import
            unique_imports = sorted(set(indented_imports))
            for imp in unique_imports:
                cleaned_lines.insert(insert_pos, imp + '\n')
                insert_pos += 1
            
            # 写回文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(cleaned_lines)
            
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
        
        if clean_indented_imports(py_file):
            print(f"✅ 已清理: {py_file.relative_to(project_root)}")
            cleaned_count += 1
    
    print(f"\n共清理 {cleaned_count} 个文件")


if __name__ == '__main__':
    main()
