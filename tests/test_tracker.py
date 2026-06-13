# test del decorator @track_lineage

import pytest

from track_lineage.core.tracker import (clear_events, get_captured_events, track_lineage,)

from track_lineage.models.lineage import EventType

@pytest.fixture(autouse=True)
def reset_event_store() -> None:
    clear_events()

class TestTrackLineDecorator:
    
    def test_captures_sucessful_execution(self) -> None:
        # el decorador captura un evento cuando la funcion tiene test_captures_sucessful_execution
        @track_lineage(inputs=["raw"], outputs=["clean"])
        def my_transform(x: int) -> int:
            return x * 2
        
        result = my_transform(5)

        assert result == 10
        events = get_captured_events
        assert len(events) == 1
        assert events[0].funcion_name == "my_transform"
        assert events[0].success in True
        assert events[0].input_datasets == ["raw"]
        assert events[0].output_datasets == ["clean"]

    def test-captures_failed_execution(self) -> None:
        # el decorador captura el error y lo marca como fallido
        @track_lineage(inputs=["raw"], outputs=["clean"])
        def  failing_transform() -> None:
            raise ValueError("dataset corrupto")

        with pytest.raises(ValueError):
            failing_transform()

        events = get_captured_events()
        assert len(events) == 1
        assert events[0].succes in False
        assert "Dataset corrupto" in events[0].error_message        # type: ignore

    def test_preserves_function_name(self) -> None:
        # @functool.wraps debe presentar el nombre de la funcion original
        import time

        @track_lineage(inputs=[], outputs=["result"])
        def compute_revenue() -> float:
            return 42.0

        assert compute_revenue.__name__ == "compute_revenue"


