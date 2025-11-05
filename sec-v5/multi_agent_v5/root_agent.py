"""
Root Agent Entry Point

This module instantiates and exports the root_agent for ADK Web UI.
All business logic, review workflows, and configurations are imported from separate modules.
"""

from .user_intent import intent_agent
from .router import RouterAgent
from .business_agents import colt_agent, clft_agent, desensitize_agent
from .review_agents import review_prompt_agent, set_pending_review, feedback_processor_agent
from .workflows import full_pipeline_with_hitl


root_agent = RouterAgent(
    name="root_agent",
    intent_agent=intent_agent,
    colt_workflow=colt_agent,
    clft_workflow=clft_agent,
    desensitize_workflow=desensitize_agent,
    review_prompt_workflow=review_prompt_agent,
    set_pending_review_workflow=set_pending_review,
    full_pipeline_workflow=full_pipeline_with_hitl,
    feedback_processor=feedback_processor_agent,
)

__all__ = ["root_agent"]
