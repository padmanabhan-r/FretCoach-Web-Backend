"""
AI Practice Coach Chat Router
Uses Google Gemini with Opik tracing
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
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Import Opik for tracking
try:
    from opik import track
    from opik.integrations.langchain import OpikTracer
    OPIK_ENABLED = True
except ImportError:
    def track(name=None, **kwargs):
        def decorator(func):
            return func
        return decorator
    OpikTracer = None
    OPIK_ENABLED = False

router = APIRouter()

# Initialize LLMs - Primary: Gemini, Fallback: MiniMax via Anthropic wrapper
gemini_model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)
minimax_model = ChatAnthropic(
    model="MiniMax-M2.1",
    temperature=0.7,
    base_url=os.environ.get("ANTHROPIC_BASE_URL")
)


def invoke_with_fallback(messages, thread_id: str = None):
    """Try Gemini first, fall back to MiniMax on rate limit errors. Uses OpikTracer for conversation tracking."""
    # Create OpikTracer with thread_id for conversation grouping
    callbacks = []
    if OPIK_ENABLED and OpikTracer:
        tracer = OpikTracer(
            tags=["ai-coach", "practice-plan"],
            metadata={"thread_id": thread_id} if thread_id else {}
        )
        callbacks = [tracer]

    config = {"callbacks": callbacks}
    if thread_id:
        config["configurable"] = {"thread_id": thread_id}

    try:
        return gemini_model.invoke(messages, config=config)
    except Exception as e:
        error_str = str(e).upper()
        if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str or "RATE" in error_str:
            print("[INFO] Gemini rate limited, falling back to MiniMax")
            return minimax_model.invoke(messages, config=config)
        raise

# In-memory store for pending practice plans (per thread)
# In production, you might use Redis or a database table
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


class ChartData(BaseModel):
    type: str
    data: Any
    metric: Optional[str] = None
    plan_id: Optional[str] = None  # For tracking pending plans


def get_user_practice_data(user_id: str) -> Dict[str, Any]:
    """Fetch user's practice data for context"""
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get aggregates
        cursor.execute("""
            SELECT
                COUNT(*) as total_sessions,
                COALESCE(AVG(pitch_accuracy), 0) as avg_pitch_accuracy,
                COALESCE(AVG(scale_conformity), 0) as avg_scale_conformity,
                COALESCE(AVG(timing_stability), 0) as avg_timing_stability,
                COALESCE(SUM(duration_seconds), 0) as total_practice_time
            FROM fretcoach.sessions WHERE user_id = %s
        """, (user_id,))
        agg = cursor.fetchone()

        # Get recent sessions
        cursor.execute("""
            SELECT session_id, start_timestamp, pitch_accuracy, scale_conformity,
                   timing_stability, scale_chosen, scale_type, duration_seconds
            FROM fretcoach.sessions WHERE user_id = %s
            ORDER BY start_timestamp DESC LIMIT 10
        """, (user_id,))
        recent = cursor.fetchall()

        # Get scales with performance
        cursor.execute("""
            SELECT scale_chosen, scale_type, COUNT(*) as count,
                   AVG(pitch_accuracy) as avg_pitch,
                   AVG(scale_conformity) as avg_scale,
                   AVG(timing_stability) as avg_timing
            FROM fretcoach.sessions WHERE user_id = %s
            GROUP BY scale_chosen, scale_type
            ORDER BY count DESC
        """, (user_id,))
        scales = cursor.fetchall()

        cursor.close()

    # Determine weakest area
    metrics = {
        "pitch": float(agg['avg_pitch_accuracy'] or 0),
        "scale": float(agg['avg_scale_conformity'] or 0),
        "timing": float(agg['avg_timing_stability'] or 0)
    }
    weakest = min(metrics, key=metrics.get) if agg['total_sessions'] > 0 else "pitch"

    return {
        "total_sessions": int(agg['total_sessions'] or 0),
        "avg_pitch_accuracy": metrics["pitch"],
        "avg_scale_conformity": metrics["scale"],
        "avg_timing_stability": metrics["timing"],
        "total_practice_time": float(agg['total_practice_time'] or 0),
        "recent_sessions": [dict(r) for r in recent],
        "practiced_scales": [dict(s) for s in scales],
        "weakest_area": weakest
    }


