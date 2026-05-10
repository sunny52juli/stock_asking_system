"""结果处理器 - 负责质量评估、重试逻辑和结果显示."""

from __future__ import annotations

import time
from typing import Any

from infrastructure.logging.logger import get_logger
from src.screening.result_display import ResultDisplayer
from src.screening.script_saver import ScriptSaver
from utils.agent.result_checker import _is_screening_successful
from infrastructure.config.settings import get_settings
from src.agent.tools.bridge import create_bridge_tools

logger = get_logger(__name__)


class ResultProcessor:
    """结果处理器 - 处理Agent执行结果."""
    
    def __init__(self, quality_evaluator, hooks=None):
        """初始化.
        
        Args:
            quality_evaluator: 质量评估器
            hooks: HookExecutor实例（可选）
        """
        self.quality_evaluator = quality_evaluator
        self.hooks = hooks
        self.result_displayer = ResultDisplayer()
        self.script_saver: ScriptSaver | None = None
    
    def process_result(
        self,
        result: dict,
        query: str,
        session,
        query_id: int,
        execution_time_ms: float,
        data=None,
        stock_codes: list = None,
    ) -> dict:
        """处理Agent执行结果.
        
        Args:
            result: Agent执行结果
            query: 用户查询
            session: 会话对象
            query_id: 查询ID
            execution_time_ms: 执行时间
            data: 数据（批量模式）
            stock_codes: 股票代码列表
            
        Returns:
            处理后的结果
        """
        # Stop Hook: 质量门禁
        if self.hooks:
            hook_result = self.hooks.execute_stop({"result": result, "query": query})
            if hook_result.is_blocked:
                logger.warning(f"[WARN] Stop Hook阻止了结果返回: {hook_result.message}")
                result["hook_feedback"] = hook_result.message
        
        # 质量评估反馈循环
        quality_result = self.quality_evaluator.evaluate(query, result)
        result["quality_evaluation"] = quality_result
        
        # 如果质量问题严重，自动触发重试
        if quality_result.get("should_retry", False):
            logger.warning(f"\n[WARN] 检测到质量问题，尝试自动优化...")
            retry_result = self._retry_with_quality_feedback(
                query, result, quality_result, session
            )
            if retry_result:
                result = retry_result
                logger.info("[OK] 自动优化完成")
        
        # 显示结果
        self.result_displayer.display(result)
        
        # 保存脚本（根据配置决定是否询问）
        script_path = self._handle_script_save(result, query, data, stock_codes)
        
        # 更新查询记录
        self._update_session(session, query_id, result, script_path, execution_time_ms)
        
        return result
    
    def _retry_with_quality_feedback(
        self,
        query: str,
        result: dict,
        quality_result: dict,
        session
    ) -> dict | None:
        """基于质量反馈重试.
        
        Args:
            query: 用户查询
            result: 原始结果
            quality_result: 质量评估结果
            session: 会话对象
            
        Returns:
            重试结果或None
        """
        # TODO: 实现重试逻辑
        # 这里需要访问agent来重新执行查询
        logger.warning("[WARN] 重试功能待实现")
        return None
    
    def _handle_script_save(
        self,
        result: dict,
        query: str,
        data=None,
        stock_codes: list = None,
    ) -> str | None:
        """处理脚本保存.
        
        Args:
            result: Agent执行结果
            query: 用户查询
            data: 数据（批量模式）
            stock_codes: 股票代码列表
            
        Returns:
            脚本路径或None
        """
        script_path = None
        is_success = _is_screening_successful(result)
        
        if not is_success:
            logger.debug("[WARN] 未检测到筛选成功信号，跳过脚本保存")
            return None
        
        try:
            # 批量模式：使用data
            if data is not None:
                logger.debug("📝 批量模式：尝试自动保存脚本")
                
                def get_data():
                    return data
                
                # 初始化脚本保存器
                if self.script_saver is None:
                    settings = get_settings()
                    bridge_tools = create_bridge_tools(
                        data_fn=get_data,
                        scripts_dir=str(settings.output.strategies_dir),
                        stock_codes=stock_codes
                    )
                    
                    self.script_saver = ScriptSaver(
                        bridge_tools,
                        auto_save=True  # 批量模式下默认自动保存
                    )
                
                # 执行保存
                save_result = self.script_saver.handle_save(result, query)
                if save_result:
                    script_path = save_result.get("script_path")
                    logger.info(f"💾 脚本已保存: {script_path}")
            else:
                # 交互式模式：跳过手动保存
                logger.debug("[INFO] 交互式模式：跳过自动保存")
                
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"[ERROR] 脚本保存失败: {error_msg}", exc_info=True)
        
        return script_path
    
    def _update_session(
        self,
        session,
        query_id: int,
        result: dict,
        script_path: str | None,
        execution_time_ms: float,
    ):
        """更新会话记录.
        
        Args:
            session: 会话对象
            query_id: 查询ID
            result: Agent执行结果
            script_path: 脚本路径
            execution_time_ms: 执行时间
        """
        candidates_count = len(result.get("candidates", []))
        status = "success" if _is_screening_successful(result) else "failed"
        
        session.update_query_status(
            query_id=query_id,
            status=status,
            script_path=script_path,
            candidates_count=candidates_count,
            execution_time_ms=execution_time_ms,
        )
        
        session.save()
