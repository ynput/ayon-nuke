# Type stubs for pyblish.api
from typing import Any, Dict, List, Optional, Type

# Plugin order constants
CollectorOrder: float
ValidatorOrder: float
ExtractorOrder: float
IntegratorOrder: float

class Plugin:
    """Base pyblish plugin"""
    order: float
    hosts: List[str]
    families: List[str]
    label: str
    optional: bool
    
    def __init__(self) -> None: ...
    def process(self, context: Any) -> None: ...

class ContextPlugin(Plugin):
    """Context-based plugin"""
    def process(self, context: Any) -> None: ...

class InstancePlugin(Plugin):
    """Instance-based plugin"""
    families: List[str]
    
    def process(self, instance: Any) -> None: ...

class Collector(ContextPlugin):
    """Collector plugin"""
    order: float

class Validator(InstancePlugin):
    """Validator plugin"""
    order: float

class Extractor(InstancePlugin):
    """Extractor plugin"""
    order: float

class Integrator(InstancePlugin):
    """Integrator plugin"""
    order: float

def register_plugin(plugin: Type[Plugin]) -> None: ...
def deregister_plugin(plugin: Type[Plugin]) -> None: ... 