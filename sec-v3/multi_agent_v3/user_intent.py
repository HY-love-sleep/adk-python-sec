from pydantic import BaseModel, Field
from google.adk.agents import Agent

class UserIntent(BaseModel):
    reasoning: str = Field(description="Reasoning process for intent classification")
    intent: str = Field(
        description="User intent: 'collection_only', 'classify_only', or 'full_pipeline_with_review'"
    )

intent_agent = Agent(
    name="intent_agent",
    model="gemini-2.0-flash",
    instruction="""
        Analyze user request and classify intent with step-by-step reasoning.
        
        **Output a JSON with TWO fields:**
        1. "reasoning": Explain your thought process (2-3 sentences)
        2. "intent": The classified intent
        
        **Intent Categories:**
        - "collection_only": Only data collection (采集)
        - "classify_only": Only classification/grading with review (分类分级+审核)
        - "full_pipeline_with_review": Full pipeline with review (采集+分类+审核)
        
        **Examples:**
        
        Input: "帮我采集数据"
        Output: {
          "reasoning": "User specifically mentions '采集数据' (data collection) without mentioning classification. This is a collection-only request.",
          "intent": "collection_only"
        }
        
        Input: "对test_db进行分类分级"
        Output: {
          "reasoning": "User asks for '分类分级' (classification and grading) on a specific database. This requires classification with review.",
          "intent": "classify_only"
        }
        
        Input: "帮我采集并分类test_db数据库"
        Output: {
          "reasoning": "User requests both '采集' (collection) and '分类' (classification). This requires the complete pipeline with review.",
          "intent": "full_pipeline_with_review"
        }
        
        Think carefully and output valid JSON only.
    """,
    output_schema=UserIntent,
    output_key="user_intent_obj",
)
