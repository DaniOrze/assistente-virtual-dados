import json
import os
import re

from dotenv import load_dotenv
load_dotenv()

import streamlit as st

if "ANTHROPIC_API_KEY" in st.secrets:
    os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]

from agent.tools import get_schema, run_query
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

llm = ChatAnthropic(model="claude-opus-4-5")

def _parse_json(text: str) -> dict:
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    return json.loads(text.strip())


def _steps_context(step_results: list) -> str:
    if not step_results:
        return ""
    parts = []
    for i, (desc, df) in enumerate(step_results):
        parts.append(f"Passo {i + 1} — {desc}:\n{df.head(10).to_string()}")
    return "\n\n".join(parts)


def _history_context(history: list) -> str:
    if not history:
        return ""
    tail = history[-5:]
    return "\n".join(
        f"Usuário: {h['question']}\nAssistente: {h['answer']}"
        for h in tail
    )

def node_resolve_question(state):
    history = state.get("conversation_history") or []
    question = state["question"]

    if not history:
        # No history — question is already self-contained
        return {**state, "resolved_question": question}

    history_text = _history_context(history)

    prompt = f"""Você é um assistente que resolve referências em perguntas de acompanhamento.

Histórico da conversa (mais recente por último):
{history_text}

Nova pergunta: "{question}"

Se esta pergunta depende do histórico para ser entendida (ex: "e em 2023?", \
"e para essa categoria?", "mostre só os 5 primeiros", "qual a variação?"), \
reescreva-a como uma pergunta completa e autossuficiente.

Se a pergunta já é autossuficiente, retorne-a exatamente como está.

Responda APENAS com a pergunta reescrita. Sem aspas, sem explicações."""

    response = llm.invoke([HumanMessage(content=prompt)])
    resolved = response.content.strip().strip('"').strip("'")

    steps = state.get("reasoning_steps", [])
    if resolved.lower() != question.lower():
        steps = steps + [f"Pergunta interpretada como: *{resolved}*"]

    return {**state, "resolved_question": resolved, "reasoning_steps": steps}


def node_get_schema(state):
    schema = get_schema()
    return {
        **state,
        "schema": schema,
        "reasoning_steps": state["reasoning_steps"] + ["Schema carregado"],
        "is_multi_step": False,
        "query_plan": [],
        "current_step": 0,
        "step_results": [],
    }

def node_plan_query(state):
    question = state["resolved_question"]

    prompt = f"""Você é um analista de dados sênior.

Schema do banco:
{state["schema"]}

Pergunta: {question}

Decida se esta pergunta pode ser respondida com UMA única query SQL ou se exige
múltiplas queries (ex: cruzar métricas de tabelas distintas, comparar períodos,
calcular rankings dependentes de sub-totais, etc.).

Responda APENAS com JSON puro — sem markdown, sem texto extra.
• Pergunta simples : {{"type": "simple"}}
• Pergunta complexa: {{"type": "multi_step", "steps": ["descrição do passo 1", "descrição do passo 2", ...]}}

Seja conservador: use multi_step apenas quando UMA query SQL não consegue
responder a pergunta de forma satisfatória."""

    response = llm.invoke([HumanMessage(content=prompt)])
    parsed = _parse_json(response.content)

    if parsed.get("type") == "multi_step":
        steps = parsed.get("steps", [])
        return {
            **state,
            "is_multi_step": True,
            "query_plan": steps,
            "current_step": 0,
            "step_results": [],
            "reasoning_steps": state["reasoning_steps"] + [
                f"Plano multi-step ({len(steps)} passos):\n"
                + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(steps))
            ],
        }

    return {
        **state,
        "is_multi_step": False,
        "reasoning_steps": state["reasoning_steps"] + ["Pergunta simples — uma única query"],
    }

def node_generate_sql(state):
    prompt = f"""Você é um analista SQL. Dado o schema abaixo, gere APENAS a query SQL
para responder à pergunta. Não adicione explicações, só o SQL.

Schema:
{state["schema"]}

Pergunta: {state["resolved_question"]}

{"Erro anterior: " + state["error"] if state.get("error") else ""}"""

    response = llm.invoke([HumanMessage(content=prompt)])
    sql = response.content.strip().strip("```sql").strip("```").strip()
    return {
        **state,
        "sql_query": sql,
        "reasoning_steps": state["reasoning_steps"] + [f"SQL gerado:\n```sql\n{sql}\n```"],
    }

def node_execute_sql(state):
    df, error = run_query(state["sql_query"])
    if error:
        return {
            **state,
            "error": error,
            "retries": state.get("retries", 0) + 1,
            "reasoning_steps": state["reasoning_steps"] + [f"Erro: {error}"],
        }
    return {
        **state,
        "sql_result": df,
        "error": None,
        "reasoning_steps": state["reasoning_steps"] + [f"Query executou: {len(df)} linhas"],
    }

