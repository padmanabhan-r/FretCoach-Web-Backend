"""
AI Practice Coach Chat Router - LangGraph Implementation
Uses LangGraph with dynamic SQL generation via tool calls
Maintains backward compatibility with existing frontend
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import json
import uuid
import re
from psycopg2.extras import RealDictCursor
from database import get_db_connection
from langgraph_workflow import invoke_workflow, OPIK_ENABLED

# Import Opik for tracking
try:
    from opik import track
except ImportError:
    def track(name=None, **kwargs):
        def decorator(func):
            return func
        return decorator

router = APIRouter()

# In-memory store for pending practice plans (per thread)
pending_plans: Dict[str, Dict[str, Any]] = {}


class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    user_id: str = "default_user"
    thread_id: Optional[str] = None


class SavePlanRequest(BaseModel):
    plan_id: str
    user_id: str = "default_user"


def extract_data_from_tool_results(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extract query results from tool call results.
    Looks for execute_sql_query tool calls and returns the data.
    """
    all_data = []

    for tool_call in tool_calls:
        tool_name = tool_call.get("tool", "")
        result = tool_call.get("result", "")

        if tool_name == "execute_sql_query" and isinstance(result, str):
            try:
                # Parse JSON result
                parsed = json.loads(result)
                if parsed.get("success") and parsed.get("data"):
                    data = parsed["data"]
                    all_data.extend(data)
            except Exception:
                pass

    return all_data


