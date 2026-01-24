"""
Database tools for LangGraph agent to dynamically query FretCoach database
"""
import json
import uuid
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
from datetime import datetime
from psycopg2.extras import RealDictCursor
from database import get_db_connection


# Database schema information for the LLM
DATABASE_SCHEMA = """
Table: fretcoach.sessions
Columns:
  - session_id (VARCHAR, PRIMARY KEY): Unique session identifier
  - user_id (VARCHAR, PRIMARY KEY): User identifier
  - start_timestamp (TIMESTAMP): When session started
  - end_timestamp (TIMESTAMP): When session ended
  - pitch_accuracy (DOUBLE): Pitch accuracy score (0-100)
  - scale_conformity (DOUBLE): Scale conformity score (0-100)
  - timing_stability (DOUBLE): Timing stability score (0-100)
  - scale_chosen (VARCHAR): Name of the scale practiced
  - scale_type (VARCHAR): Type of scale (e.g., 'diatonic', 'pentatonic')
  - sensitivity (DOUBLE): Sensor sensitivity setting
  - strictness (DOUBLE): Scoring strictness setting
  - total_notes_played (INT): Total notes played in session
  - correct_notes_played (INT): Correct notes played
  - bad_notes_played (INT): Incorrect notes played
  - total_inscale_notes (INT): Total in-scale notes
  - duration_seconds (DOUBLE): Session duration in seconds
  - ambient_light_option (BOOLEAN): Whether ambient light was enabled
  - created_at (TIMESTAMP): Record creation timestamp

Table: fretcoach.ai_practice_plans
Columns:
  - practice_id (UUID, PRIMARY KEY): Unique plan identifier
  - user_id (VARCHAR): User identifier
  - generated_at (TIMESTAMP): When plan was generated
  - practice_plan (TEXT): The practice plan content (JSON format)
  - executed_session_id (VARCHAR): Session ID if plan was executed
  - created_at (TIMESTAMP): Record creation timestamp
"""


@tool
def get_database_schema() -> str:
    """
    Get the database schema information for fretcoach tables.
    Use this to understand what data is available before generating SQL queries.

    Returns:
        str: Database schema description including table names, columns, and data types
    """
    return DATABASE_SCHEMA


@tool
def execute_sql_query(query: str) -> str:
    """
    Execute a SQL SELECT query against the fretcoach database and return results.

    IMPORTANT RULES:
    - Only SELECT queries are allowed (no INSERT, UPDATE, DELETE, DROP, etc.)
    - Always filter by user_id when querying sessions table for user-specific data
    - Use table name prefix: fretcoach.sessions, fretcoach.ai_practice_plans
    - Query will be validated for security before execution

    Args:
        query (str): A complete SQL SELECT query to execute

    Returns:
        str: Query results as a formatted string, or error message if query failed

    Example:
        execute_sql_query(query="SELECT AVG(pitch_accuracy) as avg_pitch FROM fretcoach.sessions WHERE user_id = 'user123'")
    """
    # Security check: only allow SELECT queries
    query_upper = query.strip().upper()
    if not query_upper.startswith("SELECT"):
        return "Error: Only SELECT queries are allowed. No INSERT, UPDATE, DELETE, or DDL operations permitted."

    # Block dangerous SQL keywords
    dangerous_keywords = ["DROP", "TRUNCATE", "ALTER", "CREATE", "INSERT", "UPDATE", "DELETE", "GRANT", "REVOKE"]
    for keyword in dangerous_keywords:
        if keyword in query_upper:
            return f"Error: Query contains forbidden keyword: {keyword}"

    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Execute query
                cursor.execute(query)

                # Fetch all results
                results = cursor.fetchall()

                # Convert to list of dictionaries
                data = [dict(row) for row in results]

                # Convert datetime objects to ISO strings
                for row in data:
                    for key, value in row.items():
                        if isinstance(value, datetime):
                            row[key] = value.isoformat()

                # Return formatted results
                if len(data) == 0:
                    return "Query executed successfully. No results found."

                return json.dumps({"success": True, "data": data, "row_count": len(data)}, indent=2)

    except Exception as e:
        return f"Error executing query: {str(e)}"


@tool
def save_practice_plan(
    user_id: str,
    practice_plan: str,
    executed_session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Save a generated practice plan to the database.

    Args:
        user_id (str): User identifier
        practice_plan (str): The practice plan content (can be JSON string or text)
        executed_session_id (str, optional): Session ID if this plan is linked to a session

    Returns:
        Dict with:
            - success (bool): Whether save was successful
            - practice_id (str): UUID of the saved practice plan
            - error (str, optional): Error message if save failed
    """
    try:
        practice_id = str(uuid.uuid4())

        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                query = """
                    INSERT INTO fretcoach.ai_practice_plans
                    (practice_id, user_id, practice_plan, executed_session_id)
                    VALUES (%s, %s, %s, %s)
                """
                cursor.execute(query, [practice_id, user_id, practice_plan, executed_session_id])
                conn.commit()

        return {
            "success": True,
            "practice_id": practice_id,
            "message": "Practice plan saved successfully"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
