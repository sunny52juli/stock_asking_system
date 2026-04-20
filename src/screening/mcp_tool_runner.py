"""工具执行器 - 负责执行 MCP 工具并管理依赖."""

from __future__ import annotations

import inspect
from collections import defaultdict, deque
from typing import Any
import polars as pl
from infrastructure.logging.logger import get_logger
from mcp_server.executors import execute_tool

logger = get_logger(__name__)


class ToolExecutor:
    """工具执行器 - 负责执行 MCP 工具并管理依赖."""

    def __init__(self, index_data: pl.DataFrame | None = None):
        """初始化工具执行器.
        
        Args:
            index_data: 指数数据 DataFrame，可选
        """
        self.index_data = index_data
        # 自动检测哪些工具需要 index_data 参数
        self._index_tool_cache = {}
    
    def _needs_index_data(self, tool_name: str) -> bool:
        """检查工具是否需要 index_data 参数."""
        if tool_name in self._index_tool_cache:
            return self._index_tool_cache[tool_name]
        
        # 延迟导入避免循环依赖
        from mcp_server.executors import TOOL_FUNCTIONS
        
        # 从注册的工具函数中检查签名
        if tool_name in TOOL_FUNCTIONS:
            func = TOOL_FUNCTIONS[tool_name]
            sig = inspect.signature(func)
            needs_index = 'index_data' in sig.parameters
            self._index_tool_cache[tool_name] = needs_index
            return needs_index
        
        # 如果找不到工具，默认不需要
        self._index_tool_cache[tool_name] = False
        return False

    def execute_tools(
        self,
        valid_data: pl.DataFrame,
        tools: list[dict],
        pre_filter_vars: dict[str, bool] | None = None,
    ) -> tuple[dict, int]:
        """执行工具列表.
        
        Args:
            valid_data: 有效股票数据
            tools: 工具步骤列表
            pre_filter_vars: 预筛选变量
            
        Returns:
            (命名空间, 错误计数)
        """
        from src.screening.namespace_builder import NamespaceBuilder
        
        namespace = NamespaceBuilder.build_namespace(valid_data)
        if pre_filter_vars:
            namespace.update(pre_filter_vars)
        
        tool_error_count = 0
        
        # 日志：检查指数数据
        if self.index_data is not None and not self.index_data.is_empty():
            logger.info(f"   📊 指数数据可用: {len(self.index_data)} 条记录")
        else:
            logger.warning("   ⚠️ 指数数据为空，指数相关工具将返回 NaN")
        
        # 对工具进行拓扑排序
        sorted_tools = self._topological_sort_tools(tools, valid_data.columns)
        
        logger.info(f"   📦 执行 {len(sorted_tools)} 个主工具...")
        
        # 当前工作数据（会逐步添加工具结果列）
        working_data = valid_data.clone()
        
        for i, tool_step in enumerate(sorted_tools, 1):
            tool_name = tool_step.get("name") or tool_step.get("tool")
            params = tool_step.get("params", {})
            var_name = tool_step.get("var")
            
            if not tool_name or not var_name:
                logger.warning(f"      ⚠️ 工具步骤 {i}: 缺少必要字段")
                continue
            
            try:
                # 自动检测是否需要 index_data 参数
                needs_index = self._needs_index_data(tool_name)
                
                # 使用 Pydantic 验证参数（强制约束参数名）
                from mcp_server.auto_register import tool_registry
                params = tool_registry.validate_params(tool_name, params)
                
                # 调用 MCP 工具执行器，仅指数工具传递 index_data
                if needs_index and self.index_data is not None:
                    logger.debug(f"   调用工具 {tool_name}，index_data: {len(self.index_data)} 条记录")
                    tool_result = execute_tool(
                        tool_name=tool_name,
                        data=working_data,
                        index_data=self.index_data,
                        **params
                    )
                else:
                    tool_result = execute_tool(
                        tool_name=tool_name,
                        data=working_data,
                        **params
                    )
                
                # 提取结果（可能是 Series 或 DataFrame）
                result, working_data = self._extract_result(tool_result, var_name, working_data)
                
                if result is not None:
                    # Series 情况：添加到 namespace 和 working_data
                    namespace[var_name] = result
                    working_data = working_data.with_columns(result.alias(var_name))
                else:
                    # DataFrame 已 join 的情况：从 working_data 中提取列到 namespace
                    if var_name in working_data.columns:
                        namespace[var_name] = working_data.get_column(var_name)
                    
            except Exception as e:
                tool_error_count += 1
                logger.error(f"      [{i}/{len(sorted_tools)}] ❌ {tool_name} → {var_name} 失败：{e}")
                
                # 根据错误类型决定处理方式
                if self._is_recoverable_error(e):
                    # 可恢复错误（数据问题）：填充 NaN，继续执行
                    logger.warning(f"         ⚠️  可恢复错误，将 {var_name} 设为 NaN")
                    working_data = working_data.with_columns(
                        pl.lit(None).cast(pl.Float64).alias(var_name)
                    )
                    namespace[var_name] = None
                else:
                    # 不可恢复错误（系统问题）：立即抛出
                    logger.error(f"         🛑 不可恢复错误，终止执行")
                    raise RuntimeError(
                        f"工具 '{tool_name}' 执行失败（不可恢复）: {e}\n"
                        f"提示：请检查表达式语法或工具参数是否正确"
                    ) from e
        
        logger.info(
            f"   ✅ 工具执行完成，成功：{len(sorted_tools) - tool_error_count}, "
            f"失败：{tool_error_count}"
        )
        return namespace, tool_error_count

    def _extract_result(
        self,
        tool_result: Any,
        var_name: str,
        working_data: pl.DataFrame,
    ) -> tuple[pl.Series | None, pl.DataFrame]:
        """从工具结果中提取 Series.
        
        Returns:
            (提取的 Series 或 None, 更新后的 working_data)
        """
        if isinstance(tool_result, pl.Series):
            return tool_result, working_data
        elif isinstance(tool_result, pl.DataFrame):
            # 如果返回 DataFrame，尝试提取与 var_name 匹配的列
            if var_name in tool_result.columns:
                # 单列情况：直接提取
                if len(tool_result.columns) == 1:
                    return tool_result[var_name], working_data
                else:
                    # 多列但包含 var_name：提取该列
                    return tool_result[var_name], working_data
            elif 'ts_code' in tool_result.columns and var_name in tool_result.columns:
                # 指数工具返回格式：包含 ts_code, trade_date, var_name
                # 需要 join 到 working_data
                if 'trade_date' in tool_result.columns and 'trade_date' in working_data.columns:
                    # 通过 ts_code 和 trade_date join
                    working_data = working_data.join(
                        tool_result.select(['ts_code', 'trade_date', var_name]),
                        on=['ts_code', 'trade_date'],
                        how='left'
                    )
                else:
                    # 只通过 ts_code join
                    working_data = working_data.join(
                        tool_result.select(['ts_code', var_name]),
                        on='ts_code',
                        how='left'
                    )
                return None, working_data
            elif 'ts_code' in tool_result.columns:
                # 工具返回的列名与 var_name 不匹配（如 beta vs beta_60）
                # 找到实际的结果列（排除 ts_code, trade_date）
                result_cols = [c for c in tool_result.columns if c not in ['ts_code', 'trade_date']]
                if len(result_cols) == 1:
                    actual_col = result_cols[0]
                    # 重命名为 var_name
                    tool_result_renamed = tool_result.rename({actual_col: var_name})
                    
                    if 'trade_date' in tool_result_renamed.columns and 'trade_date' in working_data.columns:
                        working_data = working_data.join(
                            tool_result_renamed.select(['ts_code', 'trade_date', var_name]),
                            on=['ts_code', 'trade_date'],
                            how='left'
                        )
                    else:
                        working_data = working_data.join(
                            tool_result_renamed.select(['ts_code', var_name]),
                            on='ts_code',
                            how='left'
                        )
                    return None, working_data
            
            # 多列情况，合并到 working_data
            for col in tool_result.columns:
                if col not in working_data.columns:
                    working_data = working_data.with_columns(tool_result[col].alias(col))
            return None, working_data
        else:
            return None, working_data

    def _is_recoverable_error(self, error: Exception) -> bool:
        """判断错误是否可恢复（即是否可以安全地填充 NaN）。
        
        可恢复的错误通常是数据层面的问题（如除零、空值），
        而不可恢复的错误是代码或配置问题（如参数错误、类型错误）。
        
        注意：Pydantic 验证错误属于参数错误，应抛出给 Agent 修正。
        """
        error_msg = str(error).lower()
        
        # Pydantic 验证错误 - 不可恢复，需要 Agent 修正参数
        if 'validation error' in error_msg or 'pydantic' in error_msg:
            return False
        
        # 可恢复的错误类型（数据层面）
        recoverable_patterns = [
            "division by zero",      # 除零
            "divide by zero",
            "zero division",
            "invalid value",         # 无效值（如 log(负数)）
            "nan encountered",       # NaN 传播
            "null value",            # 空值
            "no data available",     # 无数据
            "insufficient data",     # 数据不足
            "cannot compute",        # 无法计算
            "not enough",            # 数据不够
        ]
        
        return any(pattern in error_msg for pattern in recoverable_patterns)

    def _topological_sort_tools(
        self,
        tools: list[dict],
        existing_columns: list[str]
    ) -> list[dict]:
        """对工具列表进行拓扑排序，确保依赖的工具先执行.
        
        Args:
            tools: 工具步骤列表
            existing_columns: 已存在的列名（基础数据列）
            
        Returns:
            排序后的工具列表
        """
        
        # 构建依赖图
        dependencies = {}
        var_to_tool = {}  # var_name -> tool_step
        
        for tool_step in tools:
            var_name = tool_step.get("var")
            params = tool_step.get("params", {})
            if not var_name:
                continue
            
            # 提取 params 中引用的变量（column 参数）
            deps = set()
            for param_value in params.values():
                if isinstance(param_value, str):
                    # 检查是否是变量引用（不是基础列）
                    if param_value not in existing_columns and param_value != var_name:
                        deps.add(param_value)
            
            dependencies[var_name] = deps
            var_to_tool[var_name] = tool_step
        
        # Kahn's 算法进行拓扑排序
        in_degree = defaultdict(int)
        graph = defaultdict(list)  # dependency -> dependent vars
        
        for var, deps in dependencies.items():
            for dep in deps:
                if dep in dependencies:  # 只考虑其他工具生成的变量
                    graph[dep].append(var)
                    in_degree[var] += 1
            if var not in in_degree:
                in_degree[var] = 0
        
        # BFS
        queue = deque([var for var, degree in in_degree.items() if degree == 0])
        sorted_vars = []
        
        while queue:
            var = queue.popleft()
            sorted_vars.append(var)
            
            for dependent in graph[var]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        
        # 检测循环依赖
        if len(sorted_vars) != len(dependencies):
            missing = set(dependencies.keys()) - set(sorted_vars)
            logger.warning(f"   ⚠️ 检测到循环依赖或未解析的依赖：{missing}")
            # 将未排序的工具追加到末尾
            for var, tool_step in var_to_tool.items():
                if var not in sorted_vars:
                    sorted_vars.append(var)
        
        # 根据排序后的变量名重建工具列表
        sorted_tools = [var_to_tool[var] for var in sorted_vars if var in var_to_tool]
        
        if sorted_tools != tools:
            original_order = [t.get('var', '?') for t in tools]
            new_order = [t.get('var', '?') for t in sorted_tools]
            logger.info(f"   🔀 工具执行顺序调整：")
            logger.info(f"      原始：{' → '.join(original_order)}")
            logger.info(f"      排序：{' → '.join(new_order)}")
        
        return sorted_tools
