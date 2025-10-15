from __future__ import annotations

from google.adk.agents import Agent
from google.adk.agents import SequentialAgent
from google.adk.tools import MCPToolset
from google.adk.tools.mcp_tool import SseConnectionParams
from .user_intent import intent_agent
from .router import RouterAgent

# todo:try gemini-2.5-flash
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
        "getDbIdByName",
        "executeClassifyLevel",
        "getClassifyLevelResult"
    ]
)

# sync wait tool, temporary replacement for no Callback API
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
                # todo: human feedback
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

# Classification and Grading Agent
# todo: Here the position is temporarily set to 0, and then needs to be set to 4, and add field's classifyLevel result
clft_agent = Agent(
    name="clft_agent",
    model="gemini-2.5-flash",
    description="Handles business processes related to classification and grading services",
    instruction="""
                You are a classification and grading expert. Your goal: perform classification/grading on a database and display detailed results.

                **Input**: dbName from previous agent or user.

                **Goal**: Execute classification workflow and display complete results to user.

                **Constraints & Dependencies**:
                - Need dbId to perform classification (obtained by querying with dbName).
                - Classification task runs in background; results may not be immediately available.
                - Must display detailed results, not just "completed" message.

                **Available Tools**:
                - getDbId: Query to get dbId by dbName.
                - executeClassifyLevel: Perform classification (requires dbId, runs in background).
                - getClassifyLevelResult: Query results (set position=0, requires dbName and tbName).
                - wait_for_task_sync: Waits for background processing.

                **Typical Workflow Pattern** (for reference):
                Query dbId → Execute classification → Wait 15s → Query results (retry up to 3 times if empty)

                **Retry Policy**:
                - If getClassifyLevelResult returns empty, wait and retry (max 3 attempts).

                **Output Format**:
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
)

# A full-process agent, executed colt -> clft sequentially
full_pipeline_agent = SequentialAgent(
    name="full_pipeline_agent",
    description="Executes full pipeline: first data collection, then classification",
    sub_agents=[colt_agent, clft_agent],
)

# Instantiate RouterAgent as root_agent for adk web UI entry
root_agent = RouterAgent(
    name="root_agent",
    intent_agent=intent_agent,
    colt_workflow=colt_agent,
    clft_workflow=clft_agent,
    full_pipeline_workflow=full_pipeline_agent,
)