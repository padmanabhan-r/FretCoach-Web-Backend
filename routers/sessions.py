"""
Sessions API Router
Fetches practice session data from PostgreSQL
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from psycopg2.extras import RealDictCursor
from database import get_db_connection

router = APIRouter()


@router.get("/sessions")
async def get_sessions(
    user_id: str = Query(default="default_user"),
    limit: int = Query(default=10, ge=1, le=50),
    include_aggregates: bool = Query(default=True),
    start_date: Optional[str] = Query(default=None, description="Start date filter (ISO format)"),
    end_date: Optional[str] = Query(default=None, description="End date filter (ISO format)")
) -> Dict[str, Any]:
    """
    Fetch practice sessions from the database

    Args:
        user_id: User identifier
        limit: Number of sessions to fetch (1-50)
        include_aggregates: Include aggregate statistics
        start_date: Filter sessions from this date (ISO format, e.g. 2024-01-01)
        end_date: Filter sessions until this date (ISO format, e.g. 2024-01-07)
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Build date filter clause
            date_filter = ""
            params = [user_id]

            if start_date:
                date_filter += " AND start_timestamp >= %s"
                params.append(start_date)

            if end_date:
                # Add one day to include the end date fully
                date_filter += " AND start_timestamp < %s::date + interval '1 day'"
                params.append(end_date)

            # Fetch recent sessions
            cursor.execute(f"""
                SELECT
                    session_id, user_id, start_timestamp, end_timestamp,
                    pitch_accuracy, scale_conformity, timing_stability,
                    scale_chosen, scale_type, sensitivity, strictness,
                    total_notes_played, correct_notes_played, bad_notes_played,
                    total_inscale_notes, duration_seconds, ambient_light_option
                FROM fretcoach.sessions
                WHERE user_id = %s{date_filter}
                ORDER BY start_timestamp DESC
                LIMIT %s
            """, (*params, limit))

            sessions = cursor.fetchall()

            # Convert to list of dicts with proper serialization
            sessions_list = []
            for session in sessions:
                session_dict = dict(session)
                # Convert timestamps to ISO strings
                if session_dict.get('start_timestamp'):
                    session_dict['start_timestamp'] = session_dict['start_timestamp'].isoformat()
                if session_dict.get('end_timestamp'):
                    session_dict['end_timestamp'] = session_dict['end_timestamp'].isoformat()
                sessions_list.append(session_dict)

            aggregates = None
            if include_aggregates:
                # Fetch aggregates with same date filter
                cursor.execute(f"""
                    SELECT
                        COUNT(*) as total_sessions,
                        COALESCE(SUM(duration_seconds), 0) as total_practice_time,
                        COALESCE(AVG(pitch_accuracy), 0) as avg_pitch_accuracy,
                        COALESCE(AVG(scale_conformity), 0) as avg_scale_conformity,
                        COALESCE(AVG(timing_stability), 0) as avg_timing_stability,
                        COALESCE(SUM(total_notes_played), 0) as total_notes,
                        COALESCE(SUM(correct_notes_played), 0) as total_correct
                    FROM fretcoach.sessions
                    WHERE user_id = %s{date_filter}
                """, params)

                agg_row = cursor.fetchone()

                # Get unique scales practiced (within date range)
                cursor.execute(f"""
                    SELECT DISTINCT scale_chosen FROM fretcoach.sessions WHERE user_id = %s{date_filter}
                """, params)

                scales = [row['scale_chosen'] for row in cursor.fetchall() if row['scale_chosen']]

                aggregates = {
                    "total_sessions": int(agg_row['total_sessions'] or 0),
                    "total_practice_time": float(agg_row['total_practice_time'] or 0),
                    "avg_pitch_accuracy": float(agg_row['avg_pitch_accuracy'] or 0),
                    "avg_scale_conformity": float(agg_row['avg_scale_conformity'] or 0),
                    "avg_timing_stability": float(agg_row['avg_timing_stability'] or 0),
                    "total_notes": int(agg_row['total_notes'] or 0),
                    "total_correct": int(agg_row['total_correct'] or 0),
                    "scales_practiced": scales
                }

            cursor.close()

            return {
                "success": True,
                "sessions": sessions_list,
                "aggregates": aggregates,
                "dateRange": {
                    "start": start_date,
                    "end": end_date
                }
            }

    except Exception as e:
        print(f"[ERROR] Failed to fetch sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch sessions: {str(e)}")


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> Dict[str, Any]:
    """Fetch a single session by ID"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT * FROM fretcoach.sessions WHERE session_id = %s
            """, (session_id,))

            session = cursor.fetchone()
            cursor.close()

            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            session_dict = dict(session)
            if session_dict.get('start_timestamp'):
                session_dict['start_timestamp'] = session_dict['start_timestamp'].isoformat()
            if session_dict.get('end_timestamp'):
                session_dict['end_timestamp'] = session_dict['end_timestamp'].isoformat()

            return {"success": True, "session": session_dict}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch session: {str(e)}")