def get_performance_chart_data(user_id: str, metric: str = "all") -> Dict[str, Any]:
    """Generate chart data for performance trends"""
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT start_timestamp, pitch_accuracy, scale_conformity, timing_stability,
                   scale_chosen, duration_seconds
            FROM fretcoach.sessions WHERE user_id = %s
            ORDER BY start_timestamp DESC LIMIT 20
        """, (user_id,))

        rows = cursor.fetchall()
        cursor.close()

    # Reverse for chronological order
    rows = list(reversed(rows))

    chart_data = []
    for i, row in enumerate(rows):
        chart_data.append({
            "session": i + 1,
            "date": row['start_timestamp'].strftime("%m/%d") if row['start_timestamp'] else "",
            "pitch_accuracy": round((row['pitch_accuracy'] or 0) * 100),
            "scale_conformity": round((row['scale_conformity'] or 0) * 100),
            "timing_stability": round((row['timing_stability'] or 0) * 100),
            "scale": row['scale_chosen']
        })

    return {
        "type": "performance_trend",
        "data": chart_data,
        "metric": metric
    }


def get_comparison_chart_data(user_id: str, practice_data: Dict) -> Dict[str, Any]:
    """Generate comparison chart data (latest vs average)"""
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT pitch_accuracy, scale_conformity, timing_stability
            FROM fretcoach.sessions WHERE user_id = %s
            ORDER BY start_timestamp DESC LIMIT 1
        """, (user_id,))

        latest = cursor.fetchone()
        cursor.close()

    if not latest:
        return None

    return {
        "type": "comparison",
        "data": {
            "latest": {
                "pitch": round((latest['pitch_accuracy'] or 0) * 100),
                "scale": round((latest['scale_conformity'] or 0) * 100),
                "timing": round((latest['timing_stability'] or 0) * 100)
            },
            "average": {
                "pitch": round(practice_data['avg_pitch_accuracy'] * 100),
                "scale": round(practice_data['avg_scale_conformity'] * 100),
                "timing": round(practice_data['avg_timing_stability'] * 100)
            }
        }
    }


def extract_scale_from_message(message: str) -> tuple:
    """Extract scale name and type from user message"""
    message_lower = message.lower()

    # Scale types to detect
    scale_types = {
        "pentatonic": "pentatonic",
        "penta": "pentatonic",
        "blues": "blues",
        "natural": "natural",
        "harmonic": "harmonic",
        "melodic": "melodic",
        "major": "natural",
        "minor": "natural",
    }

    # Root notes
    roots = ["a", "b", "c", "d", "e", "f", "g"]
    sharps_flats = ["#", "sharp", "flat", "b"]

    detected_scale = None
    detected_type = "natural"

    # Check for pentatonic, blues, etc.
    for type_key, type_val in scale_types.items():
        if type_key in message_lower:
            detected_type = type_val
            break

    # Try to find scale name pattern (e.g., "A minor", "C major", "G# minor")
    # Match patterns like "A minor", "C# major", "Bb pentatonic"
    pattern = r'\b([a-g])[\s]*(#|sharp|flat|b)?[\s]*(minor|major|min|maj)?\b'
    match = re.search(pattern, message_lower)

    if match:
        root = match.group(1).upper()
        modifier = match.group(2)
        quality = match.group(3)

        if modifier in ['#', 'sharp']:
            root += '#'
        elif modifier in ['b', 'flat']:
            root += 'b'

        if quality in ['minor', 'min']:
            detected_scale = f"{root} Minor"
        elif quality in ['major', 'maj']:
            detected_scale = f"{root} Major"
        else:
            # Default to minor for pentatonic if not specified
            if detected_type == "pentatonic":
                detected_scale = f"{root} Minor"

    return detected_scale, detected_type


