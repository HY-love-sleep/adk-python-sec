from typing import AsyncGenerator
from typing_extensions import override
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.agents import Agent

class RouterAgent(BaseAgent):
    """Intelligent router with Human-in-the-Loop support"""

    intent_agent: Agent
    colt_workflow: BaseAgent
    clft_workflow: BaseAgent
    desensitize_workflow: BaseAgent
    prov2_workflow: BaseAgent
    review_prompt_workflow: BaseAgent
    set_pending_review_workflow: BaseAgent
    full_pipeline_workflow: BaseAgent
    feedback_processor: BaseAgent

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        name: str,
        intent_agent,
        colt_workflow,
        clft_workflow,
        desensitize_workflow,
        prov2_workflow,
        review_prompt_workflow,
        set_pending_review_workflow,
        full_pipeline_workflow,
        feedback_processor,
    ):
        super().__init__(
            name=name,
            intent_agent=intent_agent,
            colt_workflow=colt_workflow,
            clft_workflow=clft_workflow,
            desensitize_workflow=desensitize_workflow,
            prov2_workflow=prov2_workflow,
            review_prompt_workflow=review_prompt_workflow,
            set_pending_review_workflow=set_pending_review_workflow,
            full_pipeline_workflow=full_pipeline_workflow,
            feedback_processor=feedback_processor,
            sub_agents=[intent_agent],
        )

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        from google.genai.types import Content, Part
        import time
        
        # in "pending human feedback" state?
        pending_review = ctx.session.state.get("pending_review", False)
        
        if pending_review:
            # Use semantic detection for field queries (not review feedback)
            user_msg = (ctx.session.state.get("latest_user_message", "") or "").strip().lower()
            from google.adk.events import EventActions
            
            # detect field query requests
            # todo: maybe user LLM to detect
            field_query_keywords = ["字段", "field", "详情", "detail"]
            is_field_query = any(kw in user_msg for kw in field_query_keywords)
            
            if is_field_query:
                # exit review mode and route to clft_agent for field query
                yield Event(
                    author=self.name,
                    content=Content(
                        role="model",
                        parts=[Part(text="🔍 检测到字段查询请求。退出审核模式并处理你的查询...")]
                    ),
                    actions=EventActions(state_delta={
                        "pending_review": False,
                        "modification_count": 0,
                    }),
                    timestamp=time.time(),
                )
                # route to clft_agent
                async for event in self.clft_workflow.run_async(ctx):
                    yield event
                return

            # check modification count to prevent infinite loops
            modification_count = ctx.session.state.get("modification_count", 0)
            max_modifications = 3
            
            if modification_count >= max_modifications:
                # force approval after max modifications
                yield Event(
                    author=self.name,
                    content=Content(
                        role="model",
                        parts=[Part(text=f"⚠️ 已达到最大修改次数限制（{max_modifications} 轮）。\n\n"
                                        f"🔒 自动批准当前结果以防止无限循环。\n\n"
                                        f"📊 请查看下方的最终结果。")]
                    ),
                    actions=EventActions(state_delta={
                        "pending_review": False,
                        "modification_count": 0,
                        "final_classification_results": ctx.session.state.get("classification_results")
                    }),
                    timestamp=time.time(),
                )
                return

            # Increment modification count using EventActions (ADK best practice)
            yield Event(
                author=self.name,
                content=Content(
                    role="model",
                    parts=[Part(text=f"🔄 正在处理第 {modification_count + 1} 轮修改...")]
                ),
                actions=EventActions(state_delta={
                    "modification_count": modification_count + 1
                }),
                timestamp=time.time(),
            )
            
            # directly process feedback, skip intent recognition
            async for event in self.feedback_processor.run_async(ctx):
                yield event
            
            # Note: modification_count reset is handled by FeedbackProcessorAgent
            # when review is completed (approved/rejected) via EventActions
            
            return

        # normal flow: identify intent
        async for event in self.intent_agent.run_async(ctx):
            yield event

        intent_obj = ctx.session.state.get("user_intent_obj", {})
        intent = intent_obj.get("intent", "full_pipeline_with_review")

        # route decision
        if intent == "collection_only":
            selected = self.colt_workflow
        elif intent == "query_field_details":
            selected = self.clft_workflow
        elif intent == "desensitize":
            selected = self.desensitize_workflow
        elif intent == "watermark_only":
            selected = self.prov2_workflow
        elif intent == "classify_only":
            # classification + review flow
            async for event in self.clft_workflow.run_async(ctx):
                yield event
            async for event in self.review_prompt_workflow.run_async(ctx):
                yield event
            # set pending_review flag
            async for event in self.set_pending_review_workflow.run_async(ctx):
                yield event
            return
        else:
            selected = self.full_pipeline_workflow

        async for event in selected.run_async(ctx):
            yield event
