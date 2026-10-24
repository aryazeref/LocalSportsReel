"""Malformed JSON artifacts must trigger recoverable validation errors."""

import pytest

from app.prediction.engine import ModelBundle


@pytest.mark.parametrize("artifact", [
    None, [], "not a model", 12,
    {"artifact_version": 1, "model": [], "metadata": {}, "report": {}},
    {"artifact_version": 1, "model": {}, "metadata": None, "report": {}},
])
def test_non_object_artifact_is_rejected_without_attribute_errors(artifact):
    with pytest.raises(ValueError):
        ModelBundle.from_dict(artifact)
