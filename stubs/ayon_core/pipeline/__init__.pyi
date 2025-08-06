# Type stubs for ayon_core.pipeline
from typing import Any, Type, Dict, List, Optional

# Import the publish module
from . import publish as publish

class Creator:
    """Base creator class"""
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class Loader:
    """Base loader class"""
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

def register_creator_plugin(plugin: Type[Creator]) -> None: ...
def register_loader_plugin(plugin: Type[Loader]) -> None: ... 