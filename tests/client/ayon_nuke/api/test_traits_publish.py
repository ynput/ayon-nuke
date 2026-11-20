"""Publishing helpers decide trait usage from instance data."""
from unittest import mock

import pytest

from _module_loader import load_api_module


@pytest.fixture(scope="module")
def nuke_traits():
    return load_api_module("traits")


@pytest.mark.parametrize("value, expected", [
    (True, True),
    (False, False),
    (None, False),
])
def test_uses_trait_representations(nuke_traits, value, expected):
    instance = mock.MagicMock()
    instance.data = {}
    if value is not None:
        instance.data[nuke_traits.INSTANCE_DATA_KEY] = value

    assert nuke_traits.uses_trait_representations(instance) is expected


def test_trait_render_targets(nuke_traits):
    assert nuke_traits.TRAIT_RENDER_TARGETS == {"local", "frames"}
