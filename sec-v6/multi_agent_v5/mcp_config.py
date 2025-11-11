"""
MCP Tools Configuration and Helper Utilities

This module contains:
- MCP toolset configurations for collector and classifier services
- Helper functions for agent workflows
"""

from google.adk.tools import MCPToolset
from google.adk.tools.mcp_tool import SseConnectionParams


# MCP Tools Configuration for Data Collection Service
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

# MCP Tools Configuration for Classification Service
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
        "getClassifyLevelResult",
        "getFieldClassifyLevelDetail",
        "saveReviewedResult"
    ]
)

# MCP Tools Configuration for data mark
desensitize_mcp_tools = MCPToolset(
    connection_params=SseConnectionParams(
        url="http://172.16.22.18:8081/mcp/maskdata-service/sse",
        headers={
            'Accept': 'text/event-stream',
            'Cache-Control': 'no-cache',
        },
        timeout=50.0,
        sse_read_timeout=120.0,
    ),
    tool_filter=[
        "queryDatasourcesList",
        "createDBBatchTask",
        "executionMaskTask",
        "getBatchTaskResultDetailList"
    ]
)

# MCP Tools Configuration for provenance management Service
watermark_mcp_tools = MCPToolset(
    connection_params=SseConnectionParams(
        url="http://172.16.22.18:8081/mcp/provenance-management/sse",
        headers={
            'Accept': 'text/event-stream',
            'Cache-Control': 'no-cache',
        },
        timeout=50.0,
        sse_read_timeout=120.0,
    ),
    tool_filter=[
        "watermarkTracing",
        "getWatermarkInfo",
    ]
)

# Helper tool for background task processing
def wait_for_task_sync(seconds: int = 10) -> str:
    """Synchronous wait tool for background task processing
    
    Args:
        seconds: Number of seconds to wait
        
    Returns:
        Confirmation message
    """
    import time
    time.sleep(seconds)
    return f"Waited for {seconds} seconds"

