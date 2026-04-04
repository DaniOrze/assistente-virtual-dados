from langgraph.graph import StateGraph, END
from .state import AgentState
from .nodes import (
    node_resolve_question,
    node_get_schema,
    node_plan_query,
    node_generate_sql,
    node_execute_sql,
    node_generate_sql_step,
    node_execute_sql_step,
    node_format_answer,
    route_after_plan,
    should_retry,
    should_continue_steps,
)


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("resolve_question", node_resolve_question)
    graph.add_node("get_schema", node_get_schema)
    graph.add_node("plan_query", node_plan_query)
    graph.add_node("generate_sql", node_generate_sql)
    graph.add_node("execute_sql", node_execute_sql)
    graph.add_node("generate_sql_step", node_generate_sql_step)
    graph.add_node("execute_sql_step", node_execute_sql_step)
    graph.add_node("format_answer", node_format_answer)

    graph.set_entry_point("resolve_question")
    graph.add_edge("resolve_question", "get_schema")
    graph.add_edge("get_schema", "plan_query")

    graph.add_conditional_edges("plan_query", route_after_plan, {
        "generate_sql": "generate_sql",
        "generate_sql_step": "generate_sql_step",
    })

    # simple path
    graph.add_edge("generate_sql", "execute_sql")
    graph.add_conditional_edges("execute_sql", should_retry, {
        "generate_sql": "generate_sql",
        "format_answer": "format_answer",
        "end": END,
    })

    # multi-step path
    graph.add_edge("generate_sql_step", "execute_sql_step")
    graph.add_conditional_edges("execute_sql_step", should_continue_steps, {
        "generate_sql_step": "generate_sql_step",
        "format_answer": "format_answer",
        "end": END,
    })

    graph.add_edge("format_answer", END)

    return graph.compile()
