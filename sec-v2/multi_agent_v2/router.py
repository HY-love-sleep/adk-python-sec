from typing import AsyncGenerator
from typing_extensions import override
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.agents import Agent

class RouterAgent(BaseAgent):
    """Deterministic routing: Choose the execution process based on intent"""

    intent_agent: Agent
    colt_workflow: BaseAgent
    clft_workflow: BaseAgent
    full_pipeline_workflow: BaseAgent

    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, name: str, intent_agent, colt_workflow, clft_workflow, full_pipeline_workflow):
        super().__init__(
            name=name,
            intent_agent=intent_agent,
            colt_workflow=colt_workflow,
            clft_workflow=clft_workflow,
            full_pipeline_workflow=full_pipeline_workflow,
            sub_agents=[intent_agent],
        )

    @override
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        async for event in self.intent_agent.run_async(ctx):
            yield event

        intent_obj = ctx.session.state.get("user_intent_obj", {})
        intent = intent_obj.get("intent", "full_pipeline")
        reasoning = intent_obj.get("reasoning", "")

        # from google.adk.events import Event as EventClass, EventActions
        # from google.genai.types import Content, Part
        # import time
        #
        # routing_msg = f"🎯 Intent Identified: {intent}\n💭 Reasoning: {reasoning}"
        # yield EventClass(
        #     author=self.name,
        #     content=Content(role="model", parts=[Part(text=routing_msg)]),
        #     timestamp=time.time(),
        # )

        if intent == "collection_only":
            selected = self.colt_workflow
        elif intent == "classify_only":
            selected = self.clft_workflow
        else:
            selected = self.full_pipeline_workflow

        # 3. run selected workflow
        async for event in selected.run_async(ctx):
            yield event