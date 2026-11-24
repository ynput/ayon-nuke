"""Run pytest inside Nuke, started by `tests/run_nuke_tests.py`.

Nuke runs this file in terminal mode (`Nuke -t`). Settings come from the
environment:

    NUKE_TEST_PATHS   paths added to `sys.path` (os.pathsep separated)
    NUKE_PYTEST_ARGS  JSON list of pytest arguments
    NUKE_PYTEST_LOG   file pytest writes its output to
    NUKE_TEST_RESULT  JSON file with the pytest exit code

Nuke is closed with `os._exit()` so the exit code is pytest's.
"""

import json
import os
import sys
import traceback


def main():
    exitcode = 3
    log_path = os.environ.get("NUKE_PYTEST_LOG")
    log_stream = None
    if log_path:
        log_stream = open(log_path, "w", buffering=1)
        sys.stdout = log_stream
        sys.stderr = log_stream

    try:
        paths = os.environ.get("NUKE_TEST_PATHS", "").split(os.pathsep)
        for path in reversed(paths):
            if path and path not in sys.path:
                sys.path.insert(0, path)

        import pytest

        args = json.loads(os.environ.get("NUKE_PYTEST_ARGS") or "[]")
        exitcode = int(pytest.main(args + ["-p", "no:cacheprovider"]))
    except BaseException:
        traceback.print_exc()
    finally:
        result_path = os.environ.get("NUKE_TEST_RESULT")
        if result_path:
            with open(result_path, "w") as stream:
                json.dump({"exitcode": exitcode}, stream)
        if log_stream:
            log_stream.flush()
        os._exit(exitcode)


main()
