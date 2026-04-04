from typing import TypedDict, List, Optional, Any

class AgentState(TypedDict):
    question: str
    resolved_question: str
    schema: str
    sql_query: str
    sql_result: Any
    error: Optional[str]
    retries: int
    final_answer: str
    reasoning_steps: List[str]
    chart_type: Optional[str]
    conversation_history: List[dict]
    is_multi_step: bool
    query_plan: List[str]
    current_step: int
    step_results: List[Any]
