import json
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch


FAKE_SCHEMA = (
    "Tabela 'clientes': id (INTEGER), nome (TEXT), cidade (TEXT)\n"
    "Tabela 'compras': id (INTEGER), cliente_id (INTEGER), valor (REAL), categoria (TEXT)"
)


def make_state(**overrides) -> dict:
    state = {
        "question": "Quais os 5 clientes que mais gastaram?",
        "resolved_question": "Quais os 5 clientes que mais gastaram?",
        "schema": FAKE_SCHEMA,
        "sql_query": "",
        "sql_result": None,
        "error": None,
        "retries": 0,
        "final_answer": "",
        "reasoning_steps": [],
        "chart_type": None,
        "conversation_history": [],
        "is_multi_step": False,
        "query_plan": [],
        "current_step": 0,
        "step_results": [],
    }
    state.update(overrides)
    return state


def fake_llm_response(content: str) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    return msg


class TestParseJson:
    def test_plain_json(self):
        from agent.nodes import _parse_json
        result = _parse_json('{"type": "simple"}')
        assert result == {"type": "simple"}

    def test_json_with_markdown_fences(self):
        from agent.nodes import _parse_json
        result = _parse_json('```json\n{"answer": "ok", "chart_type": "bar"}\n```')
        assert result["answer"] == "ok"
        assert result["chart_type"] == "bar"

    def test_json_with_bare_fences(self):
        from agent.nodes import _parse_json
        result = _parse_json('```\n{"type": "multi_step", "steps": ["passo 1"]}\n```')
        assert result["type"] == "multi_step"

    def test_invalid_json_raises(self):
        from agent.nodes import _parse_json
        with pytest.raises(json.JSONDecodeError):
            _parse_json("isso nao e json")

class TestNodeGenerateSql:
    def test_sql_extracted_from_response(self):
        from agent.nodes import node_generate_sql
        sql = "SELECT nome, SUM(valor) FROM compras GROUP BY cliente_id LIMIT 5"
        state = make_state()

        with patch("agent.nodes.llm") as mock_llm:
            mock_llm.invoke.return_value = fake_llm_response(sql)
            result = node_generate_sql(state)

        assert result["sql_query"] == sql

    def test_sql_strips_markdown_fences(self):
        from agent.nodes import node_generate_sql
        raw = "```sql\nSELECT * FROM clientes\n```"
        state = make_state()

        with patch("agent.nodes.llm") as mock_llm:
            mock_llm.invoke.return_value = fake_llm_response(raw)
            result = node_generate_sql(state)

        assert "```" not in result["sql_query"]
        assert "SELECT" in result["sql_query"]

    def test_reasoning_step_added(self):
        from agent.nodes import node_generate_sql
        state = make_state()

        with patch("agent.nodes.llm") as mock_llm:
            mock_llm.invoke.return_value = fake_llm_response("SELECT 1")
            result = node_generate_sql(state)

        assert any("SQL gerado" in step for step in result["reasoning_steps"])

    def test_error_context_included_in_prompt(self):
        from agent.nodes import node_generate_sql
        state = make_state(error="no such table: vendas", retries=1)

        with patch("agent.nodes.llm") as mock_llm:
            mock_llm.invoke.return_value = fake_llm_response("SELECT * FROM compras")
            node_generate_sql(state)
            prompt_text = mock_llm.invoke.call_args[0][0][0].content

        assert "no such table: vendas" in prompt_text

    def test_no_error_context_when_clean(self):
        from agent.nodes import node_generate_sql
        state = make_state()

        with patch("agent.nodes.llm") as mock_llm:
            mock_llm.invoke.return_value = fake_llm_response("SELECT 1")
            node_generate_sql(state)
            prompt_text = mock_llm.invoke.call_args[0][0][0].content

        assert "Erro anterior" not in prompt_text

class TestNodeExecuteSql:
    def test_success_stores_dataframe(self):
        from agent.nodes import node_execute_sql
        df = pd.DataFrame({"nome": ["Alice", "Bob"], "total": [500.0, 300.0]})
        state = make_state(sql_query="SELECT nome, SUM(valor) FROM compras LIMIT 2")

        with patch("agent.nodes.run_query", return_value=(df, None)):
            result = node_execute_sql(state)

        assert result["sql_result"] is not None
        assert len(result["sql_result"]) == 2
        assert result["error"] is None

    def test_success_clears_previous_error(self):
        from agent.nodes import node_execute_sql
        df = pd.DataFrame({"x": [1]})
        state = make_state(sql_query="SELECT 1", error="erro anterior", retries=1)

        with patch("agent.nodes.run_query", return_value=(df, None)):
            result = node_execute_sql(state)

        assert result["error"] is None

    def test_error_increments_retries(self):
        from agent.nodes import node_execute_sql
        state = make_state(sql_query="SELECT * FROM tabela_inexistente", retries=0)

        with patch("agent.nodes.run_query", return_value=(None, "no such table")):
            result = node_execute_sql(state)

        assert result["retries"] == 1
        assert result["error"] == "no such table"

    def test_error_adds_reasoning_step(self):
        from agent.nodes import node_execute_sql
        state = make_state(sql_query="SELECT bad")

        with patch("agent.nodes.run_query", return_value=(None, "syntax error")):
            result = node_execute_sql(state)

        assert any("Erro" in step for step in result["reasoning_steps"])

    def test_success_adds_row_count_to_reasoning(self):
        from agent.nodes import node_execute_sql
        df = pd.DataFrame({"a": range(7)})
        state = make_state(sql_query="SELECT a FROM t")

        with patch("agent.nodes.run_query", return_value=(df, None)):
            result = node_execute_sql(state)

        assert any("7" in step for step in result["reasoning_steps"])

