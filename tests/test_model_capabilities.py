"""Model capabilities come from models.json, the single source shared with Turzi."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.local_akuvox.const import (
    DEFAULT_MODEL_CAPABILITIES,
    MODEL_CAPABILITIES,
    get_model_capabilities,
)

MODELS_JSON = (
    Path(__file__).parent.parent / "custom_components" / "local_akuvox" / "models.json"
)


def test_table_is_the_json_file() -> None:
    """The table is the file, not a copy of it."""
    assert json.loads(MODELS_JSON.read_text(encoding="utf-8")) == MODEL_CAPABILITIES


def test_every_model_has_exactly_the_three_fields() -> None:
    """Turzi's generator reads these three and nothing else."""
    for model, caps in MODEL_CAPABILITIES.items():
        assert model == model.upper(), model
        assert set(caps) == {"relays", "inputs", "tamper"}, model
        assert isinstance(caps["relays"], int)
        assert isinstance(caps["inputs"], int)
        assert isinstance(caps["tamper"], bool)


def test_lookup_exact_prefix_and_default() -> None:
    """Exact first, then the longest prefix, then the default."""
    assert get_model_capabilities("s535") == {"relays": 1, "inputs": 2, "tamper": False}
    assert get_model_capabilities("X915V2") == MODEL_CAPABILITIES["X915V2"]
    assert get_model_capabilities("R29S") == MODEL_CAPABILITIES["R29"]
    assert get_model_capabilities("Z1") == DEFAULT_MODEL_CAPABILITIES