def generate_practice_recommendation(practice_data: Dict, user_id: str, thread_id: str, user_message: str = "") -> Dict[str, Any]:
    """Generate a practice recommendation based on user data and request"""
    weakest = practice_data['weakest_area']
    focus_names = {
        "pitch": "Pitch Accuracy",
        "scale": "Scale Conformity",
        "timing": "Timing Stability"
    }

    exercises = {
        "pitch": [
            "Practice slow scales focusing on hitting each note cleanly",
            "Use a tuner while practicing to get immediate feedback",
            "Work on sustaining notes and listening to their quality"
        ],
        "scale": [
            "Practice the scale patterns slowly before increasing speed",
            "Focus on one scale at a time until it becomes muscle memory",
            "Try playing the scale in different positions on the neck"
        ],
        "timing": [
            "Practice with a metronome starting at a slow tempo",
            "Focus on consistent note duration before speed",
            "Try rhythm exercises with varying note values"
        ]
    }

    # First, try to extract scale from user's message
    user_scale, user_scale_type = extract_scale_from_message(user_message)

    if user_scale:
        # User specified a scale - use it
        suggested_scale = user_scale
        suggested_scale_type = user_scale_type
    else:
        # Fall back to suggesting a scale that needs work
        scales = practice_data.get('practiced_scales', [])
        suggested_scale = "C Major"
        suggested_scale_type = "natural"
        if scales:
            for s in scales:
                if s.get('avg_pitch', 1) < 0.8:
                    suggested_scale = s['scale_chosen']
                    suggested_scale_type = s.get('scale_type', 'natural')
                    break

    score_key = f"avg_{weakest}_{'accuracy' if weakest == 'pitch' else 'conformity' if weakest == 'scale' else 'stability'}"

    # Generate a plan_id for this recommendation
    plan_id = str(uuid.uuid4())

    plan_data = {
        "focus_area": focus_names.get(weakest, weakest),
        "current_score": round(practice_data.get(score_key, practice_data['avg_pitch_accuracy']) * 100),
        "suggested_scale": suggested_scale,
        "suggested_scale_type": suggested_scale_type,
        "exercises": exercises.get(weakest, exercises['pitch']),
        "session_target": "20-30 minutes"
    }

    # Store the pending plan (with JSON format for DB, matching ai_agent_service format)
    from datetime import datetime as dt
    plan_json = {
        "scale_name": suggested_scale,
        "scale_type": suggested_scale_type,
        "focus_area": weakest,  # Use the key (pitch/scale/timing) not display name
        "reasoning": f"Based on your practice data, {focus_names.get(weakest, weakest)} needs the most work at {plan_data['current_score']}%.",
        "strictness": 0.5,  # Default moderate settings
        "sensitivity": 0.5,
        "generated_at": dt.now().isoformat(),
        "exercises": exercises.get(weakest, exercises['pitch'])
    }

    pending_plans[thread_id] = {
        "plan_id": plan_id,
        "user_id": user_id,
        "plan_data": plan_data,  # For frontend display
        "plan_json": plan_json   # For DB storage (JSON format)
    }

    return {
        "type": "practice_plan",
        "data": plan_data,
        "plan_id": plan_id
    }


def save_practice_plan_to_db(plan_id: str, user_id: str, plan_json: dict) -> bool:
    """Save a confirmed practice plan to the database as JSON (matching ai_agent_service format)"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            print(f"[INFO] Saving practice plan {plan_id} for user {user_id}")

            # Serialize to JSON string for storage
            plan_json_str = json.dumps(plan_json)

            cursor.execute("""
                INSERT INTO fretcoach.ai_practice_plans (practice_id, user_id, practice_plan, executed_session_id)
                VALUES (%s, %s, %s, %s)
            """, (plan_id, user_id, plan_json_str, "N/A - Generated from Web Practice Coach"))

            conn.commit()
            print(f"[INFO] Practice plan {plan_id} saved successfully")
            cursor.close()
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save practice plan: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_for_confirmation(message: str) -> bool:
    """Check if user message is confirming a practice plan"""
    confirm_phrases = [
        "yes", "save", "confirm", "ok", "okay", "sure", "sounds good",
        "looks good", "perfect", "great", "let's do it", "go ahead",
        "i like it", "save it", "save the plan", "confirmed", "accept"
    ]
    message_lower = message.lower().strip()
    return any(phrase in message_lower for phrase in confirm_phrases)


def build_system_prompt(practice_data: Dict, has_pending_plan: bool = False) -> str:
    """Build the system prompt with user's practice context"""
    recent_sessions_text = ""
    for s in practice_data.get('recent_sessions', [])[:5]:
        date = s['start_timestamp'].strftime("%m/%d") if s.get('start_timestamp') else "N/A"
        recent_sessions_text += f"- {date}: {s.get('scale_chosen', 'Unknown')} (Pitch: {round((s.get('pitch_accuracy') or 0) * 100)}%, Scale: {round((s.get('scale_conformity') or 0) * 100)}%, Timing: {round((s.get('timing_stability') or 0) * 100)}%)\n"

    if not recent_sessions_text:
        recent_sessions_text = "No sessions recorded yet"

    scales_text = ", ".join([s['scale_chosen'] for s in practice_data.get('practiced_scales', [])[:5]]) or "None yet"

    pending_plan_instruction = ""
    if has_pending_plan:
        pending_plan_instruction = """
7. IMPORTANT: There is a pending practice plan. If the user confirms (says yes, ok, save it, sounds good, etc.), acknowledge that the plan has been saved and encourage them to start practicing.
"""

    return f"""You are an AI guitar practice coach for FretCoach. You help users improve their guitar playing by analyzing their practice session data and providing personalized advice.

## User's Practice Data
- **Total sessions**: {practice_data['total_sessions']}
- **Average pitch accuracy**: {round(practice_data['avg_pitch_accuracy'] * 100)}%
- **Average scale conformity**: {round(practice_data['avg_scale_conformity'] * 100)}%
- **Average timing stability**: {round(practice_data['avg_timing_stability'] * 100)}%
- **Weakest area**: {practice_data['weakest_area']}
- **Scales practiced**: {scales_text}

## Recent Sessions
{recent_sessions_text}

## Instructions
1. Be encouraging and supportive while providing honest feedback
2. When the user asks about progress or trends, tell them you'll show a chart
3. When the user asks for practice recommendations, provide specific advice and ASK if they'd like to save this plan
4. Keep responses concise but helpful
5. Use markdown formatting for better readability
6. If asked to compare performance, analyze their latest session vs average{pending_plan_instruction}

## Response Format
- Use **bold** for emphasis
- Use bullet points for lists
- Use headers (##) for sections when appropriate
- Keep paragraphs short and readable"""