class TestNodeFormatAnswerSimple:
    def _run(self, llm_response: str, **state_overrides):
        from agent.nodes import node_format_answer
        df = pd.DataFrame({"nome": ["Alice"], "total": [900.0]})
        state = make_state(sql_result=df, is_multi_step=False, **state_overrides)

        with patch("agent.nodes.llm") as mock_llm:
            mock_llm.invoke.return_value = fake_llm_response(llm_response)
            return node_format_answer(state)

    def test_final_answer_populated(self):
        result = self._run('{"answer": "Alice gastou mais.", "chart_type": "bar"}')
        assert result["final_answer"] == "Alice gastou mais."

    def test_chart_type_extracted(self):
        result = self._run('{"answer": "Texto.", "chart_type": "bar"}')
        assert result["chart_type"] == "bar"

    def test_chart_type_line(self):
        result = self._run('{"answer": "Tendência.", "chart_type": "line"}')
        assert result["chart_type"] == "line"

    def test_chart_type_table(self):
        result = self._run('{"answer": "Lista.", "chart_type": "table"}')
        assert result["chart_type"] == "table"

    def test_chart_type_none(self):
        result = self._run('{"answer": "Resposta simples.", "chart_type": "none"}')
        assert result["chart_type"] == "none"

    def test_accepts_markdown_fenced_json(self):
        result = self._run('```json\n{"answer": "Ok.", "chart_type": "bar"}\n```')
        assert result["final_answer"] == "Ok."

class TestNodeFormatAnswerMultiStep:
    def _run(self, llm_response: str):
        from agent.nodes import node_format_answer
        df1 = pd.DataFrame({"categoria": ["Eletronicos"], "total": [10000.0]})
        df2 = pd.DataFrame({"categoria": ["Eletronicos"], "total_2024": [12000.0]})
        step_results = [("Totais 2023", df1), ("Totais 2024", df2)]
        state = make_state(
            is_multi_step=True,
            step_results=step_results,
            query_plan=["Totais 2023", "Totais 2024"],
            current_step=2,
        )

        with patch("agent.nodes.llm") as mock_llm:
            mock_llm.invoke.return_value = fake_llm_response(llm_response)
            return node_format_answer(state)

    def test_final_answer_populated(self):
        result = self._run('{"answer": "Crescimento de 20%.", "chart_type": "bar"}')
        assert result["final_answer"] == "Crescimento de 20%."

    def test_sql_result_is_last_step_df(self):
        result = self._run('{"answer": "Ok.", "chart_type": "table"}')
        assert list(result["sql_result"].columns) == ["categoria", "total_2024"]

    def test_prompt_contains_all_step_results(self):
        from agent.nodes import node_format_answer
        df1 = pd.DataFrame({"x": [1]})
        df2 = pd.DataFrame({"y": [2]})
        step_results = [("Passo A", df1), ("Passo B", df2)]
        state = make_state(is_multi_step=True, step_results=step_results, current_step=2)

        with patch("agent.nodes.llm") as mock_llm:
            mock_llm.invoke.return_value = fake_llm_response('{"answer": ".", "chart_type": "none"}')
            node_format_answer(state)
            prompt = mock_llm.invoke.call_args[0][0][0].content

        assert "Passo A" in prompt
        assert "Passo B" in prompt

