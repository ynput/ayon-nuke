"""pytest configuration.

Tests run outside Nuke - `nuke` module is replaced by a mock. ayon-core
client code must be importable, either installed in the environment or
from a sibling `ayon-core` repository checkout.
"""
import sys
from pathlib import Path

tests_path = Path(__file__).resolve().parent
repo_path = tests_path.parent
client_path = repo_path / "client"
core_client_path = repo_path.parent / "ayon-core" / "client"

sys.path.append(str(client_path))
if core_client_path.exists():
    sys.path.append(str(core_client_path))
