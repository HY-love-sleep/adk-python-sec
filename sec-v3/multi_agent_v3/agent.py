from __future__ import annotations

from typing import AsyncGenerator
import time

from google.adk.agents import Agent, BaseAgent
from google.adk.agents import SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.adk.tools import MCPToolset
from google.adk.tools.mcp_tool import SseConnectionParams
from google.genai.types import Content, Part

from .user_intent import intent_agent
from .router import RouterAgent

# MCP Tools Configuration
sec_collector_mcp_tools = MCPToolset(
    connection_params=SseConnectionParams(
        url="http://172.16.22.18:8081/mcp/sec-collector-management/sse",
        headers={
            'Accept': 'text/event-stream',
            'Cache-Control': 'no-cache',
        },
        timeout=50.0,
        sse_read_timeout=120.0,
    ),
    tool_filter=[
        "addCollectionTask",
        "getPageOfCollectionTask",
        "openCollectionTask",
        "executeCollectionTask"
    ]
)

sec_classify_mcp_tools = MCPToolset(
    connection_params=SseConnectionParams(
        url="http://172.16.22.18:8081/mcp/sec-classify-level/sse",
        headers={
            'Accept': 'text/event-stream',
            'Cache-Control': 'no-cache',
        },
        timeout=50.0,
        sse_read_timeout=120.0,
    ),
    tool_filter=[
        "getMetaDataAllList",
        "executeClassifyLevel",
        "getClassifyLevelResult"
    ]
)


# Wait tool for background task processing
def wait_for_task_sync(seconds: int = 10) -> str:
    """Synchronous wait tool for background task processing"""
    import time
    time.sleep(seconds)
    return f"Waited for {seconds} seconds"


# Data Collection Agent
colt_agent = Agent(
    name="colt_agent",
    model="gemini-2.5-flash",
    description="Handles business processes related to data collection services",
    instruction="""
                You are a data collection expert. Your goal: complete a data collection task and return dbName.

                **Input**: User provides dataSourceId, dataSourceType, dataSourceName, databaseCodes.

                **Goal**: Execute a complete collection workflow and return the database name.

                **Constraints & Dependencies**:
                - A collection task must be added before it can be opened or executed.
                - You need a collectTaskId to start/execute a task (obtained from add operation response).
                - Background tasks take time to complete; wait appropriately (use wait_for_task_sync).

                **Available Tools**:
                - addCollectionTask: Creates a new task, returns collectTaskId in response.
                - openCollectionTask: Activates a task (requires collectTaskId).
                - executeCollectionTask: Runs the task (requires collectTaskId, runs in background).
                - wait_for_task_sync: Waits for background processing.

                **Typical Workflow Pattern** (for reference, not strict):
                Add task → Extract collectTaskId → Open task → Execute task → Wait → Return dbName

                **Output Format**: Return JSON {"dbName": "actual_database_name"}.

                Think step-by-step based on tool dependencies. Handle errors gracefully.
                """,
    tools=[
        sec_collector_mcp_tools,
        wait_for_task_sync,
    ],
)

# Classification and Grading Agent - Enhanced with structured output
clft_agent = Agent(
    name="clft_agent",
    model="gemini-2.5-flash",
    description="Handles classification and grading, outputs structured results with tbName",
    instruction="""
                You are a classification and grading expert. Your goal: perform classification/grading on a database and output detailed structured results.

                **Input**: dbName from previous agent or user.

                **Goal**: Execute classification workflow and output complete structured results.

                **Constraints & Dependencies**:
                - Need dbId to perform classification (obtained by querying with dbName).
                - Classification task runs in background; results may not be immediately available.
                - Must output detailed structured results including tbName for each table.

                **Available Tools**:
                - getMetaDataAllList: Query metadata to get dbId by dbName.
                - executeClassifyLevel: Perform classification (requires dbId, runs in background).
                - getClassifyLevelResult: Query results (set position=0, requires dbName and tbName).
                - wait_for_task_sync: Waits for background processing.

                **Typical Workflow Pattern** (for reference):
                Query dbId → Execute classification → Wait 15s → Query results (retry up to 3 times if empty)

                **Retry Policy**:
                - If getClassifyLevelResult returns empty, wait and retry (max 3 attempts).

                **CRITICAL - Output Format**:
                First, store structured results in state['classification_results'] as JSON:
                {
                  "dbName": "database_name",
                  "tables": [
                    {
                      "tbName": "table_name_1",
                      "classification_level": "L2",
                      "level_color": "#67C23A",
                      "classification_name": "其他",
                      "database_type": "mysql"
                    },
                    {
                      "tbName": "table_name_2",
                      "classification_level": "L1",
                      "level_color": "#F56C6C",
                      "classification_name": "敏感",
                      "database_type": "mysql"
                    }
                  ]
                }

                Then display to user in friendly format:
                📊 Database Name: [database_name]
                ️ Classification and Grading Results Summary:

                📋 Table Name: [table_name]
                - 🎯 Classification Level: [classification_level]
                - 🎨 Level Color: [color_code]
                - 📝 Classification Name: [classification_name]
                - 💾 Database Type: [database_type]

                Repeat for each table. Display specific data, not generic messages.
                """,
    tools=[
        sec_classify_mcp_tools,
        wait_for_task_sync,
    ],
    output_key="classification_results",
)

