"""股票筛选主入口 - 使用 ScreenerOrchestrator 进行股票筛选和推荐."""

import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 获取项目根目录并确保在 path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent import ScreenerOrchestrator
from infrastructure.config.settings import get_settings
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


def main():
    """主函数 - 使用 ScreenerOrchestrator"""
    
    # 创建编排器（screener 不需要 backtest 配置）
    settings = get_settings(reload=True, config_files=["screening.yaml", "stock_pool.yaml"])
    orchestrator = ScreenerOrchestrator(settings=settings)
    
    # 初始化系统
    if not orchestrator.initialize():
        logger.error("系统初始化失败")
        return
    
    # 执行股票池过滤（独立服务模块，只执行一次）
    logger.info("\n" + "=" * 60)
    logger.info("执行股票池过滤")
    logger.info("=" * 60)
    from src.agent.services.stock_pool_service import StockPoolService
    stock_pool_service = StockPoolService(settings)
    filtered_data, filtered_codes = stock_pool_service.apply_filter(
        orchestrator.data, 
        orchestrator.stock_codes
    )
    logger.info(f"✅ 股票池过滤完成：{len(filtered_codes)} 只股票")
    
    # 更新 Orchestrator 的数据并重新创建工具
    orchestrator.data = filtered_data
    orchestrator.stock_codes = filtered_codes
    orchestrator.component_initializer.create_bridge_tools(
        data_fn=lambda: orchestrator.data,
        stock_codes=orchestrator.stock_codes
    )
    orchestrator.component_initializer.create_tool_provider()
    
    # 执行查询
    queries = []
    for strategy_name, strategy_config in settings.strategies.items():
        if strategy_config.query:
            queries.append(strategy_config.query)
    
    if not queries:
        queries = ["找出最近放量突破的股票"]
    

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
