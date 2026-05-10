"""脚本保存工具 - 处理策略脚本的保存逻辑."""

from __future__ import annotations

import json
from typing import Any

from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class ScriptSaver:
    """脚本保存器 - 处理策略脚本的自动保存和用户交互."""
    
    def __init__(self, bridge_tools: dict, auto_save: bool = False):
        """初始化脚本保存器.
        
        Args:
            bridge_tools: Bridge 工具字典
            auto_save: 是否自动保存（不询问用户）
        """
        self.bridge_tools = bridge_tools
        self.auto_save = auto_save
    
    def handle_save(self, result: dict, query: str) -> dict | None:
        """处理脚本保存逻辑.
        
        Args:
            result: 查询结果
            query: 用户查询
            
        Returns:
            保存结果字典（包含 script_path），或 None
        """
        # 延迟导入避免循环依赖
        from utils.agent.result_checker import _extract_screening_logic_from_result
        
        screening_logic_json = _extract_screening_logic_from_result(result)
        if not screening_logic_json:
            logger.warning("⚠️ 未找到筛选逻辑，无法保存脚本")
            return None
        
        # ✅ 直接保存，不再询问（调用方已经询问过）
        return self._save_script(screening_logic_json, query)
    
    def _save_script(self, screening_logic_json: str, query: str) -> dict | None:
        """执行脚本保存.
        
        Args:
            screening_logic_json: 筛选逻辑 JSON 字符串
            query: 用户查询
            
        Returns:
            保存结果字典（包含 script_path），或 None
        """
        try:
            save_result_json = self.bridge_tools["save_screening_script"](
                screening_logic_json, query
            )
            save_result = json.loads(save_result_json)
            if save_result.get("status") == "success":
                # ✅ 兼容 script_paths (数组) 和 script_path (单数)
                script_paths = save_result.get('script_paths', [])
                script_path = save_result.get('script_path', '') or save_result.get('filename', '')
                
                if script_paths:
                    logger.info(f"\n💾 策略脚本已保存 ({len(script_paths)} 个版本)")
                    for path in script_paths:
                        logger.debug(f"   - {path}")
                elif script_path:
                    logger.info(f"\n💾 策略脚本已保存：{script_path}")
                else:
                    logger.info(f"\n💾 策略脚本已保存")
                return save_result
            else:
                error_msg = save_result.get('error', '未知错误')
                logger.warning(f"⚠️ 脚本保存失败：{error_msg}")
                return {"status": "failed", "error": error_msg}
        except Exception as e:
            logger.error(f"❌ 脚本保存异常: {type(e).__name__}: {e}", exc_info=True)
            return {"status": "failed", "error": str(e)}
