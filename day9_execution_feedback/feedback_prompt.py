"""构造不包含标准答案的执行结果反馈 Prompt。"""

from __future__ import annotations

import json
from typing import Any


def compact_value(value: Any, max_length: int = 120) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    text = str(value)
    return text if len(text) <= max_length else text[: max_length - 3] + "..."


def execution_feedback(execution: dict[str, Any]) -> dict[str, Any]:
    rows = execution.get("rows") or []
    return {
        "execution_success": bool(execution.get("success")),
        "error": execution.get("error"),
        "returned_columns": execution.get("columns") or [],
        "total_row_count": len(rows) if execution.get("success") else None,
        "sample_rows": [
            [compact_value(value) for value in row[:8]] for row in rows[:3]
        ],
        "sample_note": "Only the first 3 rows and first 8 columns are shown.",
    }


def build_feedback_prompt(
    question: str,
    schema: str,
    initial_sql: str,
    execution: dict[str, Any],
) -> str:
    feedback_json = json.dumps(
        execution_feedback(execution), ensure_ascii=False, indent=2
    )
    return f"""You are reviewing a SQLite Text-to-SQL query after it was executed.

Independently check whether the SQL correctly answers the natural-language question. Execution success only means the SQL is syntactically executable; it does not prove semantic correctness. Check tables, joins, filters, aggregation, GROUP BY, HAVING, DISTINCT, ordering, limits, and set logic when relevant.

If the original SQL is already correct, return the same SQL. If it is incorrect, return one corrected SQL query.

Requirements:
1. Output SQL only, without explanation or Markdown fences.
2. Only use tables and columns present in the Schema.
3. Only generate a read-only SELECT or WITH query.
4. Treat sample rows as execution evidence, not as the complete database.
5. An empty result is not automatically an error.

Schema:
{schema}

Question:
{question}

Original SQL:
{initial_sql}

Execution feedback:
{feedback_json}
"""
