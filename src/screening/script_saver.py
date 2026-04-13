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
    
    def handle_save(self, result: dict, query: str):
        """处理脚本保存逻辑.
        
        Args:
            result: 查询结果
            query: 用户查询
        """
        # 延迟导入避免循环依赖
        from utils.agent.result_checker import _extract_screening_logic_from_result
        
        screening_logic_json = _extract_screening_logic_from_result(result)
        if not screening_logic_json:
            return
        
        # 如果配置为自动保存，直接保存不询问
        if self.auto_save:
            self._save_script(screening_logic_json, query)
            return
        
        # 否则询问用户
        logger.info("\n💡 检测到筛选成功，是否保存策略脚本？)")
        try:
            user_input = input("\n是否保存此策略脚本？(y/n): ").strip().lower()
            
            if user_input in ['y', 'yes', '是']:
                self._save_script(screening_logic_json, query)
            elif user_input in ['n', 'no', '否']:
                logger.info("⏭️ 跳过保存脚本")
            else:
                logger.info("⚠️ 无效输入，跳过保存脚本)")
        except KeyboardInterrupt:
            logger.info("\n用户中断保存操作")
        except Exception as e:
            logger.warning(f"⚠️ 保存脚本时出错：{e}")
    
    def _save_script(self, screening_logic_json: str, query: str):
        """执行脚本保存.
        
        Args:
            screening_logic_json: 筛选逻辑 JSON 字符串
            query: 用户查询
        """
        save_result_json = self.bridge_tools["save_screening_script"](
            screening_logic_json, query
        )
        save_result = json.loads(save_result_json)
        if save_result.get("status") == "success":
            logger.info(f"\n💾 策略脚本已保存：{save_result.get('filename', 'unknown')}")
        else:
            logger.warning(f"⚠️ 脚本保存失败：{save_result.get('error', '未知错误')}")
