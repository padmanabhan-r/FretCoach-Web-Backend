"""
LangGraph workflow for FretCoach AI Practice Coach
"""
import os
import json
from typing import TypedDict, Annotated, Sequence, Dict, Any, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from operator import add

# Import Opik for tracing
from opik.integrations.langchain import OpikTracer

# Import LLM models
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

# Import tools
from tools.database_tools import execute_sql_query, get_database_schema

# Initialize shared memory checkpointer for conversation persistence
checkpointer = MemorySaver()


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
        use_fallback: If True, use MiniMax (via Anthropic), else use primary model

    Returns:
        LLM instance with tools bound
    """
    # Only include database tools for querying - practice plan saving is handled by the frontend
    tools = [
        get_database_schema,
        execute_sql_query
    ]

    if use_fallback:
        # Use MiniMax via Anthropic wrapper
        llm = ChatAnthropic(
            model="MiniMax-M2.1",
            temperature=0.7,
            base_url=os.getenv("ANTHROPIC_BASE_URL")
        )
    else:
        # Use OpenAI or Gemini based on USE_OPENAI_MODEL flag
        use_openai = os.getenv("USE_OPENAI_MODEL", "").lower() == "true"

        if use_openai:
            # Use OpenAI with model from OPENAI_MODEL env var
            llm = ChatOpenAI(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                temperature=0.7
            )
        else:
            # Use Gemini (default)
            llm = ChatGoogleGenerativeAI(
                model=os.getenv("GEMINI_MODEL", "gemini-3-flash-preview"),
                temperature=0.7,
                convert_system_message_to_human=True
            )

    return llm.bind_tools(tools)


# Core system prompt (always included - minimal, ~150 tokens)
CORE_SYSTEM_PROMPT = """You are an AI guitar practice coach for FretCoach. Analyze practice data, provide insights, and generate personalized practice plans.

Tools available: get_database_schema, execute_sql_query

Key rules:
- User ID is {user_id} - always filter queries by this user_id
- Query data using SQL tools, provide data-driven insights
- Charts appear automatically when you query session metrics
- When generating practice plans, output JSON with: focus_area, current_score, suggested_scale, suggested_scale_type, session_target, exercises (array of strings)
- Remember user information shared in conversation"""

# Detailed guidelines (only sent on first message to save tokens)
DETAILED_GUIDELINES = """
DETAILED INSTRUCTIONS (Reference):

Database Schema:
- fretcoach.sessions: Practice session data (pitch_accuracy, scale_conformity, timing_stability, scale_chosen, start_timestamp, etc.)
- fretcoach.ai_practice_plans: Generated practice plans (JSON format)

Tool Usage:
- get_database_schema: View available tables and columns
- execute_sql_query: Run SELECT queries (read-only, automatically filtered for this user)

Practice Plan Generation:
- Generate practice plans as JSON in your response with this exact format:
  {
    "focus_area": "string (e.g., 'Pitch Accuracy', 'Timing Stability')",
    "current_score": number (0-100),
    "suggested_scale": "string (e.g., 'C minor', 'G major')",
    "suggested_scale_type": "string (e.g., 'natural minor', 'major')",
    "session_target": "string (e.g., '15-20 minutes')",
    "exercises": ["string", "string", ...] (array of exercise descriptions as strings)
  }
- The user will save the plan using a Save button on the UI

Workflow for Progress/Trends Requests:
1. Use execute_sql_query to fetch recent session data with metrics
2. Analyze trends and provide specific insights with numbers
3. Charts will auto-generate below your response - just describe the insights

Example Queries:
- Progress: SELECT start_timestamp, pitch_accuracy, scale_conformity, timing_stability FROM fretcoach.sessions WHERE user_id = '{user_id}' ORDER BY start_timestamp DESC LIMIT 20
- Averages: SELECT AVG(pitch_accuracy), AVG(timing_stability) FROM fretcoach.sessions WHERE user_id = '{user_id}'
- Scales practiced: SELECT DISTINCT scale_chosen FROM fretcoach.sessions WHERE user_id = '{user_id}'

