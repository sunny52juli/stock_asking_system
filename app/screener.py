"""股票筛选主入口 - 支持增量策略调整和数据复用."""

import sys
import os

# 修复 Windows 控制台 UTF-8 编码问题（必须在所有输出之前）
if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import json
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量（必须在所有其他导入之前）
load_dotenv()

# 获取项目根目录并确保在 path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.services.stock_pool_service import StockPoolService
from src.agent.core.orchestrator import ScreenerOrchestrator
from src.agent.execution.state_manager import SessionStateManager
from src.agent.interactive.mode_manager import InteractiveModeManager
from src.agent.tools.strategy_detector import validate_and_suggest
from infrastructure.config.settings import get_settings
from infrastructure.logging.logger import get_logger
from utils.screening.interactive_helpers import (
    extract_logic_from_result,
    show_help_menu,
    save_strategy_script,
)

logger = get_logger(__name__)


def main():
    """主函数 - 支持交互式策略调整."""
    # 使用精简版配置（移除冗余的 strategies 部分）
    settings = get_settings(
        reload=True, 
        config_files=["screening_interactive.yaml", "stock_pool.yaml"], 
        project_root=PROJECT_ROOT
    )
    
    # 初始化会话状态管理器（支持跨查询数据复用）
    state_manager = SessionStateManager(settings)
    
    # 初始化编排器
    orchestrator = ScreenerOrchestrator(settings, state_manager)
    
    print("=" * 70)
    print("[SYSTEM] 智能股票筛选系统 v2.0")
    print("   特性：数据缓存 | 增量计算 | 策略热调整")
    print("=" * 70)
    
    # 加载基础数据（带缓存）
    print("\n[DATA] 正在加载市场数据...")
    state_manager.load_base_data()
    print(f"[OK] 数据加载完成：{len(state_manager.data)} 条记录，"
          f"{len(state_manager.stock_codes)} 只股票")
    
    # 初始化编排器（在数据加载后）
    orchestrator.data = state_manager.data
    orchestrator.index_data = state_manager.index_data
    orchestrator.stock_codes = state_manager.stock_codes
    if not orchestrator.initialize():
        print("[ERROR] 系统初始化失败")
        return
    
    # 创建交互式模式管理器
    interactive_manager = InteractiveModeManager(orchestrator, state_manager)
    
    # 交互式查询循环
    query_count = 0
    last_logic = None  # 保存上一次的筛选逻辑
    candidates_saved = False  # 标记是否已保存候选股票
    
    while True:
        try:
            # [OK] 增强：智能输入提示
            # 根据当前状态动态生成提示词
            if query_count == 0:
                # 首次查询，显示引导信息
                print(f"\n{'='*70}")
                print(f"[TARGET] 欢迎使用交互式股票筛选系统")
                print(f"{'='*70}")
                print(f"[TIP] 热门策略示例:")
                print(f"   • 高波动跑赢大盘 (beta > 1.2 & outperform > 0.5)")
                print(f"   • 低估值高分红 (PE < 15 & dividend_yield > 3%)")
                print(f"   • 技术突破形态 (close > ma20 & volume_ratio > 2)")
                print(f"\n[CONFIG] 快捷命令:")
                print(f"   • edit - 编辑上次策略")
                print(f"   • help - 查看帮助")
                print(f"   • quit - 退出系统")
                print(f"{'='*70}")
                prompt = "📝 描述你的选股策略"
                hint = "例如：'找出高波动且持续跑赢大盘的股票'"
            elif last_logic and not candidates_saved:
                # 已有策略但未保存，提示保存或修改
                prompt = "💾 是否保存当前策略？"
                hint = "输入 'y' 保存 | 'edit' 修改 | 'n' 继续新查询"
            elif last_logic:
                # 已有策略，询问是否修改或继续
                prompt = "🔄 下一步操作"
                hint = "输入 'edit' 修改策略 | 直接输入新策略描述 | 'quit' 退出"
            else:
                # 无策略状态
                prompt = "📝 描述你的选股策略"
                hint = "例如：'找出高波动且持续跑赢大盘的股票'"
            
            query = input(
                f"{prompt}\n"
                f"   {hint}\n"
                f"> "
            ).strip()
            
            if not query:
                continue
            
            # [OK] 清理输入中的多余字符（如 '>'、'？'等）
            query = query.lstrip('>？').strip()
            
            if not query:
                continue
            
            # [OK] 先检测是否为命令，避免当作策略描述处理
            query_lower = query.lower()
            
            if query_lower in ['quit', 'exit', 'q']:
                print("\n[BYE] 感谢使用，再见！")
                break
            
            if query_lower in ['help', 'h', '?', '帮助']:
                show_help_menu(last_logic, candidates_saved)
                continue
            
            # [OK] 新增：进入交互式编辑模式（支持拼写纠错）
            if query_lower in ['edit', 'eidt', 'edti', 'edi']:
                new_query = interactive_manager.start_session(last_logic)
                # [OK] 智能回退处理：如果从编辑模式带回了自然语言查询
                if new_query:
                    print(f"\n[INFO] 正在执行新查询: {new_query}")
                    query = new_query
                    query_lower = query.lower()
                    # 跳过后续的命令检测，直接进入策略验证流程
                else:
                    # 正常退出编辑模式
                    last_logic = interactive_manager.get_current_logic()
                    candidates_saved = False  # 编辑后重置保存状态
                    continue
            
            # [OK] 验证是否为有效的策略描述
            validation = validate_and_suggest(query)
            
            if not validation["is_valid"]:
                if validation["type"] == "command":
                    # 是命令但未被上面的逻辑捕获
                    print(f"\n[INFO] {validation['suggestion']}")
                else:
                    # 无效输入，给出提示
                    print(f"\n[WARN] {validation['suggestion']}")
                continue  # 跳过后续处理，重新等待输入
            
            query_count += 1
            print(f"\n{'='*70}")
            print(f"[MENU] 查询 #{query_count}: {query}")
            print(f"{'='*70}")
            
            # 执行筛选（自动复用缓存）
            result = orchestrator.execute_query(query, query_count)
            
            # 显示结果
            # [OK] 关键修复：只要有候选股票就视为成功，无论 success 字段
            candidates = result.get("candidates", []) if isinstance(result, dict) else []
            has_candidates = candidates and len(candidates) > 0
            
            if result.get("success") or has_candidates:
                candidates = result.get("candidates", [])
                
                # [OK] 统一使用 ResultDisplayer 进行详细展示
                from src.screening.result_display import ResultDisplayer
                displayer = ResultDisplayer()
                # 构造包含逻辑和候选者的完整结果结构
                display_result = {
                    "candidates": candidates,
                    "screening_logic": extract_logic_from_result(result),
                    "success": True
                }
                displayer.display(display_result)
                
                # [OK] 关键修复：无论是否有候选股票，都尝试提取筛选逻辑
                last_logic = display_result["screening_logic"]
                
                # [OK] 增强：工作流快捷操作引导
                # 只要有 last_logic 就显示操作菜单（即使没有 candidates）
                if last_logic:
                    print(f"\n{'='*70}")
                    print(f"[MENU] 下一步操作:")
                    print(f"{'='*70}")
                    
                    # 显示当前策略信息
                    if last_logic:
                        expression = last_logic.get('expression', 'N/A')
                        print(f"[DATA] 当前表达式: {expression}")
                        
                        # 根据结果数量给出优化建议
                        if not candidates:
                            print(f"\n[TIP] 优化建议:")
                            print(f"   • 放宽阈值（如降低 beta/outperform 要求）")
                            print(f"   • 减少条件数量（移除次要条件）")
                            print(f"   • 调整时间窗口（如从 60 天改为 30 天）")
                        elif len(candidates) < 5:
                            print(f"\n[TIP] 优化建议:")
                            print(f"   • 当前结果较少，可适度放宽条件")
                            print(f"   • 或保持现状，这是精选策略")
                        else:
                            print(f"\n[TIP] 优化建议:")
                            print(f"   • 结果较多，可增加条件提高精准度")
                            print(f"   • 或调整置信度公式优化排序")
                    
                    print(f"")
                    if candidates:
                        print(f"   1. [SAVE] 保存策略脚本 (y)")
                    print(f"   2. [CONFIG] 编辑优化策略 (edit)")
                    print(f"   3. [SKIP]  跳过，继续新查询 (n)")
                    print(f"{'='*70}")
                    
                    try:
                        save_choice = input("\n请选择 [1-3]: ").strip().lower()
                        
                        # [OK] 支持多种输入方式
                        if save_choice in ['1', 'y', 'yes', '是', 'save']:
                            # 保存策略脚本
                            if candidates:
                                if last_logic:
                                    save_strategy_script(
                                        last_logic, candidates, query, 
                                        state_manager, settings
                                    )
                                    candidates_saved = True  # 标记已保存
                                else:
                                    print("[WARN] 没有可保存的策略逻辑")
                            else:
                                print("[WARN] 未找到候选股票，建议先编辑优化策略")
                        
                        elif save_choice in ['2', 'edit', 'e', '调整', 'optimize']:
                            # 进入编辑模式
                            if last_logic:
                                interactive_manager.start_session(last_logic)
                                last_logic = interactive_manager.get_current_logic()
                            else:
                                print("[WARN] 没有可编辑的策略逻辑，请先执行一次筛选")
                        
                        elif save_choice in ['3', 'n', 'no', '否', '', 'skip']:
                            # 跳过
                            print("[INFO] 已跳过，准备下一次查询")
                            candidates_saved = False  # 重置保存状态
                        
                        else:
                            # [OK] 智能纠错
                            print(f"[WARN] 无效输入: '{save_choice}'")
                            print(f"   请输入数字 1-3，或命令: y/edit/n")
                    
                    except (EOFError, KeyboardInterrupt):
                        print("\n[INFO] 已跳过操作选择")
                
                else:
                    # 既没有候选股票也没有筛选逻辑
                    print(f"\n[WARN] 本次查询未生成有效策略")
                    print(f"   建议: 尝试更明确的查询描述")
            else:
                # [OK] 增强：详细错误诊断
                if result is None:
                    error_msg = "查询结果为 None（Agent 执行失败）"
                    print(f"\n[ERROR] 筛选失败: {error_msg}")
                    print(f"\n[TIP] 可能原因:")
                    print(f"   1. LLM API 调用失败（检查网络连接和 API Key）")
                    print(f"   2. Agent 执行超时（复杂查询可能需要更长时间）")
                    print(f"   3. 系统内部错误（查看详细日志）")
                elif isinstance(result, dict):
                    error_msg = result.get('error', '未知错误')
                    print(f"\n[ERROR] 筛选失败: {error_msg}")
                                
                    # [OK] 智能诊断
                    if "timeout" in error_msg.lower() or "time out" in error_msg.lower():
                        print(f"\n[TIP] 可能原因: Agent 执行超时")
                        print(f"   解决: 简化查询条件或增加超时时间")
                    elif "api" in error_msg.lower() or "key" in error_msg.lower():
                        print(f"\n[TIP] 可能原因: API 配置问题")
                        print(f"   解决: 检查 .env 文件中的 API Key 配置")
                    elif "tool" in error_msg.lower():
                        print(f"\n[TIP] 可能原因: 工具执行失败")
                        print(f"   解决: 检查数据完整性或工具参数")
                    else:
                        print(f"\n[TIP] 建议: 查看详细日志获取更多信息")
                else:
                    error_msg = f"未知错误 - result 类型: {type(result).__name__}"
                    print(f"\n[ERROR] 筛选失败: {error_msg}")
                            
                # [OK] 简化调试信息：只打印关键错误字段
                if isinstance(result, dict):
                    error_detail = result.get('error', 'N/A')
                    candidates_count = len(result.get('candidates', []))
                    logger.debug(f"🔍 错误详情: error={error_detail}, candidates={candidates_count}")
        
        except KeyboardInterrupt:
            print("\n\n[BYE] 用户中断，再见！")
            break
        except Exception as e:
            print(f"\n[WARN] 发生错误: {e}")
            import traceback
            traceback.print_exc()
    
    # 清理资源
    state_manager.cleanup()


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
