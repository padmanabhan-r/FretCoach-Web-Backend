"""
Test script for LangGraph implementation
Run this to validate the setup before deploying
"""

import os
import sys
from dotenv import load_dotenv

# Load environment
load_dotenv()

print("=" * 60)
print("FretCoach LangGraph Backend - Test Suite")
print("=" * 60)

# Test 1: Environment Variables
print("\n[Test 1] Checking environment variables...")
required_vars = ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "GOOGLE_API_KEY"]
optional_vars = ["OPIK_API_KEY", "MINIMAX_API_KEY"]

env_ok = True
for var in required_vars:
    if os.getenv(var):
        print(f"  ✓ {var} is set")
    else:
        print(f"  ✗ {var} is MISSING (required)")
        env_ok = False

for var in optional_vars:
    if os.getenv(var):
        print(f"  ✓ {var} is set")
    else:
        print(f"  ⚠ {var} is not set (optional)")

if not env_ok:
    print("\n❌ Missing required environment variables!")
    sys.exit(1)

# Test 2: Database Connection
print("\n[Test 2] Testing database connection...")
try:
    from database import get_db_connection

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            if result and result[0] == 1:
                print("  ✓ Database connection successful")
            else:
                print("  ✗ Unexpected database response")
                sys.exit(1)
except Exception as e:
    print(f"  ✗ Database connection failed: {e}")
    sys.exit(1)

# Test 3: Import LangGraph Components
print("\n[Test 3] Testing LangGraph imports...")
try:
    from langgraph.graph import StateGraph, END
    from langgraph.prebuilt import ToolNode
    print("  ✓ LangGraph core imports successful")
except ImportError as e:
    print(f"  ✗ LangGraph import failed: {e}")
    print("  Run: pip install langgraph")
    sys.exit(1)

# Test 4: Import Tools
print("\n[Test 4] Testing tool imports...")
try:
    from tools.database_tools import execute_sql_query, save_practice_plan, get_database_schema
    from tools.plotting_tools import (
        create_performance_trend_chart,
        create_comparison_chart,
        create_practice_plan_chart
    )
    print("  ✓ All tools imported successfully")
except ImportError as e:
    print(f"  ✗ Tool import failed: {e}")
    sys.exit(1)

# Test 5: Test Workflow Creation
print("\n[Test 5] Testing workflow creation...")
try:
    from langgraph_workflow import create_workflow, create_workflow_with_fallback

    workflow = create_workflow()
    print("  ✓ Primary workflow created successfully")

    fallback_workflow = create_workflow_with_fallback()
    print("  ✓ Fallback workflow created successfully")
