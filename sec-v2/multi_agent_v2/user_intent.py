from pydantic import BaseModel, Field
from google.adk.agents import LlmAgent

class UserIntent(BaseModel):
    reasoning: str = Field(
        description="Step-by-step reasoning process for intent classification"
    )
    intent: str = Field(
        description="User intent: 'collection_only', 'classify_only', or 'full_pipeline'"
    )

intent_agent = LlmAgent(
    name="intent_agent",
    model="gemini-2.5-flash",
    instruction="""
            Analyze user request and classify intent. 

            **Output a JSON with TWO fields:**
            1. "reasoning": Explain your thought process step-by-step (2-3 sentences, Use Chinese as much as possible)
            2. "intent": The classified intent

            **Intent Categories:**
            - "collection_only": Only data collection
            - "classify_only": Only classification/grading
            - "full_pipeline": Both or complete process

            **Examples:**

            Input: "帮我采集数据"
            Output: {
              "reasoning": "User specifically mentions '采集数据' (data collection) without mentioning classification or grading. This is a single-stage request.",
              "intent": "collection_only"
            }

            Input: "对数据库进行分类分级"
            Output: {
              "reasoning": "User asks for '分类分级' (classification and grading) only, with no mention of data collection. This targets the classification stage.",
              "intent": "classify_only"
            }

            Input: "帮我进行采集以及分类分级"
            Output: {
              "reasoning": "User explicitly requests both '采集' (collection) and '分类分级' (classification/grading) using '以及' (and). This requires the complete pipeline.",
              "intent": "full_pipeline"
            }

            Think carefully and output valid JSON only.
        """,
    output_schema=UserIntent,
    output_key="user_intent_obj",
)