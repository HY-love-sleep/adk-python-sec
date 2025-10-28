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

        prompt = """✅ Classification completed! Please review the results above.

                📝 **How to provide feedback:**
                
                - Type **'approved'** - if all results are correct
                
                - Type **'modified: <your changes>'** - if you want to modify any results
                  
                  **Example**: 
                  "modified: table_user should be L3 and classification name should be Information about the user, table_orders should be L2"
                
                - Type **'rejected: <reason>'** - if results are completely unacceptable
                  
                  **Example**: 
                  "rejected: Wrong database analyzed"
                
                💡 You can modify both **Classification Level** (L1/L2/L3/L4) and **Classification Name** for any table.
                
                Please respond with your review decision.
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
                parts=[Part(text="⏳ System is now awaiting your review feedback. Please respond with your decision.")]
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
    description="Interprets user feedback semantically and extracts intent",
    instruction="""
                You are a feedback interpreter. Understand user's review feedback and classify their intent.
                
                **Input**: User's natural language feedback (any format)
                
                **Output**: JSON with action type and details
                
                **Action Types**:
                1. **approved** - User accepts the results
                   - Examples: "approved", "OK", "looks good", "accept", "确认", "通过"
                
                2. **rejected** - User rejects the results
                   - Examples: "rejected: wrong data", "不对", "reject", "cancel"
                   - Extract rejection_reason if provided
                
                3. **modified** - User wants to modify specific results
                   - Examples: "table_users should be L3", "把table_users改成L3", "modify table_users to L3"
                   - Extract all modifications with table_name, new_level, and/or new_classification_name
                   - **IMPORTANT**: Preserve the FULL table name as mentioned by user (including prefixes like "table_")
                
                **Examples**:
                
                Input: "approved"
                Output: {
                  "action": "approved",
                  "modifications": []
                }
                
                Input: "looks good"
                Output: {
                  "action": "approved",
                  "modifications": []
                }
                
                Input: "rejected: wrong database"
                Output: {
                  "action": "rejected",
                  "rejection_reason": "wrong database",
                  "modifications": []
                }
                
                Input: "table_users should be L3 and classification name should be information about the user"
                Output: {
                  "action": "modified",
                  "modifications": [
                    {
                      "table_name": "table_users",
                      "new_level": "L3",
                      "new_classification_name": "information about the user"
                    }
                  ]
                }
                
                Input: "modified: table_users should be L3, table_orders should be L2"
                Output: {
                  "action": "modified",
                  "modifications": [
                    {"table_name": "table_users", "new_level": "L3"},
                    {"table_name": "table_orders", "new_level": "L2"}
                  ]
                }
                
                Input: "把 table_users 改成 L3"
                Output: {
                  "action": "modified",
                  "modifications": [
                    {"table_name": "table_users", "new_level": "L3"}
                  ]
                }
                
                Input: "table_user should be L3 and classification name should be information about the user"
                Output: {
                  "action": "modified",
                  "modifications": [
                    {
                      "table_name": "table_user",
                      "new_level": "L3",
                      "new_classification_name": "information about the user"
                    }
                  ]
                }
                
                **Important**: 
                - Understand user intent semantically, don't rely on keywords
                - Extract ALL modifications if action is "modified"
                - Handle various natural language formats (English and Chinese)
                - Be flexible: "OK", "好的", "确认" all mean "approved"
                - **Always preserve the COMPLETE table name** exactly as user mentions it
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
            # ✅ 不将 clft_agent 加入 sub_agents，因为它已经在 full_pipeline_with_hitl 中
            # 我们只是在这里调用它，不是让它成为子 Agent
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
                match_status_msg = f"\n🔍 **Category Matching**: {matched_count}/{total_tables} categories matched to standard categories.\n"

            yield Event(
                author=self.name,
                content=Content(
                    role="model",
                    parts=[Part(text=f"💾 Saving reviewed results to database...{match_status_msg}")]
                ),
                actions=EventActions(state_delta={
                    "final_classification_results": classification_results
                }),
                timestamp=time.time(),
            )

            async for event in self.clft_agent.run_async(ctx):
                yield event

            output_text = "✅✅ **Review Status**: Approved ✅✅\n\n"
            output_text += "📊 **Final Classification Results**:\n\n"

            tables = classification_results.get("tables", [])
            if tables:
                for table in tables:
                    output_text += f"📋 Table Name: {table.get('tbName', 'N/A')}\n"
                    output_text += f"- 🎯 Classification Level: {table.get('classification_level', 'N/A')}\n"

                    original_name = table.get("classification_name_original", "")
                    matched_name = table.get("classification_name", "")
                    match_status = table.get("match_status", "")
                    
                    if match_status == "matched" and original_name != matched_name:
                        confidence = table.get("match_confidence", 0.0)
                        output_text += f"- 📝 Classification Name: {matched_name} (原始: '{original_name}', 置信度: {confidence:.2f})\n"
                    elif match_status == "alias":
                        output_text += f"- 📝 Classification Name: {matched_name} (别名)\n"
                    elif match_status == "unmatched":
                        confidence = table.get("match_confidence", 0.0)
                        output_text += f"- 📝 Classification Name: {matched_name} (自定义类别，置信度: {confidence:.2f})\n"
                    elif match_status == "error":
                        output_text += f"- 📝 Classification Name: {matched_name} (匹配失败，使用原始类别)\n"
                    else:
                        output_text += f"- 📝 Classification Name: {matched_name}\n"
                    
                    output_text += f"- 💾 Database Type: {table.get('database_type', 'N/A')}\n\n"
            else:
                output_text += "⚠️ No classification results found.\n\n"

            output_text += f"💾 **Saved to Database**: {total_tables} table(s) saved successfully.\n\n"
            output_text += "✅ Review process completed successfully!\n"

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
            reason = interpretation.get("rejection_reason", "No reason provided")
            output_text = f"❌ **Review Status**: Rejected\n\n"
            output_text += f"💬 **Reason**: {reason}\n\n"
            output_text += "Review process has been cancelled.\n"

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
                            text="⚠️ Could not parse your modifications. Please specify table names and changes clearly.")]
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
                        applied_changes.append(f"Table '{matched_table}': Level {old_level} → {new_level}")

                    if new_name:
                        old_name = tables_dict[matched_table].get("classification_name", "")
                        tables_dict[matched_table]["classification_name"] = new_name
                        applied_changes.append(f"Table '{matched_table}': Name '{old_name}' → '{new_name}'")

            # Update state
            classification_results["tables"] = list(tables_dict.values())

            # Build output
            output_text = "✅ **Review Status**: Modified\n\n"
            output_text += "📊 **Updated Classification Results**:\n\n"

            tables = classification_results.get("tables", [])
            if tables:
                for table in tables:
                    output_text += f"📋 Table Name: {table.get('tbName', 'N/A')}\n"
                    output_text += f"- 🎯 Classification Level: {table.get('classification_level', 'N/A')}\n"
                    output_text += f"- 📝 Classification Name: {table.get('classification_name', 'N/A')}\n\n"
            else:
                output_text += "⚠️ No classification results found.\n\n"

            output_text += "🔄 **Changes Applied**:\n"
            if applied_changes:
                for change in applied_changes:
                    output_text += f"- {change}\n"
            else:
                output_text += "- No changes were applied (table names may not match)\n"

            output_text += "\n💡 **Continue Review**: You can continue reviewing or approve/reject.\n"

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
                        text="⚠️ Could not understand your feedback. Please try 'approved', 'rejected', or describe your modifications.")]
                ),
                timestamp=time.time(),
            )


# Instantiate the FeedbackProcessorAgent with LLM interpreter
feedback_processor_agent = FeedbackProcessorAgent(
    name="feedback_processor_agent",
    interpreter_agent=feedback_interpreter_agent,
    clft_agent=clft_agent
)
