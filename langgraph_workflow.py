"""
LangGraph workflow for FretCoach AI Practice Coach
"""
import os
import json
from typing import TypedDict, Annotated, Sequence, Dict, Any, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from operator import add

# Try to import Opik for tracing
try:
    from opik.integrations.langchain import OpikTracer
    OPIK_ENABLED = True
except ImportError:
    OpikTracer = None
    OPIK_ENABLED = False

# Import LLM models
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic

# Import tools
from tools.database_tools import execute_sql_query, save_practice_plan, get_database_schema


# Define the state for the conversation
class AgentState(TypedDict):
    """State for the FretCoach AI agent"""
    messages: Annotated[Sequence[BaseMessage], add]
    user_id: str
    thread_id: Optional[str]
    next_action: Optional[str]


# Initialize LLM with fallback
def get_llm_with_tools(use_fallback: bool = False):
    """
    Get LLM instance with tools bound.

    Args:
        use_fallback: If True, use MiniMax (via Anthropic), else use Gemini

    Returns:
        LLM instance with tools bound
    """
    # Only include database tools - plotting will be handled by the router
    tools = [
        get_database_schema,
        execute_sql_query,
        save_practice_plan
    ]

    if use_fallback:
        # Use MiniMax via Anthropic wrapper
        llm = ChatAnthropic(
            model="MiniMax-M2.1",
            temperature=0.7,
            base_url=os.getenv("ANTHROPIC_BASE_URL")
        )
    else:
        # Use Gemini
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.7,
            convert_system_message_to_human=True
        )

    return llm.bind_tools(tools)


# System prompt for the AI coach
SYSTEM_PROMPT = """You are an expert AI guitar practice coach for FretCoach, a guitar learning platform that tracks practice sessions with real-time feedback.

Your role is to:
1. Analyze users' practice data and provide insights
2. Generate personalized practice plans based on performance
3. Answer questions about progress, trends, and improvement areas
4. Fetch and analyze session data from the database

Available Tools:
- get_database_schema: Get information about available database tables and columns
- execute_sql_query: Execute SELECT queries to fetch practice session data
- save_practice_plan: Save generated practice plans to database

IMPORTANT - Automatic Chart Generation:
When users ask to see their progress, trends, visualizations, or charts, the system will AUTOMATICALLY generate and display a visual chart below your response. You don't need to create the chart yourself - just query the data and describe the insights. The chart will appear automatically!

Database Information:
- fretcoach.sessions: Contains all practice session data with metrics (pitch_accuracy, scale_conformity, timing_stability)
- fretcoach.ai_practice_plans: Stores generated practice plans

CRITICAL Guidelines:
1. The user_id is provided to you in the system context - NEVER ask the user for it
2. Always filter queries by the provided user_id when accessing session data
3. Use tools to fetch data dynamically - never make assumptions about data
4. When users ask for progress/trends/charts, query the data and provide insights - the visual chart will appear automatically
5. When creating practice plans, structure them as JSON with exercises, durations, and goals
6. Provide actionable, encouraging feedback based on actual data
7. If you need to understand the schema, use get_database_schema tool first
8. Return actual numbers and insights from the queried data

Example queries (replace USER_ID with the actual user_id from context):
- "Show my progress" or "Visualize my progress" →
  Query: SELECT start_timestamp, pitch_accuracy, scale_conformity, timing_stability, scale_chosen
        FROM fretcoach.sessions WHERE user_id = 'USER_ID'
        ORDER BY start_timestamp DESC LIMIT 20
  Response: Describe the trends you see in the data. A chart will automatically appear!

- "What's my average pitch accuracy?" →
  SELECT AVG(pitch_accuracy) FROM fretcoach.sessions WHERE user_id = 'USER_ID'

- "What scales have I practiced?" →
  SELECT DISTINCT scale_chosen FROM fretcoach.sessions WHERE user_id = 'USER_ID'

Be conversational, encouraging, and data-driven in your responses. Trust that charts will appear automatically when appropriate!
"""


def create_agent_node(llm):
    """Create the agent node that processes messages and decides on tool calls"""

    def agent(state: AgentState) -> AgentState:
        messages = state["messages"]
        user_id = state["user_id"]

        # Add system prompt with user_id context if this is the first message
        if not any(isinstance(msg, SystemMessage) for msg in messages):
            system_prompt_with_context = f"""{SYSTEM_PROMPT}

CURRENT SESSION CONTEXT:
- user_id: {user_id}
- Always use this user_id ('{user_id}') in ALL SQL queries
- NEVER ask the user for their user_id - you already have it!

IMPORTANT WORKFLOW:
When users ask to "show", "visualize", "see", or "chart" their progress/trends:
1. ALWAYS use execute_sql_query to fetch their recent session data with metrics
2. Analyze the data and provide insights in your response
3. The system will AUTOMATICALLY generate and display a visual chart below your response
4. Simply end your response naturally - the chart will appear!

Example response format:
"Based on your last 10 sessions, I can see your pitch accuracy has improved from 75% to 85%! Your timing is also getting more consistent. [A performance trend chart will appear below automatically]" """
            system_message = SystemMessage(content=system_prompt_with_context)
            messages = [system_message] + list(messages)

        # Invoke the LLM
        response = llm.invoke(messages)

        return {
            "messages": [response],
            "user_id": user_id,
            "thread_id": state.get("thread_id"),
            "next_action": "tools" if response.tool_calls else "end"
        }

    return agent