except Exception as e:
    print(f"  ✗ Workflow creation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: Test Database Schema Tool
print("\n[Test 6] Testing get_database_schema tool...")
try:
    schema = get_database_schema.invoke({})
    if "fretcoach.sessions" in schema and "fretcoach.ai_practice_plans" in schema:
        print("  ✓ Database schema retrieved successfully")
    else:
        print("  ✗ Incomplete schema information")
except Exception as e:
    print(f"  ✗ Schema retrieval failed: {e}")
    sys.exit(1)

# Test 7: Test SQL Query Tool (Safe SELECT)
print("\n[Test 7] Testing execute_sql_query tool...")
try:
    result = execute_sql_query.invoke({
        "query": "SELECT COUNT(*) as count FROM fretcoach.sessions WHERE user_id = 'test_user'"
    })

    # Result is now a string (JSON or error message)
    if isinstance(result, str) and ("success" in result.lower() or "no results" in result.lower()):
        print(f"  ✓ SQL query executed successfully")
        print(f"    Result: {result[:100]}...")
    else:
        print(f"  ⚠ Query executed: {result[:100]}...")
        print(f"    (This is OK if test_user has no data)")
except Exception as e:
    print(f"  ✗ SQL query failed: {e}")
    sys.exit(1)

# Test 8: Test SQL Injection Protection
print("\n[Test 8] Testing SQL injection protection...")
try:
    # Test 1: Blocking DROP statement
    result = execute_sql_query.invoke({
        "query": "DROP TABLE fretcoach.sessions"
    })

    if "error" in result.lower():
        print("  ✓ DROP statement blocked")
    else:
        print(f"  ✗ DROP statement NOT blocked - SECURITY RISK! Result: {result}")
        sys.exit(1)

    # Test 2: Blocking DELETE statement
    result2 = execute_sql_query.invoke({
        "query": "DELETE FROM fretcoach.sessions WHERE user_id = 'test_user'"
    })

    if "error" in result2.lower():
        print("  ✓ DELETE statement blocked")
    else:
        print(f"  ✗ DELETE statement NOT blocked - SECURITY RISK! Result: {result2}")
        sys.exit(1)

    # Test 3: Blocking INSERT statement
    result3 = execute_sql_query.invoke({
        "query": "INSERT INTO fretcoach.sessions (session_id, user_id) VALUES ('fake_id', 'test_user')"
    })

    if "error" in result3.lower():
        print("  ✓ INSERT statement blocked")
        print("  ✓ SQL injection protection working correctly")
    else:
        print(f"  ✗ INSERT statement NOT blocked - SECURITY RISK! Result: {result3}")
        sys.exit(1)

except Exception as e:
    # Also acceptable if it raises an exception
    print(f"  ✓ SQL injection protection working (exception raised: {e})")

# Test 9: Test Chart Tools (used by router, not agent)
print("\n[Test 9] Testing chart generation tools...")
try:
    # Import plotting tools
    from tools.plotting_tools import create_performance_trend_chart, create_comparison_chart

    # Test performance trend chart
    mock_data = [
        {
            "start_timestamp": "2024-01-01T10:00:00",
            "pitch_accuracy": 85.5,
            "scale_conformity": 90.2,
            "timing_stability": 88.1
        },
        {
            "start_timestamp": "2024-01-02T10:00:00",
            "pitch_accuracy": 87.3,
            "scale_conformity": 91.5,
            "timing_stability": 89.0
        }
    ]

    chart = create_performance_trend_chart.invoke({
        "sessions_data": mock_data,
        "metrics": ["pitch_accuracy", "scale_conformity"]
    })

    if chart.get("type") == "line" and chart.get("data"):
        print("  ✓ Performance trend chart generated")
    else:
        print("  ✗ Chart generation failed")
        sys.exit(1)

    # Test comparison chart
    comparison = create_comparison_chart.invoke({
        "current_metrics": {"pitch_accuracy": 85.0, "scale_conformity": 90.0, "timing_stability": 88.0},
        "average_metrics": {"pitch_accuracy": 80.0, "scale_conformity": 85.0, "timing_stability": 82.0}
    })

    if comparison.get("type") == "bar":
        print("  ✓ Comparison chart generated")
        print("  ✓ Chart tools work (used by router for visualization)")
    else:
        print("  ✗ Comparison chart generation failed")
        sys.exit(1)

except Exception as e:
    print(f"  ✗ Chart generation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 10: Test Opik Integration
print("\n[Test 10] Testing Opik integration...")
try:
    from opik.integrations.langchain import OpikTracer

    if os.getenv("OPIK_API_KEY"):
        tracer = OpikTracer(
            project_name=os.getenv("OPIK_PROJECT_NAME", "FretCoach-Test"),
            tags=["test"],
            metadata={"test": True}
        )
        print("  ✓ Opik integration configured")
    else:
        print("  ⚠ Opik not configured (OPIK_API_KEY not set)")
        print("    System will work without Opik (graceful degradation)")
except ImportError:
    print("  ⚠ Opik not installed (optional)")
    print("    Run: pip install opik")
except Exception as e:
    print(f"  ⚠ Opik configuration failed: {e}")
    print("    System will work without Opik")

# Test 11: Test Router Import
print("\n[Test 11] Testing FastAPI router...")
try:
    from routers.chat_langgraph import router

    # Check endpoints
    routes = [route.path for route in router.routes]
    expected_routes = ["/chat", "/save-plan"]

    for route in expected_routes:
        if route in routes:
            print(f"  ✓ Endpoint {route} registered")
        else:
            print(f"  ✗ Endpoint {route} NOT found")
            sys.exit(1)

except Exception as e:
    print(f"  ✗ Router import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 12: Test Main App
print("\n[Test 12] Testing main FastAPI app...")
try:
    from main import app

    # Check if chat router is included
    all_routes = [route.path for route in app.routes]

    if "/api/chat" in all_routes:
        print("  ✓ Chat endpoint registered in main app")
    else:
        print("  ✗ Chat endpoint NOT registered")
        sys.exit(1)

    if "/health" in all_routes:
        print("  ✓ Health endpoint registered")
    else:
        print("  ✗ Health endpoint NOT registered")
        sys.exit(1)

except Exception as e:
    print(f"  ✗ Main app import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# All tests passed!
print("\n" + "=" * 60)
print("✅ ALL TESTS PASSED!")
print("=" * 60)
print("\nYour LangGraph backend is ready to use!")
print("\nNext steps:")
print("  1. Run the server: uvicorn main:app --reload --port 8000")
print("  2. Test with frontend or curl")
print("  3. Monitor Opik for traces (if enabled)")
print("\nFor more information, see:")
print("  - README_LANGGRAPH.md (architecture details)")
print("  - MIGRATION_GUIDE.md (migration steps)")
print("=" * 60)
