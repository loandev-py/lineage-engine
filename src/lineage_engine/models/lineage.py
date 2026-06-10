"""
Modelos de datos del Motor de Linaje.

Estos modelos representan los tres conceptos fundamentales del sistema:
- LineageNode: un dataset o transformación (un "nodo" en el grafo)
- LineageEdge: la relación entre dos nodos ("A produjo B")
- LineageEvent: un evento capturado en tiempo real (la materia prima del linaje)
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


# ─── Enumeraciones ────────────────────────────────────────────────────────────

class NodeType(str, Enum):
    """
    Tipos de nodos en el grafo de linaje.

    Usamos str como base para que Pydantic serialice el valor
    como string ("dataset") en lugar del nombre del enum ("DATASET").
    """
    DATASET = "dataset"         # Una tabla, archivo CSV, DataFrame, etc.
    TRANSFORMATION = "transformation"  # Una función que transforma datos
    SOURCE = "source"           # El origen externo (base de datos, API, S3)
    SINK = "sink"               # El destino final (DW, dashboard, archivo)


class EventType(str, Enum):
    """Tipos de eventos que el motor puede capturar."""
    READ = "read"               # Un nodo leyó datos de otro
    WRITE = "write"             # Un nodo escribió datos a otro
    TRANSFORM = "transform"     # Una transformación procesó datos
    SCHEMA_CHANGE = "schema_change"  # Las columnas o tipos cambiaron


# ─── Modelos principales ─────────────────────────────────────────────────────

class LineageNode(BaseModel):
    """
    Un nodo en el grafo de linaje.

    Representa cualquier entidad que produce o consume datos:
    puede ser una tabla en una base de datos, un archivo CSV,
    una función de transformación, o un modelo de ML.

    Ejemplo de uso:
        node = LineageNode(
            name="orders_cleaned",
            node_type=NodeType.DATASET,
            metadata={"rows": 50000, "source": "postgres"}
        )
    """
    # uuid4() genera un ID único universal — nunca habrá dos nodos con el mismo ID
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=255)
    node_type: NodeType
    # datetime.now(timezone.utc): siempre en UTC para evitar problemas de zona horaria
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # dict[str, Any]: metadatos flexibles — cada nodo puede tener info diferente
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def name_must_be_snake_case(cls, v: str) -> str:
        """
        Valida que el nombre use snake_case.
        En sistemas de datos, nombres consistentes evitan bugs difíciles de encontrar.
        "orders cleaned" y "orders_cleaned" son datasets diferentes para el sistema.
        """
        if " " in v:
            raise ValueError(
                f"El nombre del nodo no puede tener espacios: '{v}'. "
                f"Usa snake_case: '{v.replace(' ', '_')}'"
            )
        return v.lower()

    class Config:
        # Permite usar el enum directamente en lugar del .value
        use_enum_values = True


class LineageEdge(BaseModel):
    """
    Una arista (relación) en el grafo de linaje.

    Representa el flujo de datos entre dos nodos.
    Si el nodo A produjo el nodo B, existe un LineageEdge
    con source_id=A.id y target_id=B.id.

    Ejemplo:
        edge = LineageEdge(
            source_id=raw_table.id,
            target_id=clean_table.id,
            transformation_name="limpiar_nulos"
        )
    """
    id: UUID = Field(default_factory=uuid4)
    source_id: UUID                        # El nodo que produce/lee datos
    target_id: UUID                        # El nodo que recibe/consume datos
    transformation_name: str               # Nombre de la función que creó esta relación
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("transformation_name")
    @classmethod
    def validate_transformation_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El nombre de la transformación no puede estar vacío.")
        return v.strip()


class LineageEvent(BaseModel):
    """
    Un evento de linaje capturado en tiempo real.

    Esta es la "materia prima" del sistema. Cada vez que una función
    decorada con @track_lineage se ejecuta, genera un LineageEvent.
    Estos eventos se acumulan y el Graph Builder los convierte en
    nodos y aristas del grafo de linaje.

    Ejemplo de evento generado automáticamente:
        {
          "id": "a1b2c3...",
          "event_type": "transform",
          "function_name": "limpiar_datos",
          "input_datasets": ["raw_orders"],
          "output_datasets": ["orders_cleaned"],
          "execution_time_ms": 234.5,
          "success": true,
          "timestamp": "2024-01-15T10:30:00Z"
        }
    """
    id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    function_name: str
    # Los datasets de entrada y salida se capturan del decorador
    input_datasets: list[str] = Field(default_factory=list)
    output_datasets: list[str] = Field(default_factory=list)
    execution_time_ms: float = Field(ge=0)  # ge=0: debe ser >= 0
    success: bool = True
    error_message: str | None = None        # Solo se llena si success=False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("error_message")
    @classmethod
    def error_requires_failure(cls, v: str | None, info: Any) -> str | None:
        """Si hay mensaje de error, el evento debe marcarse como fallido."""
        if v is not None and info.data.get("success", True):
            raise ValueError(
                "No puedes tener error_message con success=True. "
                "Si hay error, establece success=False."
            )
        return v

    def to_jsonl_line(self) -> str:
        """
        Serializa el evento a una línea JSONL.

        JSONL (JSON Lines) es un formato donde cada línea es un JSON válido.
        Es ideal para logs porque puedes hacer append sin reescribir el archivo,
        y puedes leerlo línea por línea sin cargar todo en memoria.
        """
        return self.model_dump_json() + "\n"