def extract_practice_plan_from_response(response: str, tool_calls: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Extract practice plan from LLM response or tool results.
    Returns practice plan data if found, None otherwise.
    """
    # Check tool calls for saved practice plans
    for tool_call in tool_calls:
        if tool_call.get("tool") == "save_practice_plan":
            result = tool_call.get("result", {})
            if result.get("success"):
                return {
                    "plan_id": result.get("practice_id"),
                    "saved": True
                }

    # Look for practice plan in response (JSON format)
    try:
        # Try to find JSON in the response
        json_match = re.search(r'\{[\s\S]*"exercises"[\s\S]*\}', response)
        if json_match:
            plan_json = json.loads(json_match.group(0))
            plan_id = str(uuid.uuid4())
            return {
                "plan_id": plan_id,
                "plan_json": plan_json,
                "saved": False
            }
    except:
        pass

    return None


def check_for_confirmation(message: str) -> bool:
    """Check if message contains confirmation words"""
    confirmation_words = ["yes", "yeah", "yep", "sure", "ok", "okay", "confirm", "save", "please"]
    return any(word in message.lower() for word in confirmation_words)


def save_practice_plan_to_db(plan_id: str, user_id: str, plan_json: Any) -> bool:
    """Save practice plan to database"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            plan_str = json.dumps(plan_json) if not isinstance(plan_json, str) else plan_json
            query = """
                INSERT INTO fretcoach.ai_practice_plans
                (practice_id, user_id, practice_plan, executed_session_id)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(query, [plan_id, user_id, plan_str, None])
            conn.commit()
            return True
    except Exception as e:
        print(f"[ERROR] Failed to save practice plan: {e}")
        return False


def get_quick_context(user_id: str) -> Dict[str, Any]:
    """
    Get quick context about user for response enrichment.
    This provides metadata without using tools (for efficiency).
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Get basic stats
            cursor.execute("""
                SELECT COUNT(*) as total_sessions,
                       COALESCE(AVG(pitch_accuracy), 0) as avg_pitch,
                       COALESCE(AVG(scale_conformity), 0) as avg_scale,
                       COALESCE(AVG(timing_stability), 0) as avg_timing
                FROM fretcoach.sessions WHERE user_id = %s
            """, [user_id])

            stats = cursor.fetchone()

            # Determine weakest area
            weakest_area = "pitch accuracy"
            min_score = stats['avg_pitch']
            if stats['avg_scale'] < min_score:
                weakest_area = "scale conformity"
                min_score = stats['avg_scale']
            if stats['avg_timing'] < min_score:
                weakest_area = "timing stability"

            return {
                "total_sessions": stats['total_sessions'],
                "weakest_area": weakest_area,
                "avg_pitch": round(stats['avg_pitch'], 1),
                "avg_scale": round(stats['avg_scale'], 1),
                "avg_timing": round(stats['avg_timing'], 1)
            }

    except Exception as e:
        print(f"[ERROR] Failed to get quick context: {e}")
        return {
            "total_sessions": 0,
            "weakest_area": "unknown",
            "avg_pitch": 0,
            "avg_scale": 0,
            "avg_timing": 0
        }


@track(name="ai_coach_chat_langgraph")
@router.post("/chat")
async def chat(request: ChatRequest) -> Dict[str, Any]:
    """
    AI Practice Coach chat endpoint using LangGraph.

    Processes user messages via LangGraph workflow with dynamic SQL generation.
    Maintains backward compatibility with frontend expectations.
    """
    # Set thread_id for conversation tracking
    thread_id = request.thread_id or f"chat-{request.user_id}"

    try:
        # Get quick context for response enrichment
        context = get_quick_context(request.user_id)

        # Get the last user message
        last_user_msg = request.messages[-1].content if request.messages else ""

        # Check if user is confirming a pending plan
        plan_saved = False
        if thread_id in pending_plans and check_for_confirmation(last_user_msg):
            pending = pending_plans[thread_id]
            if save_practice_plan_to_db(pending['plan_id'], request.user_id, pending['plan_json']):
                plan_saved = True
                del pending_plans[thread_id]

        # Convert messages to format expected by workflow
        workflow_messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]

        # Invoke LangGraph workflow with fallback handling
        use_fallback = False
        result = None

        try:
            result = invoke_workflow(
                messages=workflow_messages,
                user_id=request.user_id,
                thread_id=thread_id,
                use_fallback=False
            )
        except Exception as e:
            error_str = str(e).upper()
            if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str or "RATE" in error_str:
                result = invoke_workflow(
                    messages=workflow_messages,
                    user_id=request.user_id,
                    thread_id=thread_id,
                    use_fallback=True
                )
            else:
                raise

        if not result or not result.get("success"):
            raise HTTPException(status_code=500, detail="Workflow execution failed")

        # Extract response and tool results
        ai_content = result.get("response", "")

        # Ensure ai_content is a string
        if not isinstance(ai_content, str):
            ai_content = str(ai_content)

        tool_calls = result.get("tool_calls", [])

        # Extract data from query results
        query_data = extract_data_from_tool_results(tool_calls)

        # Generate chart based on user intent and data
        chart_data = None
        last_user_msg_lower = last_user_msg.lower()

        if query_data:
            # Check if user wants trend/progress visualization
            if any(word in last_user_msg_lower for word in ["progress", "trend", "over time", "chart", "graph", "visualize", "plot"]):
                from tools.plotting_tools import create_performance_trend_chart
                # Check if data has performance metrics
                if query_data and len(query_data) > 0:
                    first_row_keys = query_data[0].keys()
                    has_metrics = any(k in first_row_keys for k in ["pitch_accuracy", "scale_conformity", "timing_stability"])

                    if has_metrics:
                        chart_result = create_performance_trend_chart.invoke({
                            "sessions_data": query_data,
                            "metrics": ["pitch_accuracy", "scale_conformity", "timing_stability"]
                        })
                        chart_data = chart_result

            # Check if user wants comparison
            elif any(word in last_user_msg_lower for word in ["compare", "comparison", "versus", "vs", "latest"]):
                from tools.plotting_tools import create_comparison_chart
                # Try to create comparison if we have current and average data
                if len(query_data) >= 1:
                    current = query_data[0] if "pitch_accuracy" in query_data[0] else {}
                    avg_metrics = context
                    if current:
                        chart_result = create_comparison_chart.invoke({
                            "current_metrics": {
                                "pitch_accuracy": current.get("pitch_accuracy", 0),
                                "scale_conformity": current.get("scale_conformity", 0),
                                "timing_stability": current.get("timing_stability", 0)
                            },
                            "average_metrics": {
                                "pitch_accuracy": avg_metrics.get("avg_pitch", 0),
                                "scale_conformity": avg_metrics.get("avg_scale", 0),
                                "timing_stability": avg_metrics.get("avg_timing", 0)
                            }
                        })
                        chart_data = chart_result

        # Extract practice plan if present
        practice_plan = extract_practice_plan_from_response(ai_content, tool_calls)

        # Handle practice plan
        if practice_plan and not practice_plan.get("saved"):
            # Store as pending plan
            pending_plans[thread_id] = {
                "plan_id": practice_plan["plan_id"],
                "user_id": request.user_id,
                "plan_json": practice_plan.get("plan_json", {})
            }

            # Create chart data for practice plan
            if not chart_data:
                chart_data = {
                    "type": "practice_plan",
                    "data": practice_plan.get("plan_json", {}),
                    "plan_id": practice_plan["plan_id"]
                }

            ai_content += "\n\n*I've created a practice plan for you. Click 'Save Plan' to save it.*"

        elif practice_plan and practice_plan.get("saved"):
            plan_saved = True

        # Add chart context to response
        if chart_data and not plan_saved:
            chart_type = chart_data.get("type", "")
            if "trend" in chart_type.lower() or "line" in chart_type.lower():
                ai_content += "\n\n*I've displayed your performance trend chart below.*"
            elif "comparison" in chart_type.lower() or "bar" in chart_type.lower():
                ai_content += "\n\n*I've shown a comparison chart below.*"

        # If plan was saved, add confirmation
        if plan_saved:
            ai_content += "\n\n✅ *Your practice plan has been saved! You can access it anytime from your practice history.*"

        # Ensure content is a string before returning
        if not isinstance(ai_content, str):
            ai_content = str(ai_content)

        # Determine which model was used
        model_used = result.get("model_used", "Unknown")

        # Return response in expected format
        response_data = {
            "success": True,
            "message": {
                "role": "assistant",
                "content": ai_content
            },
            "chartData": chart_data,
            "planSaved": plan_saved,
            "hasPendingPlan": thread_id in pending_plans,
            "modelUsed": model_used,
            "sessionContext": {
                "total_sessions": context['total_sessions'],
                "weakest_area": context['weakest_area']
            }
        }

        # Verify message content is string
        if not isinstance(response_data["message"]["content"], str):
            response_data["message"]["content"] = str(response_data["message"]["content"])

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.post("/save-plan")
async def save_plan(request: SavePlanRequest) -> Dict[str, Any]:
    """
    Save a practice plan directly (via button click).
    Maintains backward compatibility with existing endpoint.
    """
    try:
        # Find the pending plan by plan_id across all threads
        plan_data = None
        thread_to_delete = None

        for thread_id, pending in pending_plans.items():
            if pending.get('plan_id') == request.plan_id:
                plan_data = pending
                thread_to_delete = thread_id
                break

        if not plan_data:
            raise HTTPException(status_code=404, detail="Practice plan not found or expired")

        # Save to database
        success = save_practice_plan_to_db(
            plan_data['plan_id'],
            request.user_id,
            plan_data['plan_json']
        )

        if success:
            # Remove from pending
            if thread_to_delete:
                del pending_plans[thread_to_delete]
            return {"success": True, "message": "Practice plan saved!"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save practice plan")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Save failed: {str(e)}")
