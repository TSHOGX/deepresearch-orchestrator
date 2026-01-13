"""JSON schemas for structured LLM outputs.

These schemas are used with Claude CLI's --json-schema parameter
to enforce structured output at the API level.
"""

# Schema for planner's structured output (Step 2 of Two-Step Pattern)
# Used after free-form thinking to extract structured plan
PLANNER_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "mode": {
            "type": "string",
            "enum": ["clarification", "plan"],
            "description": "Whether to ask clarifications or provide a plan"
        },
        "understanding": {
            "type": "string",
            "description": "Summary of how the query is understood"
        },
        "clarifications": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Questions to ask user for clarification (only if mode=clarification)"
        },
        "plan_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Unique identifier for this plan item"
                    },
                    "topic": {
                        "type": "string",
                        "description": "Research topic name"
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed description of what to research"
                    },
                    "scope": {
                        "type": "string",
                        "description": "Boundaries for this research item"
                    },
                    "priority": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                        "description": "Priority level (1=highest, 5=lowest)"
                    },
                    "key_questions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Key questions to answer"
                    },
                    "suggested_sources": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Suggested sources to explore"
                    }
                },
                "required": ["topic", "description"],
                "additionalProperties": False
            },
            "description": "List of research items (only if mode=plan)"
        },
        "estimated_time_minutes": {
            "type": "integer",
            "minimum": 1,
            "description": "Estimated time to complete research in minutes"
        }
    },
    "required": ["mode", "understanding"],
    "additionalProperties": False
}


def get_planner_schema() -> dict:
    """Get the schema for planner extraction step."""
    return PLANNER_EXTRACTION_SCHEMA
