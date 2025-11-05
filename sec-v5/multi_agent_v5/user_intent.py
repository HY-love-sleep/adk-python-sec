from pydantic import BaseModel, Field
from google.adk.agents import Agent

class UserIntent(BaseModel):
    reasoning: str = Field(description="Reasoning process for intent classification")
    intent: str = Field(
        description="User intent: 'collection_only', 'classify_only', 'query_field_details', 'full_pipeline_with_review', or 'desensitize'"
    )


intent_agent = Agent(
    name="intent_agent",
    model="gemini-2.5-flash",
    instruction="""
        Analyze user request and classify intent with step-by-step reasoning.

        **Output a JSON with TWO fields:**
        1. "reasoning": Explain your thought process (2-3 sentences)
        2. "intent": The classified intent

        **Intent Categories:**
        - "collection_only": Only data collection
        - "classify_only": Only classification/grading with review
        - "full_pipeline_with_review": Full pipeline (collection + classification) with review
        - "query_field_details": Query field-level classification details for specific tables
        - "desensitize": Data masking/desensitization task

        **Decision Logic:**
        1. If user mentions "字段" / "field" / "字段详情" / "field details" → "query_field_details"
        2. If user mentions "脱敏" / "desensitize" / "masking" / "数据脱敏" → "desensitize"
        3. If user ONLY asks for collection → "collection_only"
        4. If user ONLY asks for classification (without prior classification) → "classify_only"
        5. If user asks for BOTH collection AND classification → "full_pipeline_with_review"
        6. After review is completed, if user asks about table details → "query_field_details"

        **Examples:**

        Input: "帮我采集数据"
        Output: {
          "reasoning": "User specifically mentions data collection without mentioning classification. This is a collection-only request.",
          "intent": "collection_only"
        }

        Input: "对test_db进行分类分级"
        Output: {
          "reasoning": "User asks for classification and grading on a specific database. This requires classification with review.",
          "intent": "classify_only"
        }

        Input: "帮我采集并分类test_db数据库"
        Output: {
          "reasoning": "User requests both collection and classification. This requires the complete pipeline with review.",
          "intent": "full_pipeline_with_review"
        }

        Input: "我想知道表order的字段级别分类分级详情"
        Output: {
          "reasoning": "User asks for field-level classification details for a specific table (order). This is a field detail query, not a full pipeline.",
          "intent": "query_field_details"
        }

        Input: "查询表user的字段详情"
        Output: {
          "reasoning": "User explicitly asks for field details of table 'user'. This is a query for existing classification results at field level.",
          "intent": "query_field_details"
        }

        Input: "show me field details for table_users"
        Output: {
          "reasoning": "User asks for field-level details. This is a field detail query request.",
          "intent": "query_field_details"
        }

        Input: "对表user进行数据脱敏"
        Output: {
          "reasoning": "User explicitly requests data masking/desensitization for a table. This is a desensitization task.",
          "intent": "desensitize"
        }

        Input: "帮我脱敏表order的数据"
        Output: {
          "reasoning": "User asks for data masking (脱敏) on table 'order'. This requires desensitization workflow.",
          "intent": "desensitize"
        }

        **IMPORTANT**: 
        - "字段" / "field" keywords → almost always "query_field_details"
        - After classification is done, queries about specific tables → "query_field_details"
        - Only use "full_pipeline_with_review" when BOTH collection AND classification are requested

        Think carefully and output valid JSON only.
    """,
    output_schema=UserIntent,
    output_key="user_intent_obj",
)