Response Style:
- Conversational and encouraging
- Data-driven with specific numbers
- Actionable recommendations
- Remember user's name and preferences from conversation
"""


def create_agent_node(llm):
    """Create the agent node that processes messages and decides on tool calls"""

    def agent(state: AgentState) -> AgentState:
        messages = state["messages"]
        user_id = state["user_id"]

        # Check if this is the first turn by counting conversation messages
        # First turn: only 1 message (first user message)
        # Subsequent turns: 3+ messages (user, assistant, user, ...)
        conversation_messages = [m for m in messages if isinstance(m, (HumanMessage, AIMessage))]
        is_first_turn = len(conversation_messages) <= 1

        if is_first_turn:
            # First turn: Include CORE + DETAILED guidelines (full context, ~1150 tokens)
            system_prompt = CORE_SYSTEM_PROMPT.format(user_id=user_id) + "\n\n" + DETAILED_GUIDELINES.format(user_id=user_id)
        else:
            # Subsequent turns: Only CORE prompt (lightweight, ~150 tokens)
            # Saves ~1000 tokens per turn (60-70% reduction)
            system_prompt = CORE_SYSTEM_PROMPT.format(user_id=user_id)

        # Add system message to messages (only for LLM input, not persisted in state)
        system_message = SystemMessage(content=system_prompt)
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
        execute_sql_query
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

    # Compile the graph with memory checkpointer for conversation persistence
    return workflow.compile(checkpointer=checkpointer)


def create_workflow_with_fallback():
    """Create workflow with fallback LLM (MiniMax)"""

    llm = get_llm_with_tools(use_fallback=True)

    # Create the graph
    workflow = StateGraph(AgentState)

    # Create nodes
    agent_node = create_agent_node(llm)
    tool_node = ToolNode([
        get_database_schema,
        execute_sql_query
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

    # Compile the graph with memory checkpointer for conversation persistence
    return workflow.compile(checkpointer=checkpointer)


# Create compiled workflows
primary_workflow = create_workflow()
fallback_workflow = create_workflow_with_fallback()


def get_model_name(use_fallback: bool = False) -> str:
    """Get the model name being used"""
    if use_fallback:
        return "MiniMax-M2.1"
    else:
        use_openai = os.getenv("USE_OPENAI_MODEL", "").lower() == "true"
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini") if use_openai else os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")


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

    # With checkpointer enabled, only send new messages to avoid duplicates.
    # For continuing conversations (with thread_id), send only the last message (new user input).
    # For new conversations (first message), send all messages.
    if thread_id and len(lc_messages) > 1:
        # Get the workflow to check existing state
        workflow = fallback_workflow if use_fallback else primary_workflow
        try:
            # Check if this thread has existing state
            state = workflow.get_state(config={"configurable": {"thread_id": thread_id}})
            if state.values.get("messages"):
                # Thread exists, only send the last message (new user message)
                lc_messages = [lc_messages[-1]]
        except Exception:
            # Thread doesn't exist yet, send all messages
            pass

    # Prepare initial state
    initial_state = {
        "messages": lc_messages,
        "user_id": user_id,
        "thread_id": thread_id,
        "next_action": None
    }

    # Select workflow first so we can access its graph for Opik tracing
    workflow = fallback_workflow if use_fallback else primary_workflow

    # Get model name for tags and metadata
    model_name = get_model_name(use_fallback)

    # Base tags for all AI coach chat traces
    base_tags = [
        "fretcoach-hub",
        "ai-coach-chat",
        "from-hub-dashboard",
        "practice-plan",
        model_name
    ]

    # Configure Opik tracing
    tracer = OpikTracer(
        project_name=os.getenv("OPIK_PROJECT_NAME", "FretCoach"),
        tags=base_tags,
        metadata={
            "user_id": user_id,
            "model": model_name
        },
        graph=workflow.get_graph(xray=True)
    )
    config = {"callbacks": [tracer]}

    if thread_id:
        config["configurable"] = {"thread_id": thread_id}

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

                # Check if response contains a practice plan
                has_practice_plan = '"exercises"' in response_content and '{' in response_content

                return {
                    "response": response_content,
                    "tool_calls": tool_results,
                    "success": True,
                    "model_used": model_name,
                    "has_practice_plan": has_practice_plan
                }

        return {
            "response": "I apologize, but I encountered an issue processing your request.",
            "success": False
        }

    except Exception as e:
        error_str = str(e).upper()
        # Raise exception for rate limit errors so caller can retry with fallback
        if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str or "RATE" in error_str or "QUOTA" in error_str:
            print(f"[ERROR] Rate limit error detected in workflow: {str(e)[:200]}")
            raise  # Re-raise to trigger fallback in caller

        # For other errors, log and return error response
        print(f"[ERROR] Workflow error: {str(e)[:200]}")
        return {
            "response": f"An error occurred: {str(e)}",
            "success": False,
            "error": str(e)
        }
