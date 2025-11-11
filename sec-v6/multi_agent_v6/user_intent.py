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
        分析用户请求并通过逐步推理对意图进行分类。

        **输出包含两个字段的 JSON：**
        1. "reasoning": 解释你的思考过程（2-3句话）
        2. "intent": 分类后的意图

        **意图类别：**
        - "collection_only": 仅数据采集
        - "classify_only": 仅分类分级（带审核）
        - "full_pipeline_with_review": 完整流程（采集 + 分类）带审核
        - "query_field_details": 查询特定表的字段级分类详情
        - "desensitize": 数据脱敏任务
        - "watermark_only": 数据水印溯源任务

        **决策逻辑：**
        1. 如果用户提到"字段" / "field" / "字段详情" / "field details" → "query_field_details"
        2. 如果用户提到"脱敏" / "desensitize" / "masking" / "数据脱敏" → "desensitize"
        3. 如果用户提到"溯源" / "水印" / "watermark" / "数据溯源" → "watermark_only"
        4. 如果用户只要求采集 → "collection_only"
        5. 如果用户只要求分类（没有先前的分类） → "classify_only"
        6. 如果用户要求采集和分类两者 → "full_pipeline_with_review"
        7. 审核完成后，如果用户询问表详情 → "query_field_details"

        **示例：**

        输入: "帮我采集数据"
        输出: {
          "reasoning": "用户明确提到数据采集，没有提及分类。这是一个仅采集的请求。",
          "intent": "collection_only"
        }

        输入: "对test_db进行分类分级"
        输出: {
          "reasoning": "用户要求对特定数据库进行分类分级。这需要分类并带审核。",
          "intent": "classify_only"
        }

        输入: "帮我采集并分类test_db数据库"
        输出: {
          "reasoning": "用户同时请求采集和分类。这需要完整的流程并带审核。",
          "intent": "full_pipeline_with_review"
        }

        输入: "我想知道表order的字段级别分类分级详情"
        输出: {
          "reasoning": "用户询问特定表（order）的字段级分类详情。这是字段详情查询，不是完整流程。",
          "intent": "query_field_details"
        }

        输入: "查询表user的字段详情"
        输出: {
          "reasoning": "用户明确要求查询表'user'的字段详情。这是对现有分类结果的字段级查询。",
          "intent": "query_field_details"
        }

        输入: "show me field details for table_users"
        输出: {
          "reasoning": "用户询问字段级详情。这是字段详情查询请求。",
          "intent": "query_field_details"
        }

        输入: "对表user进行数据脱敏"
        输出: {
          "reasoning": "用户明确请求对表进行数据脱敏。这是脱敏任务。",
          "intent": "desensitize"
        }

        输入: "帮我脱敏表order的数据"
        输出: {
          "reasoning": "用户要求对表'order'进行数据脱敏。这需要脱敏工作流程。",
          "intent": "desensitize"
        }

        输入: "对表user进行数据溯源"
        输出: {
          "reasoning": "用户要求对表'user'进行数据水印溯源。这需要水印溯源工作流程。",
          "intent": "watermark_only"
        }
        
        **重要提示**: 
        - "字段" / "field" 关键词 → 几乎总是 "query_field_details"
        - 分类完成后，关于特定表的查询 → "query_field_details"
        - 只有当同时请求采集和分类时才使用 "full_pipeline_with_review"

        仔细思考并仅输出有效的 JSON。
    """,
    output_schema=UserIntent,
    output_key="user_intent_obj",
)
