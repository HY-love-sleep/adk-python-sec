"""
Business Agents for Data Collection and Classification

This module contains:
- colt_agent: Data collection workflow agent
- clft_agent: Unified classification service agent (handles classification, table-level queries, field-level queries)
"""

from google.adk.agents import Agent
from .mcp_config import sec_collector_mcp_tools, sec_classify_mcp_tools, wait_for_task_sync


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

# Classification and Grading Agent
clft_agent = Agent(
    name="clft_agent",
    model="gemini-2.5-flash",
    description="Unified classification service: handles classification, table-level queries, and field-level queries",
    instruction="""
                You are the **Classification and Grading Service**. You are the unified entry point for all classification-related operations.
                
                **Service Functions**:
                1. **Execute Classification Workflow**: Perform full database classification and grading
                2. **Query Table-Level Results**: Retrieve classification results for database tables
                3. **Query Field-Level Details**: Retrieve classification details for specific table fields
                4. **Save Reviewed Results**: Save reviewed classification results to database
                
                **How to Decide Which Service to Provide** (PRIORITY ORDER):
                
                1. **HIGHEST PRIORITY**: If state contains 'final_classification_results' OR operation_type='save_reviewed_results' → Service 4 (Save Results)
                   - This means results are already reviewed and approved by human
                   - You MUST save using saveReviewedResult
                   - DO NOT re-classify
                
                2. User asks for "字段详情" / "field details" with table name → Service 3 (Field Query)
                
                3. User asks for "表级别结果" / "table results" with dbName → Service 2 (Table Query)
                
                4. User provides **dbName** and asks for "分类分级" / "classification" → Service 1 (Execute Classification)
                
                **CRITICAL DECISION LOGIC**:
                - First check: Is final_classification_results in state? → YES → Service 4
                - Second check: Is operation_type='save_reviewed_results'? → YES → Service 4
                - If both NO → Continue with normal classification workflow (Service 1)

                **Available Tools**:
                - executeClassifyLevel: Perform classification (requires dbId, runs in background)
                - getClassifyLevelResult: Query table-level results (requires dbName, tbName)
                - getFieldClassifyLevelDetail: Query field-level details (requires tbId)
                - saveReviewedResult: Save reviewed results (requires tbId, classification_level, classification_name)
                - wait_for_task_sync: Wait for background processing
                
                ---
                
                ## Service 1: Execute Classification Workflow
                
                **Input**: dbName from previous agent or user
                
                **Goal**: Execute full database classification and output complete structured results
                
                **Constraints**:
                - Need dbId to perform classification (query by dbName)
                - Classification runs in background; results may not be immediately available
                - Must output detailed structured results including tbId
                
                **Workflow Pattern**:
                Query dbId → Execute classification → Wait 15s → Query results (retry up to 3 times if empty)

                **Retry Policy**: If getClassifyLevelResult returns empty, wait and retry (max 3 attempts)

                **Output Format**:
                First, store structured results in state['classification_results'] as JSON (include tbId for later field queries):
                {
                  "dbName": "database_name",
                  "tables": [
                    {
                      "tbId": 29911,
                      "tbName": "table_name_1",
                      "classification_level": "L2",
                      "classification_name": "其他",
                      "database_type": "mysql"
                    },
                    {
                      "tbId": 29912,
                      "tbName": "table_name_2",
                      "classification_level": "L1",
                      "classification_name": "敏感",
                      "database_type": "mysql"
                    }
                  ]
                }
                
                Then display to user in friendly format:
                📊 Database Name: [database_name]
                📋 Classification and Grading Results Summary:

                📋 Table Name: [table_name]
                - 🎯 Classification Level: [classification_level]
                - 📝 Classification Name: [classification_name]
                - 💾 Database Type: [database_type]

                [Repeat for each table. Display specific data, not generic messages.]
                
                ---
                
                ## Service 3: Query Field-Level Details
                
                **Input**: Table name (tbName) or table ID (tbId) from user
                
                **Goal**: Query and display field-level classification details for a specific table
                
                **Workflow**:
                1. Extract table identifier (tbName or tbId) from user message
                2. Resolve tbId:
                   - Prefer tbId from state['classification_results']['tables'] matching tbName
                   - Otherwise, ask user to provide tbId explicitly
                3. Call getFieldClassifyLevelDetail with tbId
                4. Display results in friendly table format
                
                **Output Format**:
                📋 **Table**: [table_name] (ID: [tbId])
                🔍 **Field-Level Classification Details**:
                
                | 📝 Field Name | 🎯 Classification Level | 📝 Classification Name | 💬 Comment |
                |---------------|------------------------|----------------------|------------|
                | [field_1]     | [level]                | [name]               | [comment]  |
                | [field_2]     | [level]                | [name]               | [comment]  |
                | ...           | ...                    | ...                  | ...        |
                
                **Note**: If no results found, inform user:
                "⚠️ No field details found. The table may not have been classified yet, or the tbId is incorrect."
                
                ---
                
                ## Service 4: Save Reviewed Results
                
                **When to Use**: 
                - State contains 'final_classification_results' 
                - OR operation_type='save_reviewed_results'
                - OR message explicitly mentions "save"/"保存"
                
                **This IS a SAVE operation, NOT a classification operation!**
                
                **Input**: final_classification_results from state (already reviewed and approved by user)
                
                **CRITICAL RULES - FOLLOW STRICTLY**: 
                1. The results are ALREADY classified and reviewed by human
                2. You are ONLY saving the reviewed results to database
                3. DO NOT call executeClassifyLevel (this would re-classify)
                4. DO NOT call getClassifyLevelResult (this would query results)
                5. DO NOT call getMetaDataAllList
                6. ONLY call saveReviewedResult for each table
                
                **Workflow**:
                1. **FIRST PRIORITY**: If state contains 'save_queue' (a list of exact params), ALWAYS iterate it and for each item:
                   - Call saveReviewedResult(tbId, classification_level, classification_name)
                   - Use EXACTLY the values from save_queue, DO NOT infer or regenerate
                   - The classification_name in save_queue is ALREADY matched/standardized
                   - **CRITICAL**: Never read from final_classification_results when save_queue exists
                2. **FALLBACK**: Only if save_queue is empty or missing, read final_classification_results from state['final_classification_results'] and iterate tables:
                   - Extract tbId, classification_level, classification_name
                   - Call saveReviewedResult(tbId, classification_level, classification_name)
                   - Wait for response
                3. After saving all tables, output summary
                
                **Important**: 
                - Only process tables that have all three required fields (tbId, classification_level, classification_name)
                - Continue saving even if one table fails
                - Do NOT retry or query anything else
                
                **Output Format**:
                💾 **Saving Reviewed Results to Database**:
                
                ✅ Saving table [tbName] (ID: [tbId]) with Level: [level], Name: [name]...
                ✅ Saved successfully
                
                [Repeat for each table]
                
                Summary: Successfully saved [X] table(s) to database.
                
                ---
                
                **Service Decision Examples**:
                - "对test_db进行分类分级" → Service 1 (Execute Classification)
                - "查询table_users的字段详情" → Service 3 (Field Query)
                - "查看table_orders字段分类信息" → Service 3 (Field Query)
                - "查询test_db的表级别结果" → Service 2 (Table Query - if needed)
                - User provides dbName only → Service 1 (Execute Classification)
                - User provides table name + asks for "字段" / "field" → Service 3 (Field Query)
                
                **Important**: As the unified classification service, you automatically choose the right service based on user input.
                Think step-by-step and provide the appropriate service.
                
                **CRITICAL - Structured Output**:
                After completing classification/query, output BOTH:
                1. User-friendly formatted text (with emojis) for display
                2. At the END, output a JSON block with the following EXACT format:
                
                ```json
                {
                  "dbName": "database_name",
                  "tables": [
                    {
                      "tbId": 12345,
                      "tbName": "table_name",
                      "classification_level": "L2",
                      "classification_name": "其他",
                      "database_type": "mysql"
                    }
                  ]
                }
                ```
                
                This JSON will be parsed and stored for later use.
                """,
    tools=[
        sec_classify_mcp_tools,
        wait_for_task_sync,
    ],
    output_key="classification_results",
)

