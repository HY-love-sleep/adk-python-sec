"""
Workflow Orchestration with SequentialAgent

This module contains:
- full_pipeline_with_hitl: Complete workflow with human-in-the-loop review
"""

from google.adk.agents import SequentialAgent
from .business_agents import colt_agent, clft_agent
from .review_agents import review_prompt_agent, set_pending_review


# Full pipeline workflow: collection → classification → review prompt → set pending flag
full_pipeline_with_hitl = SequentialAgent(
    name="full_pipeline_with_hitl",
    description="Full pipeline: collection → classification → review prompt → set pending flag",
    sub_agents=[colt_agent, clft_agent, review_prompt_agent, set_pending_review],
)

