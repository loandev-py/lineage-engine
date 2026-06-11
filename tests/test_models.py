import pytest
from pydantic import ValidationError

from lineage_engine.models.lineage import (EventType, LineageEdge, LineageEvent, LineageNode, NodeType)

class TestLineageNode:

    def test_creates_node_with_valid_data(self) -> None:
        node = LineageNode(name="orders_raw", node_type=NodeType.DATASET)
        assert node.name == "ordes_raw"
        assert node.node_type == NodeType.DATASET
        assert node.id is not None
        assert node.created_at is not None

    def test_name_is_lowercased(self) -> None:
        node =LineageNode(name="orders_Raw", node_type=NodeType.DATASET)
        assert node.name == "orders_raw"


