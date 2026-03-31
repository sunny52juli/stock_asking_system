#!/usr/bin/env python3
"""
Screener DeepAgent 主入口 - 简化版

只提供策略脚本生成和股票推荐功能，使用最近交易日数据
不计算收益率，不回测历史表现

"""

import io
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 设置 Windows 终端 UTF-8 编码
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 获取项目根目录并确保在 path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.logger import get_logger
from screener_deepagent.agent_factory import create_screener_agent
from config.screener_deepagent_config import ScreenerDeepAgentConfig
from screener_deepagent.context.skill_registry import SkillRegistry
from datahub.data_loader import load_latest_market_data
from screener_deepagent.llm import build_llm_from_api_config
from screener_deepagent.memory.long_term import SQLiteLongTermMemory
from screener_deepagent.tools.bridge import create_bridge_tools
from screener_deepagent.tools.provider import ScreenerToolProvider
from utils.check import _check_api_key, _extract_screening_logic_from_result, _is_screening_successful
logger = get_logger(__name__)




def main():
    """
    主函数 - 简化工作流
    
    流程:
      1. 加载最近交易日数据
      2. 构建 Agent (Intent → Planner → Executor)
      3. 执行查询并显示推荐股票
      4. 手动选择是否保存策略脚本
    """
    logger.info("=" * 60)
    logger.info("Screener DeepAgent - AI 股票推荐系统")
    logger.info("=" * 60)

    if not _check_api_key():
        return

    try:

        # 加载市场数据（使用 backtest_config 配置的日期范围，确保满足观察期要求）
        from datahub import load_market_data_for_backtest
        data = load_market_data_for_backtest(force_reload=False)
        
        # 构建 LLM
        api_config = ScreenerDeepAgentConfig.get_api_config()
        llm = build_llm_from_api_config(api_config)

        # 加载 MCP 工具
        logger.info("正在加载 MCP 工具...")
        try:
            import asyncio
            from langchain_mcp_adapters.client import MultiServerMCPClient  # type: ignore
            
            # 直接使用硬编码配置，避免 JSON 文件问题
            connections = {
                "screener-mcp": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["-m", "screener_mcp.server"],
                }
            }
            
            logger.info(f"MCP 连接配置：{connections}")
            
            # 在 async 中获取 MCP 工具
            async def _load_mcp_tools():
                client = MultiServerMCPClient(connections)
                return await client.get_tools()
            
            mcp_tools = asyncio.run(_load_mcp_tools())
            
            # 统计工具数量和名称
            tool_names = [getattr(tool, 'name', f'tool_{i}') for i, tool in enumerate(mcp_tools)]
            logger.info(f"✅ 成功加载 {len(mcp_tools)} 个 MCP 工具")
            logger.info(f"📋 工具列表：{', '.join(tool_names[:10])}{'...' if len(tool_names) > 10 else ''}")
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            logger.warning(f"⚠️ MCP 工具加载失败：{type(e).__name__}: {e}")
            logger.warning(f"详细错误:\n{error_detail}")
            logger.warning("将只使用 bridge 工具")
            mcp_tools = []

        # 创建桥接工具（仅包含筛选和行业查询工具，不需要收益率计算）
        bridge_tools_dict = create_bridge_tools(
            data_fn=lambda: data,
            scripts_dir=str(ScreenerDeepAgentConfig.get_scripts_dir()),
        )

        # 创建工具提供者
        tool_provider = ScreenerToolProvider(
            mcp_tools=mcp_tools,  # 传入 MCP 工具
            bridge_tools=bridge_tools_dict,
        )

        # 初始化技能和记忆
        logger.info("初始化 Skills Registry...")
        skill_registry = SkillRegistry()
        skills_dir = ScreenerDeepAgentConfig.SKILLS_DIR
        if skills_dir.exists():
            skill_registry.load_local_skills(str(skills_dir))

        logger.info("初始化 Long-term Memory...")
        long_term_memory = SQLiteLongTermMemory()

        # 创建 Agent
        logger.info("创建 DeepAgent...")
        agent, initial_files = create_screener_agent(
            llm=llm,
            tool_provider=tool_provider,
            skill_registry=skill_registry,
            long_term_memory=long_term_memory,
            skills_dir=skills_dir,
        )

    except Exception as e:
        logger.exception("初始化失败：%s", e)
        return

    # 执行查询
    queries = ScreenerDeepAgentConfig.get_demo_queries()
    logger.info(f"\n将执行 {len(queries)} 个查询\n")

    all_results = []

    for i, query in enumerate(queries, 1):
        logger.info("=" * 60)
        logger.info(f"查询 {i}/{len(queries)}: {query}")
        logger.info("=" * 60)
        
        # 标记本次查询是否已保存过脚本（避免重复保存）
        script_saved_for_this_query = False
        
        try:
            # 调用 Agent
            result = agent.invoke(
                {
                    "messages": [{"role": "user", "content": query}],
                    "files": initial_files,
                },
                config={"configurable": {"thread_id": f"query-{i}"}},
            )

            logger.info("\n✅ 查询完成")
            
            if result.get("messages"):
                final_message = result["messages"][-1]
                content = (
                    final_message.content 
                    if hasattr(final_message, 'content') 
                    else str(final_message)
                )
                
                logger.info("\n📊 Agent 分析结果:")
                logger.info("-" * 60)
                logger.info(content[:800])  # 显示前 800 字符，查看更多内容
                
                # 尝试提取并显示推荐的股票代码
                import re
                stock_codes = re.findall(r'\b[0-9]{6}\.[A-Z]{2}\b', content)
                if stock_codes:
                    logger.info("\n🎯 推荐股票:")
                    logger.info("-" * 60)
                    for code in stock_codes[:20]:  # 最多显示 20 只
                        logger.info(f"  - {code}")
                    if len(stock_codes) > 20:
                        logger.info(f"  ... 还有 {len(stock_codes) - 20} 只股票")
                else:
                    logger.info("\n⚠️ 未检测到明确的股票代码，可能筛选失败或需要检查数据")
                
                all_results.append(result)

                # 询问用户是否保存筛选脚本（每次查询只保存一次）
                if _is_screening_successful(result) and not script_saved_for_this_query:
                    screening_logic_json = _extract_screening_logic_from_result(result)
                    if screening_logic_json:
                        logger.info("\n💡 检测到筛选成功，是否保存策略脚本？")
                        try:
                            user_input = input("\n是否保存此策略脚本？(y/n): ").strip().lower()
                            
                            if user_input in ['y', 'yes', '是']:
                                save_result_json = bridge_tools_dict["save_screening_script"](
                                    screening_logic_json, query
                                )
                                save_result = json.loads(save_result_json)
                                if save_result.get("status") == "success":
                                    logger.info(
                                        f"\n💾 策略脚本已保存：{save_result.get('filename', 'unknown')}"
                                    )
                                    # 标记已保存，不再重复保存
                                    script_saved_for_this_query = True
                                else:
                                    logger.warning(
                                        f"⚠️ 脚本保存失败：{save_result.get('error', '未知错误')}"
                                    )
                            elif user_input in ['n', 'no', '否']:
                                logger.info("⏭️ 跳过保存脚本")
                            else:
                                logger.info("⚠️ 无效输入，跳过保存脚本")
                        except KeyboardInterrupt:
                            logger.info("\n用户中断保存操作")
                        except Exception as e:
                            logger.warning(f"⚠️ 保存脚本时出错：{e}")

        except KeyboardInterrupt:
            logger.warning("\n用户中断程序")
            break
        except Exception as e:
            logger.exception("查询失败：%s", e)

    logger.info("\n" + "=" * 60)
    logger.info(f"所有查询执行完成，成功：{len(all_results)}/{len(queries)}")
    logger.info("=" * 60)


def cli():
    """命令行入口"""
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        if mode == "help" or mode == "-h" or mode == "--help":
            print("用法:")
            print("  python -m screener_deepagent.run          # 执行默认查询列表")
            print("  quant-query-deepagent                     # 通过脚本入口")
            print("\n说明:")
            print("  - 使用最近交易日数据")
            print("  - 手动选择是否保存策略脚本")
            print("  - 不计算历史收益率")
            sys.exit(0)
        else:
            print(f"未知模式：{mode}")
            print("使用 --help 查看帮助")
            sys.exit(1)
    else:
        try:
            main()
        except KeyboardInterrupt:
            print("\n\n⚠️ 用户中断程序")
            sys.exit(0)
        except Exception as e:
            logger.exception("程序异常：%s", e)
            sys.exit(1)


if __name__ == "__main__":
    cli()