@track(name="ai_coach_chat")
@router.post("/chat")
async def chat(request: ChatRequest) -> Dict[str, Any]:
    """
    AI Practice Coach chat endpoint

    Processes user messages and returns AI responses with optional chart data
    """
    # Set thread_id for Opik conversation tracking
    thread_id = request.thread_id or f"chat-{request.user_id}"

    try:
        # Get user's practice data
        practice_data = get_user_practice_data(request.user_id)

        # Get the last user message for intent detection
        last_user_msg = request.messages[-1].content if request.messages else ""
        last_user_msg_lower = last_user_msg.lower()

        # Check if there's a pending plan and user is confirming
        plan_saved = False
        if thread_id in pending_plans and check_for_confirmation(last_user_msg):
            pending = pending_plans[thread_id]
            if save_practice_plan_to_db(pending['plan_id'], pending['user_id'], pending['plan_json']):
                plan_saved = True
                del pending_plans[thread_id]  # Clear the pending plan

        # Check if there's a pending plan for this thread
        has_pending_plan = thread_id in pending_plans

        # Build messages for LLM
        system_prompt = build_system_prompt(practice_data, has_pending_plan)
        messages = [SystemMessage(content=system_prompt)]

        for msg in request.messages:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            else:
                messages.append(AIMessage(content=msg.content))

        # Detect intent and prepare chart data
        chart_data = None

        if any(word in last_user_msg_lower for word in ["progress", "trend", "chart", "graph", "show me", "visualize", "how am i doing"]):
            chart_data = get_performance_chart_data(request.user_id)

        elif any(word in last_user_msg_lower for word in ["compare", "versus", "vs", "latest", "average", "comparison"]):
            chart_data = get_comparison_chart_data(request.user_id, practice_data)

        elif any(word in last_user_msg_lower for word in ["practice", "recommend", "suggest", "what should", "plan", "advice", "help me"]) and not plan_saved:
            chart_data = generate_practice_recommendation(practice_data, request.user_id, thread_id, last_user_msg)

        # Generate AI response (with automatic fallback and Opik tracing)
        response = invoke_with_fallback(messages, thread_id=thread_id)
        ai_content = response.content

        # Add chart context to response if chart is being shown
        if chart_data:
            if chart_data['type'] == 'performance_trend':
                ai_content += "\n\n*I've displayed your performance trend chart below.*"
            elif chart_data['type'] == 'comparison':
                ai_content += "\n\n*I've shown a comparison of your latest session vs your average below.*"
            elif chart_data['type'] == 'practice_plan':
                ai_content += "\n\n*I've created a practice plan for you below. Click 'Save Plan' to save it.*"

        # If plan was saved, add confirmation
        if plan_saved:
            ai_content += "\n\n✅ *Your practice plan has been saved! You can access it anytime from your practice history.*"

        return {
            "success": True,
            "message": {
                "role": "assistant",
                "content": ai_content
            },
            "chartData": chart_data,
            "planSaved": plan_saved,
            "hasPendingPlan": thread_id in pending_plans,
            "sessionContext": {
                "total_sessions": practice_data['total_sessions'],
                "weakest_area": practice_data['weakest_area']
            }
        }

    except Exception as e:
        print(f"[ERROR] Chat failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.post("/save-plan")
async def save_plan(request: SavePlanRequest) -> Dict[str, Any]:
    """
    Save a practice plan directly (via button click)
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

        # Save to database (as JSON, matching ai_agent_service format)
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
        print(f"[ERROR] Save plan failed: {e}")
        raise HTTPException(status_code=500, detail=f"Save failed: {str(e)}")
