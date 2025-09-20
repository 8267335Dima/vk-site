# tests/logic/test_scenario_conversion.py

import pytest
from unittest.mock import MagicMock

from app.api.endpoints.scenarios import _db_to_graph, ScenarioStepNode, ScenarioEdge
from app.db.models import Scenario, ScenarioStep
from app.core.enums import ScenarioStepType

class TestScenarioGraphConversion:
    """Юнит-тесты для функций преобразования данных сценария."""

    def test_db_to_graph_with_conditional_branching(self):
        """
        Тест: проверяет правильность конвертации сложного сценария с условием
        из формата БД в формат узлов и ребер для React Flow.
        """
        # Arrange: создаем мок-объекты, имитирующие структуру из SQLAlchemy
        mock_scenario = MagicMock(spec=Scenario)
        
        step1_start = MagicMock(spec=ScenarioStep, id=1, step_type=ScenarioStepType.action, details={"id": "node-1", "data": {"action_type": "start"}}, position_x=10, position_y=10, next_step_id=2, on_success_next_step_id=None, on_failure_next_step_id=None)
        step2_cond = MagicMock(spec=ScenarioStep, id=2, step_type=ScenarioStepType.condition, details={"id": "node-2", "data": {}}, position_x=10, position_y=110, next_step_id=None, on_success_next_step_id=3, on_failure_next_step_id=4)
        step3_success = MagicMock(spec=ScenarioStep, id=3, step_type=ScenarioStepType.action, details={"id": "node-3", "data": {}}, position_x=-100, position_y=210, next_step_id=None, on_success_next_step_id=None, on_failure_next_step_id=None)
        step4_failure = MagicMock(spec=ScenarioStep, id=4, step_type=ScenarioStepType.action, details={"id": "node-4", "data": {}}, position_x=100, position_y=210, next_step_id=None, on_success_next_step_id=None, on_failure_next_step_id=None)
        
        mock_scenario.steps = [step1_start, step2_cond, step3_success, step4_failure]

        # Act
        nodes, edges = _db_to_graph(mock_scenario)

        # Assert
        assert len(nodes) == 4
        assert len(edges) == 3

        # Проверяем узлы
        node_map = {n.id: n for n in nodes}
        assert node_map["node-1"].type == "start"
        assert node_map["node-2"].type == "condition"
        assert node_map["node-3"].type == "action"

        # Проверяем ребра
        edge_map = {e.id: e for e in edges}
        # Ребро от старта к условию
        assert edge_map["enode-1-node-2"].source == "node-1"
        assert edge_map["enode-1-node-2"].target == "node-2"
        # Ребро "успех"
        assert edge_map["enode-2-node-3-success"].source == "node-2"
        assert edge_map["enode-2-node-3-success"].target == "node-3"
        assert edge_map["enode-2-node-3-success"].sourceHandle == "on_success"
        # Ребро "провал"
        assert edge_map["enode-2-node-4-failure"].source == "node-2"
        assert edge_map["enode-2-node-4-failure"].target == "node-4"
        assert edge_map["enode-2-node-4-failure"].sourceHandle == "on_failure"

    def test_db_to_graph_empty_scenario(self):
        """Тест: пустой сценарий должен возвращать пустые списки."""
        mock_scenario = MagicMock(spec=Scenario, steps=[])
        nodes, edges = _db_to_graph(mock_scenario)
        assert nodes == []
        assert edges == []