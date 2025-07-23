# Type stubs for ayon_core.pipeline.publish
from typing import Any, Dict, List, Optional
import pyblish.api

class Extractor(pyblish.api.InstancePlugin):
    """Base extractor class"""
    order: float
    families: List[str]
    hosts: List[str]
    
    def process(self, instance: Any) -> None: ...

class Validator(pyblish.api.InstancePlugin):
    """Base validator class"""
    order: float
    families: List[str]
    hosts: List[str]
    
    def process(self, instance: Any) -> None: ...

class Collector(pyblish.api.ContextPlugin):
    """Base collector class"""
    order: float
    
    def process(self, context: Any) -> None: ...

class Integrator(pyblish.api.InstancePlugin):
    """Base integrator class"""
    order: float
    families: List[str]
    hosts: List[str]
    
    def process(self, instance: Any) -> None: ...

class OptionalPyblishPluginMixin:
    """Mixin for optional pyblish plugins"""
    optional: bool
    
    def __init__(self, *args: Any, **kwargs: Any) -> None: ... 