class TestNodeGenerateSqlStep:
    def test_sql_generated_for_current_step(self):
        from agent.nodes import node_generate_sql_step
        state = make_state(
            is_multi_step=True,
            query_plan=["Total por categoria", "Top clientes"],
            current_step=0,
            step_results=[],
        )

        with patch("agent.nodes.llm") as mock_llm:
            mock_llm.invoke.return_value = fake_llm_response("SELECT categoria, SUM(valor) FROM compras GROUP BY categoria")
            result = node_generate_sql_step(state)

        assert "SELECT" in result["sql_query"]

    def test_reasoning_step_shows_step_index(self):
        from agent.nodes import node_generate_sql_step
        state = make_state(
            is_multi_step=True,
            query_plan=["Passo 1", "Passo 2"],
            current_step=1,
            step_results=[(
                "Passo 1",
                pd.DataFrame({"x": [1]}),
            )],
        )

        with patch("agent.nodes.llm") as mock_llm:
            mock_llm.invoke.return_value = fake_llm_response("SELECT 1")
            result = node_generate_sql_step(state)

        assert any("2/2" in step for step in result["reasoning_steps"])

    def test_previous_step_results_in_prompt(self):
        from agent.nodes import node_generate_sql_step
        prev_df = pd.DataFrame({"categoria": ["Eletronicos"], "total": [5000]})
        state = make_state(
            is_multi_step=True,
            query_plan=["Passo 1", "Passo 2"],
            current_step=1,
            step_results=[("Passo 1", prev_df)],
        )

        with patch("agent.nodes.llm") as mock_llm:
            mock_llm.invoke.return_value = fake_llm_response("SELECT 1")
            node_generate_sql_step(state)
            prompt = mock_llm.invoke.call_args[0][0][0].content

        assert "Eletronicos" in prompt

class TestNodeExecuteSqlStep:
    def test_success_advances_step(self):
        from agent.nodes import node_execute_sql_step
        df = pd.DataFrame({"categoria": ["Eletronicos"], "total": [1000]})
        state = make_state(
            sql_query="SELECT categoria, SUM(valor) FROM compras GROUP BY categoria",
            is_multi_step=True,
            query_plan=["Passo 1", "Passo 2"],
            current_step=0,
            step_results=[],
        )

        with patch("agent.nodes.run_query", return_value=(df, None)):
            result = node_execute_sql_step(state)

        assert result["current_step"] == 1

    def test_success_appends_to_step_results(self):
        from agent.nodes import node_execute_sql_step
        df = pd.DataFrame({"x": [1, 2]})
        state = make_state(
            sql_query="SELECT x FROM t",
            is_multi_step=True,
            query_plan=["Step A"],
            current_step=0,
            step_results=[],
        )

        with patch("agent.nodes.run_query", return_value=(df, None)):
            result = node_execute_sql_step(state)

        assert len(result["step_results"]) == 1
        assert result["step_results"][0][0] == "Step A"

    def test_success_resets_retries(self):
        from agent.nodes import node_execute_sql_step
        df = pd.DataFrame({"x": [1]})
        state = make_state(
            sql_query="SELECT x FROM t",
            is_multi_step=True,
            query_plan=["Step A"],
            current_step=0,
            step_results=[],
            retries=2,
        )

        with patch("agent.nodes.run_query", return_value=(df, None)):
            result = node_execute_sql_step(state)

        assert result["retries"] == 0
        assert result["error"] is None

    def test_error_increments_retries_without_advancing(self):
        from agent.nodes import node_execute_sql_step
        state = make_state(
            sql_query="SELECT bad",
            is_multi_step=True,
            query_plan=["Step A"],
            current_step=0,
            step_results=[],
            retries=1,
        )

        with patch("agent.nodes.run_query", return_value=(None, "syntax error")):
            result = node_execute_sql_step(state)

        assert result["retries"] == 2
        assert result["current_step"] == 0  # não avançou

class TestShouldRetry:
    def test_no_error_goes_to_format_answer(self):
        from agent.nodes import should_retry
        assert should_retry(make_state()) == "format_answer"

    def test_error_below_limit_retries(self):
        from agent.nodes import should_retry
        state = make_state(error="some error", retries=1)
        assert should_retry(state) == "generate_sql"

    def test_error_at_limit_ends(self):
        from agent.nodes import should_retry
        state = make_state(error="some error", retries=3)
        assert should_retry(state) == "end"

    def test_error_above_limit_ends(self):
        from agent.nodes import should_retry
        state = make_state(error="some error", retries=5)
        assert should_retry(state) == "end"


class TestShouldContinueSteps:
    def test_more_steps_remaining(self):
        from agent.nodes import should_continue_steps
        state = make_state(
            is_multi_step=True,
            query_plan=["Step 1", "Step 2"],
            current_step=1,
        )
        assert should_continue_steps(state) == "generate_sql_step"

    def test_all_steps_done_goes_to_format_answer(self):
        from agent.nodes import should_continue_steps
        state = make_state(
            is_multi_step=True,
            query_plan=["Step 1", "Step 2"],
            current_step=2,
        )
        assert should_continue_steps(state) == "format_answer"

    def test_error_below_limit_retries_step(self):
        from agent.nodes import should_continue_steps
        state = make_state(
            error="bad sql",
            retries=2,
            query_plan=["Step 1"],
            current_step=0,
        )
        assert should_continue_steps(state) == "generate_sql_step"

    def test_error_at_limit_ends(self):
        from agent.nodes import should_continue_steps
        state = make_state(
            error="bad sql",
            retries=3,
            query_plan=["Step 1"],
            current_step=0,
        )
        assert should_continue_steps(state) == "end"
