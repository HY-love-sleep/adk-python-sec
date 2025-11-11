"""
Review and Feedback Agents for Human-in-the-Loop (HITL)

This module contains:
- ReviewPromptAgent: Custom agent that prompts user for review
- SetPendingReviewAgent: Custom agent that sets pending_review flag
- FeedbackInterpretation: Pydantic models for feedback parsing
- feedback_interpreter_agent: LLM agent for semantic feedback understanding
- FeedbackProcessorAgent: Custom agent that applies feedback modifications
"""

from __future__ import annotations

from typing import AsyncGenerator, List, Optional, Literal
import time

from google.adk.agents import Agent, BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai.types import Content, Part
from pydantic import BaseModel, Field
from .business_agents import clft_agent
from .category_matcher import category_matcher


# Custom ReviewPromptAgent
class ReviewPromptAgent(BaseAgent):
    """Custom agent that prompts for review """

    model_config = {"arbitrary_types_allowed": True}

    async def _run_async_impl(
            self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Prompt user for review feedback"""

        prompt = """✅ 分类完成！请审核以上结果。

                📝 **如何提供反馈：**
                
                - 输入 **'approved'** 或 **'通过'** 或 **'确认'** - 如果所有结果都正确
                
                - 输入 **'modified: <你的修改>'** 或 **'修改: <你的修改>'** - 如果你想修改任何结果
                  
                  **示例**: 
                  "modified: table_user 应该是 L3，分类名称应该是用户信息，table_orders 应该是 L2"
                  或
                  "修改: table_user 改成 L3，分类名称改成用户信息"
                
                - 输入 **'rejected: <原因>'** 或 **'拒绝: <原因>'** - 如果结果完全不可接受
                  
                  **示例**: 
                  "rejected: 分析了错误的数据库"
                  或
                  "拒绝: 数据库不对"
                
                💡 你可以修改任何表的 **分类级别** (L1/L2/L3/L4) 和 **分类名称**。
                
                请输入你的审核决定。
                """

        yield Event(
            author=self.name,
            content=Content(role="model", parts=[Part(text=prompt)]),
            timestamp=time.time(),
        )

review_prompt_agent = ReviewPromptAgent(name="review_prompt_agent")


# Custom Agent: Sets pending_review flag to True
class SetPendingReviewAgent(BaseAgent):
    """Deterministic agent that sets the pending_review flag to True"""

    model_config = {"arbitrary_types_allowed": True}

    async def _run_async_impl(
            self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Set pending_review = True in state to signal awaiting human feedback"""
        yield Event(
            author=self.name,
            content=Content(
                role="model",
                parts=[Part(text="⏳ 系统正在等待你的审核反馈。请输入你的决定。")]
            ),
            actions=EventActions(state_delta={
                "pending_review": True,
                "modification_count": 0
            }),
            timestamp=time.time(),
        )

set_pending_review = SetPendingReviewAgent(name="set_pending_review")

# Pydantic Models
class TableModification(BaseModel):
    """Represents a modification request for a specific table"""
    table_name: str = Field(description="Name of the table to modify")
    new_level: Optional[str] = Field(default=None, description="New classification level (L1/L2/L3/L4)")
    new_classification_name: Optional[str] = Field(default=None, description="New classification name")

class FeedbackInterpretation(BaseModel):
    """Structured interpretation of user feedback"""
    action: Literal["approved", "rejected", "modified"] = Field(
        description="User's feedback action: 'approved' if accepting results, 'rejected' if rejecting, 'modified' if requesting changes"
    )
    rejection_reason: Optional[str] = Field(default=None,
                                            description="Reason for rejection (only if action is 'rejected')")
    modifications: List[TableModification] = Field(
        default=[],
        description="List of table modifications (only if action is 'modified')"
    )


# Feedback Interpreter Agent - Uses LLM to understand user feedback semantically
feedback_interpreter_agent = Agent(
    name="feedback_interpreter_agent",
    model="gemini-2.5-flash",
    description="语义化解释用户反馈并提取意图",
    instruction="""
                你是一个反馈解释器。理解用户的审核反馈并对其意图进行分类。
                
                **输入**：用户的自然语言反馈（任何格式）
                
                **输出**：包含操作类型和详情的 JSON
                
                **操作类型**：
                1. **approved** - 用户接受结果
                   - 示例："approved"、"OK"、"looks good"、"accept"、"确认"、"通过"、"好的"、"可以"
                
                2. **rejected** - 用户拒绝结果
                   - 示例："rejected: wrong data"、"不对"、"reject"、"cancel"、"拒绝"、"不行"
                   - 如果提供了拒绝原因，提取 rejection_reason
                
                3. **modified** - 用户想要修改特定结果
                   - 示例："table_users应该是L3"、"把table_users改成L3"、"modify table_users to L3"
                   - 提取所有修改，包括 table_name、new_level 和/或 new_classification_name
                   - **重要**：保留用户提到的完整表名（包括"table_"等前缀）
                
                **示例**：
                
                输入: "approved"
                输出: {
                  "action": "approved",
                  "modifications": []
                }
                
                输入: "看起来不错"
                输出: {
                  "action": "approved",
                  "modifications": []
                }
                
                输入: "rejected: 数据库错误"
                输出: {
                  "action": "rejected",
                  "rejection_reason": "数据库错误",
                  "modifications": []
                }
                
                输入: "table_users应该是L3，分类名称应该是用户信息"
                输出: {
                  "action": "modified",
                  "modifications": [
                    {
                      "table_name": "table_users",
                      "new_level": "L3",
                      "new_classification_name": "用户信息"
                    }
                  ]
                }
                
                输入: "modified: table_users应该是L3，table_orders应该是L2"
                输出: {
                  "action": "modified",
                  "modifications": [
                    {"table_name": "table_users", "new_level": "L3"},
                    {"table_name": "table_orders", "new_level": "L2"}
                  ]
                }
                
                输入: "把 table_users 改成 L3"
                输出: {
                  "action": "modified",
                  "modifications": [
                    {"table_name": "table_users", "new_level": "L3"}
                  ]
                }
                
                输入: "table_user应该是L3，分类名称应该是用户信息"
                输出: {
                  "action": "modified",
                  "modifications": [
                    {
                      "table_name": "table_user",
                      "new_level": "L3",
                      "new_classification_name": "用户信息"
                    }
                  ]
                }
                
                **重要提示**： 
                - 语义化理解用户意图，不要依赖关键词
                - 如果操作是"modified"，提取所有修改
                - 处理各种自然语言格式（英文和中文）
                - 灵活处理："OK"、"好的"、"确认"都表示"approved"
                - **始终保留用户提到的完整表名**
                """,
    output_schema=FeedbackInterpretation,
    output_key="feedback_interpretation",
)


# Custom Feedback Processor Agent - Applies LLM-interpreted feedback deterministically
class FeedbackProcessorAgent(BaseAgent):
    """Custom agent that processes feedback using LLM semantic understanding"""

    interpreter_agent: Agent
    clft_agent: Agent
    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, name: str, interpreter_agent: Agent, clft_agent: Agent):
        super().__init__(
            name=name,
            interpreter_agent=interpreter_agent,
            clft_agent=clft_agent,
            sub_agents=[interpreter_agent],
        )

    def _normalize_state_value(self, value, default=None):
        """Convert Pydantic object, JSON string, or text to dict"""
        if value is None:
            return default if default is not None else {}

        # convert to dict
        if hasattr(value, "model_dump"):
            return value.model_dump()

        if isinstance(value, dict):
            return value

        # parse as JSON
        if isinstance(value, str):
            import json
            import re
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except:
                pass

            # extract JSON from Markdown code block
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', value, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(1))
                    if isinstance(parsed, dict):
                        return parsed
                except:
                    pass

            # try to find JSON object in the text
            json_match = re.search(r'\{[^{}]*"tables"[^{}]*\[.*?\]\s*\}', value, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(0))
                    if isinstance(parsed, dict):
                        return parsed
                except:
                    pass

        return default if default is not None else {}

    async def _run_async_impl(
            self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Process user feedback using LLM semantic interpretation"""

        # use LLM to interpret user feedback semantically
        async for event in self.interpreter_agent.run_async(ctx):
            yield event

        # normalize LLM interpretation
        interpretation = self._normalize_state_value(
            ctx.session.state.get("feedback_interpretation")
        )

        action = interpretation.get("action", "")

        if action == "approved":
            # User approved - finalize results
            classification_results = self._normalize_state_value(
                ctx.session.state.get("classification_results")
            )
            
            if not classification_results:
                classification_results = {}

            # 对每个分类名称进行标准化匹配
            matched_count = 0
            for table in classification_results.get("tables", []):
                user_category = table.get("classification_name", "")
                # todo: user_category --> original_category
                if user_category:
                    matched_category, similarity, status = await category_matcher.find_best_match(user_category)

                    table["classification_name_original"] = user_category
                    table["classification_name"] = matched_category
                    table["match_confidence"] = similarity
                    table["match_status"] = status
                    
                    if status == "matched":
                        matched_count += 1

            total_tables = len(classification_results.get("tables", []))

            match_status_msg = ""
            if matched_count > 0:
                match_status_msg = f"\n🔍 **类别匹配**: {matched_count}/{total_tables} 个类别匹配到标准类别。\n"

            # 构造 save_queue
            save_queue = []
            debug_info = []
            
            for table in classification_results.get("tables", []):
                tbId = table.get("tbId")
                classification_level = table.get("classification_level")
                classification_name = table.get("classification_name")
                original_name = table.get("classification_name_original", classification_name)
                tbName = table.get("tbName", "N/A")
                
                if tbId and classification_level and classification_name:
                    save_queue.append({
                        "tbId": tbId,
                        "classification_level": classification_level,
                        "classification_name": classification_name,
                        "tbName": tbName
                    })

                    if original_name != classification_name:
                        debug_info.append(f"表 {tbName}: '{original_name}' → '{classification_name}'")

            debug_msg = ""
            if debug_info:
                debug_msg = "\n\n🔍 **匹配摘要**:\n" + "\n".join(debug_info)

            yield Event(
                author=self.name,
                content=Content(
                    role="model",
                    parts=[Part(text=f"💾 正在保存审核结果到数据库...{match_status_msg}{debug_msg}\n\n📝 **重要提示**：使用匹配的类别名称进行保存。\n")]
                ),
                actions=EventActions(state_delta={
                    "final_classification_results": classification_results,
                    "operation_type": "save_reviewed_results",
                    "save_queue": save_queue
                }),
                timestamp=time.time(),
            )

            yield Event(
                author=self.name,
                content=Content(
                    role="model",
                    parts=[Part(text="请帮我保存审批后的分类分级结果")]
                ),
                timestamp=time.time(),
            )

            async for event in self.clft_agent.run_async(ctx):
                yield event
            
            # 清除临时状态
            yield Event(
                author=self.name,
                content=Content(
                    role="model",
                    parts=[Part(text="")]
                ),
                actions=EventActions(state_delta={
                    "operation_type": None,
                    "save_queue": None
                }),
                timestamp=time.time(),
            )

            output_text = "✅✅ **审核状态**: 已批准 ✅✅\n\n"
            output_text += "📊 **最终分类结果**:\n\n"

            tables = classification_results.get("tables", [])
            if tables:
                for table in tables:
                    output_text += f"📋 表名: {table.get('tbName', 'N/A')}\n"
                    output_text += f"- 🎯 分类级别: {table.get('classification_level', 'N/A')}\n"

                    original_name = table.get("classification_name_original", "")
                    matched_name = table.get("classification_name", "")
                    match_status = table.get("match_status", "")
                    
                    if match_status == "matched" and original_name != matched_name:
                        confidence = table.get("match_confidence", 0.0)
                        output_text += f"- 📝 分类名称: {matched_name} (原始: '{original_name}', 置信度: {confidence:.2f})\n"
                    elif match_status == "alias":
                        output_text += f"- 📝 分类名称: {matched_name} (别名)\n"
                    elif match_status == "unmatched":
                        confidence = table.get("match_confidence", 0.0)
                        output_text += f"- 📝 分类名称: {matched_name} (自定义类别，置信度: {confidence:.2f})\n"
                    elif match_status == "error":
                        output_text += f"- 📝 分类名称: {matched_name} (匹配失败，使用原始类别)\n"
                    else:
                        output_text += f"- 📝 分类名称: {matched_name}\n"
                    
                    output_text += f"- 💾 数据库类型: {table.get('database_type', 'N/A')}\n\n"
            else:
                output_text += "⚠️ 未找到分类结果。\n\n"

            output_text += f"💾 **已保存到数据库**: 成功保存 {total_tables} 个表。\n\n"
            output_text += "✅ 审核流程成功完成！\n"

            yield Event(
                author=self.name,
                content=Content(role="model", parts=[Part(text=output_text)]),
                actions=EventActions(state_delta={
                    "pending_review": False,
                    "modification_count": 0,
                    "final_classification_results": classification_results
                }),
                timestamp=time.time(),
            )

        elif action == "rejected":
            reason = interpretation.get("rejection_reason", "未提供原因")
            output_text = f"❌ **审核状态**: 已拒绝\n\n"
            output_text += f"💬 **原因**: {reason}\n\n"
            output_text += "审核流程已取消。\n"

            yield Event(
                author=self.name,
                content=Content(role="model", parts=[Part(text=output_text)]),
                actions=EventActions(state_delta={
                    "pending_review": False,
                    "modification_count": 0,
                }),
                timestamp=time.time(),
            )

        elif action == "modified":
            modifications_list = interpretation.get("modifications", [])

            if not modifications_list:
                yield Event(
                    author=self.name,
                    content=Content(
                        role="model",
                        parts=[Part(
                            text="⚠️ 无法解析你的修改。请清楚地指定表名和更改内容。")]
                    ),
                    timestamp=time.time(),
                )
                return

            # Apply modifications deterministically
            # Get classification_results from state and normalize
            classification_results = self._normalize_state_value(
                ctx.session.state.get("classification_results")
            )
            
            if not classification_results:
                classification_results = {}

            tables_dict = {t.get("tbName"): t for t in classification_results.get("tables", [])}
            applied_changes = []

            for mod in modifications_list:
                table_name = mod.get("table_name")
                new_level = mod.get("new_level")
                new_name = mod.get("new_classification_name")

                # Try exact match first
                matched_table = None
                if table_name and table_name in tables_dict:
                    matched_table = table_name
                else:
                    # Try fuzzy match: check if table_name is part of any tbName or vice versa
                    for tb_name in tables_dict.keys():
                        if table_name and (
                                table_name.lower() in tb_name.lower() or tb_name.lower() in table_name.lower()):
                            matched_table = tb_name
                            break

                if matched_table:
                    if new_level:
                        old_level = tables_dict[matched_table].get("classification_level", "")
                        tables_dict[matched_table]["classification_level"] = new_level
                        applied_changes.append(f"表 '{matched_table}': 级别 {old_level} → {new_level}")

                    if new_name:
                        old_name = tables_dict[matched_table].get("classification_name", "")
                        tables_dict[matched_table]["classification_name"] = new_name
                        applied_changes.append(f"表 '{matched_table}': 名称 '{old_name}' → '{new_name}'")

            # Update state
            classification_results["tables"] = list(tables_dict.values())

            # Build output
            output_text = "✅ **审核状态**: 已修改\n\n"
            output_text += "📊 **更新后的分类结果**:\n\n"

            tables = classification_results.get("tables", [])
            if tables:
                for table in tables:
                    output_text += f"📋 表名: {table.get('tbName', 'N/A')}\n"
                    output_text += f"- 🎯 分类级别: {table.get('classification_level', 'N/A')}\n"
                    output_text += f"- 📝 分类名称: {table.get('classification_name', 'N/A')}\n\n"
            else:
                output_text += "⚠️ 未找到分类结果。\n\n"

            output_text += "🔄 **已应用的更改**:\n"
            if applied_changes:
                for change in applied_changes:
                    output_text += f"- {change}\n"
            else:
                output_text += "- 未应用任何更改（表名可能不匹配）\n"

            output_text += "\n💡 **继续审核**: 你可以继续审核或批准/拒绝。\n"

            yield Event(
                author=self.name,
                content=Content(role="model", parts=[Part(text=output_text)]),
                actions=EventActions(state_delta={
                    "classification_results": classification_results,
                    # Keep pending_review=True for continued review
                }),
                timestamp=time.time(),
            )
        else:
            # Unknown action
            yield Event(
                author=self.name,
                content=Content(
                    role="model",
                    parts=[Part(
                        text="⚠️ 无法理解你的反馈。请尝试输入 'approved'（通过）、'rejected'（拒绝）或描述你的修改。")]
                ),
                timestamp=time.time(),
            )


# Instantiate the FeedbackProcessorAgent with LLM interpreter
feedback_processor_agent = FeedbackProcessorAgent(
    name="feedback_processor_agent",
    interpreter_agent=feedback_interpreter_agent,
    clft_agent=clft_agent
)
