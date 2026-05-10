"""股票筛选交互工具 - 处理用户交互相关的辅助功能."""

from __future__ import annotations

import json
from typing import Any

from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


def extract_logic_from_result(result: dict) -> dict | None:
    """从查询结果中提取筛选逻辑.
    
    Args:
        result: 查询结果字典
        
    Returns:
        筛选逻辑字典，或 None
    """
    try:
        messages = result.get("messages", [])
        if not messages:
            logger.debug("[WARN] 结果中没有 messages 字段")
            return None
        
        for message in reversed(messages):
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tool_call in message.tool_calls:
                    # [OK] 支持多种工具名称
                    tool_name = tool_call.get("name", "")
                    if tool_name in ["run_screening", "cached_run_screening"]:
                        args = tool_call.get("args", {})
                        if "screening_logic_json" in args:
                            logic = json.loads(args["screening_logic_json"])
                            logger.info(f"[OK] 成功提取筛选逻辑: {logic.get('name', '未命名')}")
                            return logic
        
        logger.debug("[WARN] 未在消息中找到 run_screening 工具调用")
        return None
    except Exception as e:
        logger.error(f"[ERROR] 提取筛选逻辑失败: {type(e).__name__}: {e}", exc_info=True)
        return None


def show_help_menu(last_logic: dict | None, candidates_saved: bool) -> None:
    """显示帮助菜单.
    
    Args:
        last_logic: 上一次的筛选逻辑
        candidates_saved: 是否已保存候选股票
    """
    print(f"\n{'='*70}")
    print(f"[HELP] 帮助菜单")
    print(f"{'='*70}")
    print(f"\n📝 基本用法:")
    print(f"   • 直接输入策略描述，例如：")
    print(f"     '找出高波动且持续跑赢大盘的股票'")
    print(f"     '低估值高分红的蓝筹股'")
    print(f"\n⚙️  快捷命令:")
    print(f"   • edit  - 编辑上次策略")
    print(f"   • help  - 显示此帮助菜单")
    print(f"   • quit  - 退出系统")
    print(f"\n💡 工作流提示:")
    
    if last_logic and not candidates_saved:
        print(f"   • 当前有未保存的策略，建议先保存或编辑")
    elif last_logic:
        print(f"   • 已有策略，可以编辑优化或开始新查询")
    else:
        print(f"   • 暂无策略，请输入策略描述开始")
    
    print(f"\n🔧 高级功能:")
    print(f"   • 策略生成后可选择保存为 Python 脚本")
    print(f"   • 使用 edit 命令进入交互式编辑模式")
    print(f"   • 支持自然语言描述，系统自动转换为量化条件")
    print(f"{'='*70}")


def save_strategy_script(
    last_logic: dict,
    candidates: list,
    query: str,
    state_manager,
    settings
) -> None:
    """保存策略脚本（增强版 - 带详细错误提示）.
    
    Args:
        last_logic: 筛选逻辑
        candidates: 候选股票列表
        query: 原始查询
        state_manager: 状态管理器
        settings: 配置对象
    """
    print("\n📝 正在保存策略脚本...")
    try:
        from src.screening.script_saver import ScriptSaver
        from src.agent.tools.bridge import create_bridge_tools
        
        def get_data():
            return state_manager.data
        
        bridge_tools = create_bridge_tools(
            data_fn=get_data,
            scripts_dir=str(settings.output.strategies_dir),
            stock_codes=state_manager.stock_codes
        )
        
        script_saver = ScriptSaver(
            bridge_tools,
            auto_save=False  # 手动保存模式
        )
        
        # [OK] 关键修复：构建结果字典时必须包含筛选逻辑
        mock_result = {
            "candidates": candidates,
            "messages": [
                {
                    "tool_calls": [
                        {
                            "name": "run_screening",
                            "args": {
                                "screening_logic_json": json.dumps(last_logic, ensure_ascii=False)
                            }
                        }
                    ]
                }
            ]
        }
        
        save_result = script_saver.handle_save(mock_result, query)
        
        if save_result and save_result.get("status") == "success":
            # [OK] 修复：使用 script_paths（数组）而不是 script_path（单数）
            script_paths = save_result.get('script_paths', [])
            if script_paths:
                print(f"[OK] 脚本已保存 ({len(script_paths)} 个版本):")
                for path in script_paths:
                    print(f"   📄 {path}")
            else:
                print(f"[OK] 脚本已保存")
        else:
            # [OK] 增强：详细错误诊断
            error_detail = save_result.get('error', '未知错误') if save_result else 'handle_save 返回 None'
            print(f"[WARN] 脚本保存失败: {error_detail}")
            
            # 智能诊断
            if "strategy_name" in error_detail.lower() or "config" in error_detail.lower():
                print(f"\n[TIP] 可能原因: 策略名称在配置文件中未找到")
                print(f"   解决: 检查 screening_interactive.yaml 中的配置")
            elif "json" in error_detail.lower():
                print(f"\n[TIP] 可能原因: 筛选逻辑 JSON 格式错误")
                print(f"   解决: 检查 screening_logic 结构完整性")
            else:
                print(f"\n[TIP] 建议: 查看详细日志获取更多信息")
            
            logger.error(f"[ERROR] 脚本保存失败详情: {save_result}")
    
    except ImportError as e:
        print(f"[ERROR] 脚本保存失败: 缺少依赖模块 - {e}")
        logger.error(f"[ERROR] 导入错误: {e}", exc_info=True)
    
    except Exception as e:
        print(f"[ERROR] 脚本保存失败: {type(e).__name__}: {e}")
        logger.error(f"[ERROR] 脚本保存异常: {type(e).__name__}: {e}", exc_info=True)
