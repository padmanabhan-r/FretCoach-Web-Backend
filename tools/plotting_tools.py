"""
Plotting and visualization tools for LangGraph agent
"""
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
from datetime import datetime


@tool
def create_performance_trend_chart(
    sessions_data: List[Dict[str, Any]],
    metrics: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Create a performance trend chart from session data.

    Args:
        sessions_data (List[Dict]): List of session records with timestamps and metrics
        metrics (List[str], optional): Metrics to plot. Defaults to ['pitch_accuracy', 'scale_conformity', 'timing_stability']

    Returns:
        Dict with chart configuration for frontend plotting:
            - type: "line"
            - data: Chart data with labels and datasets
            - title: Chart title
            - description: Chart description
    """
    if not metrics:
        metrics = ["pitch_accuracy", "scale_conformity", "timing_stability"]

    # Sort sessions by timestamp
    sorted_sessions = sorted(
        sessions_data,
        key=lambda x: x.get("start_timestamp", "")
    )

    # Extract labels (dates) and data points
    labels = []
    datasets = {metric: [] for metric in metrics}

    for session in sorted_sessions:
        # Format timestamp for label
        timestamp = session.get("start_timestamp", "")
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                labels.append(dt.strftime("%m/%d %H:%M"))
            except:
                labels.append(timestamp[:10])
        else:
            labels.append("")

        # Extract metric values (convert from 0-1 to 0-100 percentage)
        for metric in metrics:
            value = session.get(metric)
            datasets[metric].append((value * 100) if value is not None else 0)

    # Build chart configuration
    metric_labels = {
        "pitch_accuracy": "Pitch Accuracy",
        "scale_conformity": "Scale Conformity",
        "timing_stability": "Timing Stability"
    }

    metric_colors = {
        "pitch_accuracy": "rgba(75, 192, 192, 1)",
        "scale_conformity": "rgba(153, 102, 255, 1)",
        "timing_stability": "rgba(255, 159, 64, 1)"
    }

    chart_datasets = []
    for metric in metrics:
        chart_datasets.append({
            "label": metric_labels.get(metric, metric),
            "data": datasets[metric],
            "borderColor": metric_colors.get(metric, "rgba(0, 0, 0, 1)"),
            "backgroundColor": metric_colors.get(metric, "rgba(0, 0, 0, 0.1)"),
            "tension": 0.4
        })

    return {
        "type": "performance_trend",
        "data": {
            "labels": labels,
            "datasets": chart_datasets
        },
        "options": {
            "responsive": True,
            "plugins": {
                "title": {
                    "display": True,
                    "text": "Performance Trend Over Time"
                },
                "legend": {
                    "display": True
                }
            },
            "scales": {
                "y": {
                    "beginAtZero": True,
                    "max": 100
                }
            }
        },
        "title": "Performance Trend",
        "description": f"Showing trend for {len(sorted_sessions)} practice sessions"
    }


@tool
def create_comparison_chart(
    current_metrics: Dict[str, float],
    average_metrics: Dict[str, float]
) -> Dict[str, Any]:
    """
    Create a comparison chart between current session and average performance.

    Args:
        current_metrics (Dict[str, float]): Current session metrics (e.g., {"pitch_accuracy": 85.5, ...})
        average_metrics (Dict[str, float]): Average metrics across all sessions

    Returns:
        Dict with bar chart configuration comparing current vs average
    """
    metrics = ["pitch_accuracy", "scale_conformity", "timing_stability"]
    labels = ["Pitch Accuracy", "Scale Conformity", "Timing Stability"]

    # Convert from 0-1 to 0-100 percentage
    current_values = [(current_metrics.get(m, 0) * 100) for m in metrics]
    average_values = [(average_metrics.get(m, 0) * 100) for m in metrics]

    return {
        "type": "comparison",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Latest Session",
                    "data": current_values,
                    "backgroundColor": "rgba(75, 192, 192, 0.6)",
                    "borderColor": "rgba(75, 192, 192, 1)",
                    "borderWidth": 1
                },
                {
                    "label": "Your Average",
                    "data": average_values,
                    "backgroundColor": "rgba(153, 102, 255, 0.6)",
                    "borderColor": "rgba(153, 102, 255, 1)",
                    "borderWidth": 1
                }
            ]
        },
        "options": {
            "responsive": True,
            "plugins": {
                "title": {
                    "display": True,
                    "text": "Latest Session vs Your Average"
                }
            },
            "scales": {
                "y": {
                    "beginAtZero": True,
                    "max": 100
                }
            }
        },
        "title": "Performance Comparison",
        "description": "How your latest session compares to your overall average"
    }


@tool
def create_practice_plan_chart(
    practice_plan: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create a visual chart representation of a practice plan.

    Args:
        practice_plan (Dict): Practice plan with exercises and durations

    Returns:
        Dict with chart configuration (typically a horizontal bar chart showing time allocation)
    """
    exercises = practice_plan.get("exercises", [])

    if not exercises:
        return {
            "type": "text",
            "data": practice_plan,
            "title": "Practice Plan",
            "description": "Your personalized practice plan"
        }

    labels = []
    durations = []

    for exercise in exercises:
        labels.append(exercise.get("name", "Exercise"))
        durations.append(exercise.get("duration_minutes", 0))

    return {
        "type": "practice_plan",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Duration (minutes)",
                "data": durations,
                "backgroundColor": [
                    "rgba(255, 99, 132, 0.6)",
                    "rgba(54, 162, 235, 0.6)",
                    "rgba(255, 206, 86, 0.6)",
                    "rgba(75, 192, 192, 0.6)",
                    "rgba(153, 102, 255, 0.6)"
                ]
            }]
        },
        "options": {
            "indexAxis": "y",
            "responsive": True,
            "plugins": {
                "title": {
                    "display": True,
                    "text": "Practice Plan Breakdown"
                }
            }
        },
        "title": "Practice Plan",
        "description": f"Total practice time: {sum(durations)} minutes"
    }