def node_generate_sql_step(state):
    step_idx = state["current_step"]
    step_desc = state["query_plan"][step_idx]
    total = len(state["query_plan"])
    prev_ctx = _steps_context(state.get("step_results", []))

    prompt = f"""Você é um analista SQL.

Schema:
{state["schema"]}

Pergunta geral: {state["resolved_question"]}

Você está executando o passo {step_idx + 1} de {total}: {step_desc}

{("Resultados dos passos anteriores:\n" + prev_ctx) if prev_ctx else ""}
{"Erro na tentativa anterior: " + state["error"] if state.get("error") else ""}

Gere APENAS o SQL para este passo específico. Sem explicações."""

    response = llm.invoke([HumanMessage(content=prompt)])
    sql = response.content.strip().strip("```sql").strip("```").strip()
    return {
        **state,
        "sql_query": sql,
        "reasoning_steps": state["reasoning_steps"] + [
            f"Passo {step_idx + 1}/{total} — SQL:\n```sql\n{sql}\n```"
        ],
    }

def node_execute_sql_step(state):
    df, error = run_query(state["sql_query"])
    if error:
        return {
            **state,
            "error": error,
            "retries": state.get("retries", 0) + 1,
            "reasoning_steps": state["reasoning_steps"] + [f"Erro no passo: {error}"],
        }

    step_idx = state["current_step"]
    step_desc = state["query_plan"][step_idx]
    step_results = list(state.get("step_results", [])) + [(step_desc, df)]

    return {
        **state,
        "step_results": step_results,
        "current_step": step_idx + 1,
        "error": None,
        "retries": 0,
        "reasoning_steps": state["reasoning_steps"] + [
            f"Passo {step_idx + 1} concluído: {len(df)} linhas"
        ],
    }

def node_format_answer(state):
    if state.get("is_multi_step") and state.get("step_results"):
        step_results = state["step_results"]
        ctx = _steps_context(step_results)
        last_df = step_results[-1][1]

        prompt = f"""Pergunta do usuário: {state["resolved_question"]}

Você executou {len(step_results)} queries. Resultados:

{ctx}

Com base em TODOS esses resultados, escreva:
1. Uma resposta clara e objetiva em português para um diretor.
2. O melhor tipo de visualização para o resultado final. Escolha um entre:
   - "bar"      → comparar categorias ou rankings
   - "line"     → tendência ao longo do tempo
   - "pie"      → proporção/participação de partes em um todo (use quando houver poucas categorias, ≤8)
   - "scatter"  → correlação entre duas variáveis numéricas (requer ao menos 2 colunas numéricas)
   - "heatmap"  → distribuição cruzada entre duas dimensões e um valor numérico (requer exatamente 3 colunas)
   - "table"    → listagem de registros ou quando nenhum gráfico se aplica
   - "none"     → resposta puramente textual, sem dados tabulares

Responda APENAS com JSON puro:
{{"answer": "...", "chart_type": "..."}}"""

        response = llm.invoke([HumanMessage(content=prompt)])
        parsed = _parse_json(response.content)
        return {
            **state,
            "final_answer": parsed["answer"],
            "chart_type": parsed["chart_type"],
            "sql_result": last_df,
        }

    # simple path
    df = state["sql_result"]
    prompt = f"""Pergunta: {state["resolved_question"]}
Resultado da query (primeiras linhas): {df.head(10).to_string()}

1. Escreva uma resposta em português para o diretor.
2. Sugira o melhor tipo de visualização. Escolha um entre:
   - "bar"      → comparar categorias ou rankings
   - "line"     → tendência ao longo do tempo
   - "pie"      → proporção/participação de partes em um todo (use quando houver poucas categorias, ≤8)
   - "scatter"  → correlação entre duas variáveis numéricas (requer ao menos 2 colunas numéricas)
   - "heatmap"  → distribuição cruzada entre duas dimensões e um valor numérico (requer exatamente 3 colunas)
   - "table"    → listagem de registros ou quando nenhum gráfico se aplica
   - "none"     → resposta puramente textual, sem dados tabulares
Responda APENAS com JSON puro: {{"answer": "...", "chart_type": "..."}}"""

    response = llm.invoke([HumanMessage(content=prompt)])
    parsed = _parse_json(response.content)
    return {
        **state,
        "final_answer": parsed["answer"],
        "chart_type": parsed["chart_type"],
    }

def route_after_plan(state):
    return "generate_sql_step" if state.get("is_multi_step") else "generate_sql"


def should_retry(state):
    if state.get("error") and state.get("retries", 0) < 3:
        return "generate_sql"
    elif state.get("error"):
        return "end"
    return "format_answer"


def should_continue_steps(state):
    if state.get("error"):
        if state.get("retries", 0) < 3:
            return "generate_sql_step"
        return "end"
    if state["current_step"] < len(state["query_plan"]):
        return "generate_sql_step"
    return "format_answer"
