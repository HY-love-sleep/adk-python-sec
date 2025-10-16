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
    review_prompt_workflow: Agent
    set_pending_review_workflow: BaseAgent  # Sets pending_review flag
    full_pipeline_workflow: BaseAgent
    feedback_processor: Agent  # Processes human feedback

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        name: str,
        intent_agent,
        colt_workflow,
        clft_workflow,
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
        
        # check if in "pending human feedback" state
        pending_review = ctx.session.state.get("pending_review", False)
        
        if pending_review:
            # check modification count to prevent infinite loops
            modification_count = ctx.session.state.get("modification_count", 0)
            max_modifications = 3
            
            if modification_count >= max_modifications:
                # force approval after max modifications
                from google.adk.events import EventActions
                
                yield Event(
                    author=self.name,
                    content=Content(
                        role="model",
                        parts=[Part(text=f"⚠️ Maximum modification limit reached ({max_modifications} rounds).\n\n"
                                        f"🔒 Auto-approving current results to prevent infinite loop.\n\n"
                                        f"📊 Please review the final results below.")]
                    ),
                    actions=EventActions(state_delta={
                        "pending_review": False,
                        "modification_count": 0,
                        "final_classification_results": ctx.session.state.get("classification_results")
                    }),
                    timestamp=time.time(),
                )
                return
            
            # increment modification count before processing
            ctx.session.state["modification_count"] = modification_count + 1
            
            # directly process feedback, skip intent recognition
            async for event in self.feedback_processor.run_async(ctx):
                yield event
            
            # if review is completed (approved/rejected), reset counter
            if not ctx.session.state.get("pending_review", False):
                ctx.session.state["modification_count"] = 0
            
            return

        # normal flow: identify intent
        async for event in self.intent_agent.run_async(ctx):
            yield event

        intent_obj = ctx.session.state.get("user_intent_obj", {})
        intent = intent_obj.get("intent", "full_pipeline_with_review")

        # route decision
        if intent == "collection_only":
            selected = self.colt_workflow
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
