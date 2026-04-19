#!/usr/bin/env python3
"""敏感信息检测 Hook - 防止 API Key、密码等写入代码."""

import re
import sys
from pathlib import Path


# 敏感信息模式
SENSITIVE_PATTERNS = [
    # API Keys
    (r'(?:api[_-]?key|apikey)\s*[:=]\s*["\']([A-Za-z0-9_\-]{20,})["\']', "API Key"),
    (r'sk-[A-Za-z0-9]{20,}', "OpenAI/SK Key"),
    (r'tushare[_-]?token\s*[:=]\s*["\']([A-Za-z0-9]{40,})["\']', "Tushare Token"),
    
    # Passwords
    (r'(?:password|passwd|pwd)\s*[:=]\s*["\']([^"\']{8,})["\']', "Password"),
    
    # AWS Credentials
    (r'AKIA[0-9A-Z]{16}', "AWS Access Key"),
    (r'(?:aws[_-]?secret)[_\s]*[:=]\s*["\']([A-Za-z0-9/+=]{40})["\']', "AWS Secret Key"),
    
    # Private Keys
    (r'-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----', "Private Key"),
    
    # Database URLs with credentials
    (r'(?:mysql|postgres|mongodb)://[^:]+:[^@]+@', "Database URL with credentials"),
]


def check_file(filepath: Path) -> list[str]:
    """检查单个文件中的敏感信息."""
    violations = []
    
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception as e:
        return [f"无法读取文件 {filepath}: {e}"]
    
    for pattern, secret_type in SENSITIVE_PATTERNS:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            line_num = content[:match.start()].count('\n') + 1
            violations.append(
                f"  ⚠️  Line {line_num}: 检测到 {secret_type}\n"
                f"     文件: {filepath}\n"
                f"     建议: 使用环境变量或 .env 文件管理敏感信息"
            )
    
    return violations


def main():
    """主函数."""
    if len(sys.argv) < 2:
        print("用法: python no-secrets.py <file1> [file2] ...")
        sys.exit(1)
    
    files = [Path(f) for f in sys.argv[1:]]
    all_violations = []
    
    for filepath in files:
        if not filepath.exists():
            continue
        
        # 跳过测试文件和示例文件
        if 'test_' in filepath.name or filepath.suffix not in ['.py', '.yaml', '.yml', '.json']:
            continue
        
        violations = check_file(filepath)
        all_violations.extend(violations)
    
    if all_violations:
        print("\nSensitive data detection failed:\n")
        for violation in all_violations:
            print(violation)
        print("\nPlease remove sensitive data before committing\n")
        sys.exit(1)
    else:
        print("Sensitive data check passed")
        sys.exit(0)


if __name__ == "__main__":
    main()