def should_continue(state: AgentState) -> str:
    """Determine if we should continue to tools or end"""
    messages = state["messages"]
    last_message = messages[-1]

    # If there are tool calls, continue to tools
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    # Otherwise, end
    return "end"


def create_workflow():
    """Create the LangGraph workflow"""

    # Initialize with primary LLM (Gemini)
    llm = get_llm_with_tools(use_fallback=False)

    # Create the graph
    workflow = StateGraph(AgentState)

    # Create nodes
    agent_node = create_agent_node(llm)
    tool_node = ToolNode([
        get_database_schema,
        execute_sql_query,
        save_practice_plan
    ])

    # Add nodes to graph
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)

    # Set entry point
    workflow.set_entry_point("agent")

    # Add conditional edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )

    # Add edge from tools back to agent
    workflow.add_edge("tools", "agent")

    # Compile the graph
    return workflow.compile()


def create_workflow_with_fallback():
    """Create workflow with fallback LLM (MiniMax)"""

    llm = get_llm_with_tools(use_fallback=True)

    # Create the graph
    workflow = StateGraph(AgentState)

    # Create nodes
    agent_node = create_agent_node(llm)
    tool_node = ToolNode([
        get_database_schema,
        execute_sql_query,
        save_practice_plan
    ])

    # Add nodes to graph
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)

    # Set entry point
    workflow.set_entry_point("agent")

    # Add conditional edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )

    # Add edge from tools back to agent
    workflow.add_edge("tools", "agent")

    # Compile the graph
    return workflow.compile()


# Create compiled workflows
primary_workflow = create_workflow()
fallback_workflow = create_workflow_with_fallback()


def invoke_workflow(
    messages: list,
    user_id: str = "default_user",
    thread_id: Optional[str] = None,
    use_fallback: bool = False
) -> Dict[str, Any]:
    """
    Invoke the LangGraph workflow with Opik tracing.

    Args:
        messages: List of chat messages
        user_id: User identifier
        thread_id: Thread ID for conversation tracking
        use_fallback: Whether to use fallback LLM

    Returns:
        Dict with response and metadata
    """
    # Convert messages to LangChain format
    lc_messages = []
    for msg in messages:
        if msg.get("role") == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        elif msg.get("role") == "assistant":
            lc_messages.append(AIMessage(content=msg["content"]))
        elif msg.get("role") == "system":
            lc_messages.append(SystemMessage(content=msg["content"]))

    # Prepare initial state
    initial_state = {
        "messages": lc_messages,
        "user_id": user_id,
        "thread_id": thread_id,
        "next_action": None
    }

    # Configure Opik tracing if available
    config = {}
    if OPIK_ENABLED and OpikTracer:
        tracer = OpikTracer(
            project_name=os.getenv("OPIK_PROJECT_NAME", "FretCoach"),
            tags=["ai-coach", "langgraph", "practice-plan"],
            metadata={
                "user_id": user_id,
                "thread_id": thread_id or "no-thread",
                "model": "fallback" if use_fallback else "primary"
            }
        )
        config["callbacks"] = [tracer]

    if thread_id:
        config["configurable"] = {"thread_id": thread_id}

    # Select workflow
    workflow = fallback_workflow if use_fallback else primary_workflow

    # Invoke workflow
    try:
        result = workflow.invoke(initial_state, config=config)

        # Extract final message
        final_messages = result.get("messages", [])
        if final_messages:
            last_message = final_messages[-1]

            # Check if it's an AI message
            if isinstance(last_message, AIMessage):
                # Extract content - handle both string and list formats
                response_content = last_message.content

                # If content is a list (content blocks), extract text
                if isinstance(response_content, list):
                    text_parts = []
                    for block in response_content:
                        if isinstance(block, dict) and "text" in block:
                            text_parts.append(block["text"])
                        elif isinstance(block, str):
                            text_parts.append(block)
                    response_content = "".join(text_parts)

                # Ensure it's a string
                if not isinstance(response_content, str):
                    response_content = str(response_content)

                # Check for tool calls in the response
                tool_results = []
                for msg in reversed(final_messages):
                    if isinstance(msg, ToolMessage):
                        # Tool results are now strings (JSON or error messages)
                        tool_results.append({
                            "tool": msg.name,
                            "result": msg.content
                        })

                return {
                    "response": response_content,
                    "tool_calls": tool_results,
                    "success": True
                }

        return {
            "response": "I apologize, but I encountered an issue processing your request.",
            "success": False
        }

    except Exception as e:
        error_str = str(e).upper()
        # Raise exception for rate limit errors so caller can retry with fallback
        if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str or "RATE" in error_str:
            raise
        return {
            "response": f"An error occurred: {str(e)}",
            "success": False,
            "error": str(e)
        }
