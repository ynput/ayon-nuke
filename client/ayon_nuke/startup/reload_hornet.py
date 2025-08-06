import importlib
import sys
import nuke
import os

def reload_hornet_deadline_utils():
    mod_name = "hornet_deadline_utils"
    if mod_name in sys.modules:
        importlib.reload(sys.modules[mod_name])
        print(f"Reloaded {mod_name}")
    else:
        print(f"Module {mod_name} not found")

# reload_hornet_deadline_utils()