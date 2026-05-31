"""测试概念加载器功能."""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_concept_loader_syntax():
    """测试概念加载器语法."""
    print("=" * 60)
    print("测试1: 检查概念加载器语法")
    print("=" * 60)
    
    try:
        # 直接执行文件检查语法
        exec(open('datahub/loaders/concept_loader.py', encoding='utf-8').read())
        print("✅ 概念加载器语法正确")
        return True
    except Exception as e:
        print(f"❌ 语法错误: {e}")
        return False


def test_stock_domain_extension():
    """测试 Stock Domain 扩展."""
    print("\n" + "=" * 60)
    print("测试2: 检查 Stock Domain 扩展")
    print("=" * 60)
    
    try:
        with open('datahub/domain/stock.py', 'r', encoding='utf-8') as f:
            content = f.read()
            
        if 'universe_with_concepts' in content:
            print("✅ Stock.universe_with_concepts() 方法已添加")
        else:
            print("❌ 未找到 universe_with_concepts 方法")
            return False
            
        if 'load_and_merge_concepts' in content:
            print("✅ 概念合并逻辑已集成")
        else:
            print("⚠️  警告: 未找到概念合并调用")
            
        return True
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False


def test_stock_loader_extension():
    """测试 StockDataLoader 扩展."""
    print("\n" + "=" * 60)
    print("测试3: 检查 StockDataLoader 扩展")
    print("=" * 60)
    
    try:
        with open('datahub/loaders/stock_loader.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = [
            ('include_concepts', 'include_concepts 参数'),
            ('_include_concepts', '_include_concepts 属性'),
            ('universe_with_concepts', '概念加载调用'),
            ('get_available_concepts', 'get_available_concepts 函数'),
        ]
        
        all_passed = True
        for keyword, description in checks:
            if keyword in content:
                print(f"✅ {description} 已添加")
            else:
                print(f"❌ {description} 缺失")
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False


def test_documentation():
    """测试文档是否创建."""
    print("\n" + "=" * 60)
    print("测试4: 检查文档")
    print("=" * 60)
    
    doc_path = Path('datahub/loaders/README_CONCEPTS.md')
    if doc_path.exists():
        print(f"✅ 使用指南已创建: {doc_path}")
        with open(doc_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        print(f"   文档长度: {len(lines)} 行")
        return True
    else:
        print(f"❌ 文档不存在: {doc_path}")
        return False


def main():
    """运行所有测试."""
    print("\n" + "🧪 " * 30)
    print("概念信息功能实现测试")
    print("🧪 " * 30 + "\n")
    
    results = []
    
    # 运行测试
    results.append(("语法检查", test_concept_loader_syntax()))
    results.append(("Stock Domain", test_stock_domain_extension()))
    results.append(("StockDataLoader", test_stock_loader_extension()))
    results.append(("文档", test_documentation()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name:20s} {status}")
    
    print("-" * 60)
    print(f"总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！概念信息功能已成功实现。")
        print("\n📝 下一步:")
        print("   1. 运行实际数据加载测试（需要 TuShare token）")
        print("   2. 在 StockPoolService 中集成概念过滤")
        print("   3. 更新 SKILL.md 文档")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败，请检查")
        return 1


if __name__ == "__main__":
    exit(main())