# Human Review Prompt Agent - Prompts user for feedback
review_prompt_agent = Agent(
    name="review_prompt_agent",
    model="gemini-2.5-flash",
    description="Prompts user to review classification results and provide feedback",
    instruction="""
                You are a review coordinator. Your task:
                
                1. Read state['classification_results'] (structured JSON with dbName and tables array)
                2. Mark the system as awaiting feedback by setting state['pending_review'] = True
                3. Output a clear, friendly prompt asking the user to review the classification results
                
                **Output Format**:
                
                "
                ✅ Classification completed! Please review the results above.
                
                📝 **How to provide feedback:**
                
                - Type **'approved'** - if all results are correct
                
                - Type **'modified: <your changes>'** - if you want to modify any results
                  
                  **Example**: 
                  "modified: table_users should be L3 and classification name should be 用户相关信息, table_orders should be L2"
                
                - Type **'rejected: <reason>'** - if results are completely unacceptable
                  
                  **Example**: 
                  "rejected: Wrong database analyzed"
                
                💡 You can modify both **Classification Level** (L1/L2/L3/L4) and **Classification Name** (分类名称) for any table.
                
                Please respond with your review decision.
                "
                
                **Important**: Your prompt will inform the user that the system is awaiting their feedback.
                """,
)

# Custom Agent: Sets pending_review flag to True
class SetPendingReviewAgent(BaseAgent):
    """Deterministic agent that sets the pending_review flag to True"""
    
    model_config = {"arbitrary_types_allowed": True}
    
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Set pending_review = True in state to signal awaiting human feedback"""
        yield Event(
            author=self.name,
            content=Content(
                role="model",
                parts=[Part(text="⏳ System is now awaiting your review feedback. Please respond with your decision.")]
            ),
            actions=EventActions(state_delta={"pending_review": True}),
            timestamp=time.time(),
        )

# Instantiate the SetPendingReviewAgent
set_pending_review = SetPendingReviewAgent(name="set_pending_review")

# Feedback Processor Agent - Processes user feedback and applies modifications
feedback_processor_agent = Agent(
    name="feedback_processor_agent",
    model="gemini-2.5-flash",
    description="Processes user feedback and applies modifications to classification results",
    instruction="""
                You are a feedback processor. Your task is to interpret user feedback and apply changes to classification results.
                
                **Inputs**:
                1. Read the LATEST USER MESSAGE as feedback
                2. Read state['classification_results'] (original structured JSON)
                
                **Process**:
                
                1. **Parse feedback status**:
                   - If message contains "approved" (case-insensitive) → status = "approved"
                   - If message starts with "modified:" → status = "modified"
                   - If message starts with "rejected:" → status = "rejected"
                
                2. **If status is "modified"**:
                   - Parse the user's modification requests carefully
                   - Extract table name, new classification level, and/or new classification name
                   
                   **Example parsing**:
                   Input: "modified: table_users should be L3 and classification name should be 用户相关信息, table_orders should be L2"
                   
                   Actions:
                   - Find "table_users" in state['classification_results']['tables']
                   - Set its classification_level to "L3"
                   - Set its classification_name to "用户相关信息"
                   - Find "table_orders" in state['classification_results']['tables']
                   - Set its classification_level to "L2"
                   
                   - Update level_color based on new level (L1:#F56C6C, L2:#67C23A, L3:#E6A23C, L4:#909399)
                
                3. **Store final results**:
                   - Save modified/original results to state['final_classification_results']
                   - Set state['pending_review'] = False to clear the review flag
                
                4. **Output to user**:
                
                "
                ✅ **Review Status**: [Approved/Modified/Rejected]
                💬 **Your Feedback**: [summary of user's feedback]
                
                📊 **Final Classification and Grading Results**:
                Database Name: [dbName]
                
                [For each table:]
                📋 Table Name: [tbName]
                - 🎯 Classification Level: [classification_level] [if modified: (Modified from [old_level])]
                - 🎨 Level Color: [level_color]
                - 📝 Classification Name: [classification_name] [if modified: (Modified from [old_name])]
                - 💾 Database Type: [database_type]
                
                [If any modifications were made:]
                🔄 **Changes Applied**:
                - [table_name]: Level [old] → [new], Name "[old]" → "[new]"
                "
                
                **Important**:
                - Be precise about what was changed
                - If approved, output original results with confirmation
                - If rejected, explain the rejection clearly
                - Always set state['pending_review'] = False when done
                """,
    output_key="final_classification_results",
)

# Sequential workflows
full_pipeline_with_hitl = SequentialAgent(
    name="full_pipeline_with_hitl",
    description="Full pipeline: collection → classification → review prompt → set pending flag",
    sub_agents=[colt_agent, clft_agent, review_prompt_agent, set_pending_review],
)

# classify_with_hitl = SequentialAgent(
#     name="classify_with_hitl",
#     description="Classification with human review",
#     sub_agents=[clft_agent, review_prompt_agent],
# )

# Instantiate RouterAgent as root_agent for adk web UI entry
root_agent = RouterAgent(
    name="root_agent",
    intent_agent=intent_agent,
    colt_workflow=colt_agent,
    clft_workflow=clft_agent,
    review_prompt_workflow=review_prompt_agent,
    set_pending_review_workflow=set_pending_review,
    full_pipeline_workflow=full_pipeline_with_hitl,
    feedback_processor=feedback_processor_agent,
)
