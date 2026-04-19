"""行业匹配工具 - 使用 LLM 智能匹配行业."""

from __future__ import annotations

import json
import re
from typing import Any

from infrastructure.logging.logger import get_logger

from langchain_core.messages import HumanMessage
logger = get_logger(__name__)


class IndustryMatcher:
    """行业匹配器 - 支持 LLM 智能匹配和简单模糊匹配."""
    
    def __init__(self, llm: Any):
        """初始化行业匹配器.
        
        Args:
            llm: LLM 实例
        """
        self.llm = llm
    
    def match_industries(self, target_industries: list[str], available_industries: list[str]) -> list[str]:
        """匹配行业（优先使用 LLM，失败时降级到简单匹配）.
        
        Args:
            target_industries: 用户输入的目标行业列表
            available_industries: 系统中可用的行业列表
            
        Returns:
            匹配到的行业列表
        """
        try:
            return self._llm_match(target_industries, available_industries)
        except Exception as e:
            logger.warning(f"⚠️ LLM 行业匹配失败：{e}，回退到简单匹配")
            return self._simple_match(target_industries, available_industries)
    
    def _llm_match(self, target_industries: list[str], available_industries: list[str]) -> list[str]:
        """使用 LLM 智能匹配行业.
        
        Args:
            target_industries: 用户输入的目标行业列表
            available_industries: 系统中可用的行业列表
            
        Returns:
            匹配到的行业列表
        """
        # 构建 prompt
        prompt = f"""你是一个行业分类专家。请帮助用户从可用行业列表中找出与用户输入最相关的行业。

**重要规则**：
1. **必须且只能**从下面的“可用行业列表”中选择行业，**绝对不能**自己创造行业名称
2. 返回的行业名称必须与可用行业列表中的名称**完全一致**（包括标点符号）
3. 每个输入关键词**至少**返回 1 个最相关的行业（即使相关性不高）
4. 按相关性从高到低排序，最相关的排在前面
5. 如果找不到相关度高的行业，也要返回相关度最高的那个

用户输入的行业关键词：
{json.dumps(target_industries, ensure_ascii=False, indent=2)}

可用行业列表（共 {len(available_industries)} 个，**只能从这里选择**）：
{json.dumps(available_industries, ensure_ascii=False, indent=2)}

匹配原则：
- 同义词或近义词：如“科技”→“计算机应用”、“电子设备”、“通信设备”
- 上下游产业链：如“新能源”→“光伏设备”、“电池”、“风电设备”
- 细分领域：如“医药”→“化学制药”、“中药”、“生物制品”
- 概念板块：如“人工智能”→“软件开发”、“IT服务”
- **注意**：即使语义相关，也必须从上面的可用行业列表中选择最接近的

请以 JSON 格式返回匹配结果：
{{
    "matched_industries": ["行业1", "行业2", ...],
    "reasoning": "简要说明匹配理由"
}}

**只返回 JSON，不要其他内容。**
**再次强调：返回的行业名称必须与可用行业列表中的名称完全一致！**"""
        
        # 调用 LLM
        response = self.llm.invoke([HumanMessage(content=prompt)])
        content = response.content if hasattr(response, 'content') else str(response)
        
        # 解析 JSON 响应
        json_match = re.search(r'\{[^}]*\}', content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            matched = result.get("matched_industries", [])
            reasoning = result.get("reasoning", "")
            
            # 验证匹配结果
            valid_matches = [ind for ind in matched if ind in available_industries]
            invalid_matches = [ind for ind in matched if ind not in available_industries]
            
            if invalid_matches:
                logger.warning(f"⚠️ LLM 返回了 {len(invalid_matches)} 个无效行业：{invalid_matches[:5]}")
                logger.info(f"📋 前10个可用行业：{available_industries[:10]}")
            
            if valid_matches:
                logger.info(f"🤖 LLM 行业匹配成功")
                logger.info(f"   匹配理由：{reasoning}")
                logger.info(f"   匹配数量：{len(valid_matches)} 个行业")
                return valid_matches
            else:
                logger.warning(f"⚠️ LLM 没有返回有效行业，回退到简单匹配")
                return self._simple_match(target_industries, available_industries)
        else:
            logger.warning(f"⚠️ LLM 响应无法解析为 JSON，回退到简单匹配")
            return self._simple_match(target_industries, available_industries)
    
    def _simple_match(self, target_industries: list[str], available_industries: list[str]) -> list[str]:
        """简单的字符串模糊匹配（作为 LLM 失败的降级方案）.
        
        Args:
            target_industries: 用户输入的目标行业列表
            available_industries: 系统中可用的行业列表
            
        Returns:
            匹配到的行业列表
        """
        matched_industries = []
        for target in target_industries:
            target_lower = target.lower().strip()
            matched = False
            
            # 策略1: 精确匹配
            if target in available_industries:
                matched_industries.append(target)
                logger.info(f"🔍 行业匹配（精确）：'{target}' → '{target}'")
                matched = True
                continue
            
            # 策略2: 双向包含检查
            if not matched:
                for industry in available_industries:
                    industry_lower = industry.lower()
                    if target_lower in industry_lower or industry_lower in target_lower:
                        matched_industries.append(industry)
                        logger.info(f"🔍 行业匹配（包含）：'{target}' → '{industry}'")
                        matched = True
                        break
            
            # 策略3: 分词匹配（将目标词拆分后匹配）
            if not matched and len(target) > 2:
                # 尝试匹配目标的子串
                for industry in available_industries:
                    industry_lower = industry.lower()
                    # 检查是否有共同的关键字（至少2个字符）
                    for i in range(len(target_lower) - 1):
                        for j in range(i + 2, min(len(target_lower) + 1, i + 5)):
                            substring = target_lower[i:j]
                            if substring in industry_lower:
                                matched_industries.append(industry)
                                logger.info(f"🔍 行业匹配（子串）：'{target}' → '{industry}' (匹配: '{substring}')")
                                matched = True
                                break
                        if matched:
                            break
                    if matched:
                        break
            
            # 策略4: 常见同义词映射
            if not matched:
                synonym_map = {
                    '芯片': ['半导体', '集成电路', '元件', '电子'],
                    '半导体': ['芯片', '集成电路', '元件'],
                    '新能源': ['光伏', '风电', '电池', '电力设备'],
                    '医药': ['制药', '生物', '医疗', '中药'],
                    '科技': ['计算机', '电子', '通信', '软件'],
                    'ai': ['人工智能', '软件', '计算机'],
                    '人工智能': ['ai', '软件', '计算机'],
                }
                for keyword, synonyms in synonym_map.items():
                    if keyword in target_lower or target_lower in keyword:
                        for synonym in synonyms:
                            for industry in available_industries:
                                if synonym in industry.lower():
                                    matched_industries.append(industry)
                                    logger.info(f"🔍 行业匹配（同义）：'{target}' → '{industry}' (通过: '{synonym}')")
                                    matched = True
                                    break
                            if matched:
                                break
                    if matched:
                        break
            
            if not matched:
                logger.warning(f"⚠️ 未找到匹配的行业：'{target}'，可用行业前20个：{available_industries[:20]}")
        
        return matched_industries
