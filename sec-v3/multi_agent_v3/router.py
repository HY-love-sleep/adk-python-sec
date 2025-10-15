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
            sub_agents=[intent_agent],  # Only include always-executed agents
        )

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        # 🔍 First check if we're in "pending human feedback" state
        pending_review = ctx.session.state.get("pending_review", False)
        
        if pending_review:
            # Directly process feedback, skip intent recognition
            async for event in self.feedback_processor.run_async(ctx):
                yield event
            return  # End after processing feedback

        # Normal flow: identify intent
        async for event in self.intent_agent.run_async(ctx):
            yield event

        intent_obj = ctx.session.state.get("user_intent_obj", {})
        intent = intent_obj.get("intent", "full_pipeline_with_review")

        # Route decision
        if intent == "collection_only":
            selected = self.colt_workflow
        elif intent == "classify_only":
            # Manually execute classification + review flow
            async for event in self.clft_workflow.run_async(ctx):
                yield event
            async for event in self.review_prompt_workflow.run_async(ctx):
                yield event
            # Set pending_review flag
            async for event in self.set_pending_review_workflow.run_async(ctx):
                yield event
            return  # End after setting flag
        else:  # full_pipeline_with_review
            selected = self.full_pipeline_workflow

        async for event in selected.run_async(ctx):
            yield event
