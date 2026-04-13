"""SubAgent 抽象基类 - 统一智能体调用接口."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class BaseSubAgent(ABC):
    """子智能体抽象基类.
    
    提供统一的执行接口和异常处理，所有子智能体必须继承此类。
    
    使用示例：
        class ScreeningAgent(BaseSubAgent):
            def execute(self, input_data: dict) -> dict:
                # 实现筛选逻辑
                return {"stocks": [...]}
        
        agent = ScreeningAgent()
        result = agent.run({"query": "找出涨幅超过50%的股票"})
        # result = {
        #     "agent": "screening",
        #     "status": "success",
        #     "data": {"stocks": [...]},
        #     "execution_time": 1.23,
        # }
    """
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """执行子智能体任务（子类必须实现）.
        
        Args:
            input_data: 输入数据
            
        Returns:
            执行结果字典
        """
        pass
    
    def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """安全运行子智能体（统一包装器）.
        
        自动处理：
        - 异常捕获
        - 执行时间记录
        - 标准化返回格式
        
        Args:
            input_data: 输入数据
            
        Returns:
            标准化的结果字典：
            {
                "agent": str,              # 智能体名称
                "status": "success" | "failure",
                "data": Any | None,        # 成功时包含结果
                "error": str | None,       # 失败时包含错误信息
                "execution_time": float,   # 执行时间（秒）
            }
        """
        start_time = time.time()
        
        try:
            logger.debug(f"🤖 启动子智能体：{self.name}")
            
            # 调用子类实现的 execute 方法
            result = self.execute(input_data)
            
            execution_time = time.time() - start_time
            
            # 确保返回格式标准化
            if not isinstance(result, dict):
                result = {"result": result}
            
            result.setdefault("status", "success")
            
            logger.debug(f"✅ 子智能体 {self.name} 执行完成 ({execution_time:.2f}s)")
            
            return {
                "agent": self.name,
                "status": "success",
                "data": result,
                "error": None,
                "execution_time": execution_time,
            }
        
        except Exception as e:
            execution_time = time.time() - start_time
            
            logger.error(f"❌ 子智能体 {self.name} 执行失败：{e}", exc_info=True)
            
            return {
                "agent": self.name,
                "status": "failure",
                "data": None,
                "error": str(e),
                "execution_time": execution_time,
            }
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"


class AgentOrchestrator:
    """智能体编排器 - 协调多个子智能体执行.
    
    支持：
    - 顺序执行
    - 并行执行（未来扩展）
    - 依赖管理
    """
    
    def __init__(self):
        self.agents: list[BaseSubAgent] = []
    
    def register_agent(self, agent: BaseSubAgent):
        """注册子智能体."""
        self.agents.append(agent)
        logger.info(f"📝 注册子智能体：{agent.name}")
    
    def execute_sequential(self, input_data: dict[str, Any]) -> list[dict[str, Any]]:
        """顺序执行所有注册的子智能体.
        
        Args:
            input_data: 初始输入数据（会传递给每个智能体）
            
        Returns:
            所有智能体的执行结果列表
        """
        results = []
        
        for agent in self.agents:
            logger.info(f"▶️  执行子智能体：{agent.name}")
            result = agent.run(input_data)
            results.append(result)
            
            # 如果某个智能体失败，可以选择停止或继续
            if result["status"] == "failure":
                logger.warning(f"⚠️  子智能体 {agent.name} 失败，继续执行下一个")
        
        return results
    
    def execute_with_context(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """带上下文传递的顺序执行.
        
        前一个智能体的输出会作为后一个智能体的输入的一部分。
        
        Args:
            input_data: 初始输入数据
            
        Returns:
            最终的聚合结果
        """
        context = input_data.copy()
        all_results = []
        
        for agent in self.agents:
            # 将之前的结果添加到上下文中
            context["previous_results"] = all_results
            
            logger.info(f"▶️  执行子智能体：{agent.name} (上下文：{len(context)} 个键)")
            result = agent.run(context)
            all_results.append(result)
            
            # 如果成功，将结果合并到上下文
            if result["status"] == "success" and result["data"]:
                context[f"{agent.name}_result"] = result["data"]
            
            # 如果失败，可以选择停止
            if result["status"] == "failure":
                logger.error(f"🛑 子智能体 {agent.name} 失败，停止执行")
                break
        
        return {
            "results": all_results,
            "final_context": context,
            "total_agents": len(self.agents),
            "successful_agents": sum(1 for r in all_results if r["status"] == "success"),
        }
    
    def get_agent_names(self) -> list[str]:
        """获取所有注册的智能体名称."""
        return [agent.name for agent in self.agents]
    
    def clear_agents(self):
        """清空所有注册的智能体."""
        self.agents.clear()
        logger.info("🗑️  已清空所有子智能体")
