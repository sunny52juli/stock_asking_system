# ============================================================================
# DEPRECATED - 此文件已被弃用
# ============================================================================
# 弃用原因: 此文件未被项目中任何其他模块引用或使用
# 替代方案: 请使用 src/agent/ 模块中的编排器功能
# 弃用日期: 2026-04-19
# ============================================================================

"""股票筛选主入口 - 使用 ScreenerOrchestrator 进行股票筛选和推荐."""

import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量（必须在所有其他导入之前）
load_dotenv()

# 获取项目根目录并确保在 path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.services.stock_pool_service import StockPoolService
from src.agent import ScreenerOrchestrator
from infrastructure.config.settings import get_settings
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


def main():
    """主函数 - 使用 ScreenerOrchestrator"""
    
    # 创建编排器（screener 不需要 backtest 配置）
    settings = get_settings(reload=True, config_files=["screening.yaml", "stock_pool.yaml"], project_root=PROJECT_ROOT)
    orchestrator = ScreenerOrchestrator(settings=settings)
    
    # 初始化系统（不加载数据）
    if not orchestrator.initialize():
        logger.error("系统初始化失败")
        return
    
    # 执行股票池过滤（StockPoolService 负责加载数据）
    logger.info("\n" + "=" * 60)
    logger.info("执行股票池过滤")
    logger.info("=" * 60)
    stock_pool_service = StockPoolService(settings)
    filtered_data, filtered_codes, index_data = stock_pool_service.apply_filter()
    
    # 检查过滤结果
    if len(filtered_codes) == 0:
        logger.error("❌ 股票池过滤后没有剩余股票！请检查 stock_pool.yaml 配置")
        raise RuntimeError("股票池过滤失败：结果为空")
    
    logger.info(f"✅ 股票池过滤完成：{len(filtered_codes)} 只股票")
    
    # 更新 Orchestrator 的数据并重新创建工具
    orchestrator.data = filtered_data
    orchestrator.stock_codes = filtered_codes
    orchestrator.index_data = index_data
    orchestrator.component_initializer.create_bridge_tools(
        data_fn=lambda: (orchestrator.data, orchestrator.index_data),
        stock_codes=orchestrator.stock_codes
    )
    orchestrator.component_initializer.create_tool_provider()
    logger.info("✅ Bridge 工具和 ToolProvider 已更新，Agent 将使用过滤后的股票池")
    
    # 执行查询
    queries = []
    for strategy_name, strategy_config in settings.strategies.items():
        if strategy_config.query:
            queries.append(strategy_config.query)
    


    logger.info(f"\n将执行 {len(queries)} 个查询\n")
    
    all_results = []
    
    for i, query in enumerate(queries, 1):
        result = orchestrator.execute_query(query, query_id=i)
        if result:
            all_results.append(result)
    
    logger.info("\n" + "=" * 60)
    logger.info(f"所有查询执行完成，成功：{len(all_results)}/{len(queries)}")
    logger.info("=" * 60)


def cli():
    """命令行入口"""
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        if mode in ["help", "-h", "--help"]:
            print("用法:")
            print("  python screener.py          # 执行默认查询列表")
            print("\n说明:")
            print("  - 使用最新交易日数据")
            print("  - 根据配置决定是否自动保存策略脚本")
            sys.exit(0)
        else:
            print(f"未知模式：{mode}")
            print("使用 --help 查看帮助")
            sys.exit(1)
    else:
        try:
            main()
        except KeyboardInterrupt:
            logger.info("\n用户中断程序")
            sys.exit(0)
        except Exception as e:
            logger.exception("程序异常：%s", e)
            sys.exit(1)


if __name__ == "__main__":
    cli()
