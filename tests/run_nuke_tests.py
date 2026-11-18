"""Run the tests in `tests/nuke` inside Nuke.

The tests run in a real Nuke session in terminal mode (`Nuke -t`), so no
window opens. It needs a Nuke licence that allows terminal mode.

Usage:
    ayon run tests/run_nuke_tests.py [--app PATH] [--core PATH] [-- ARGS]
    python tests/run_nuke_tests.py ...  (without the AYON launcher)

Only the standard library is used, so any Python 3.9+ runs this file.
See `tests/README.md`.
"""

import argparse
import glob
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
NUKE_TESTS_DIR = os.path.join(TESTS_DIR, "nuke")
BOOTSTRAP = os.path.join(NUKE_TESTS_DIR, "bootstrap.py")
REQUIREMENTS = os.path.join(TESTS_DIR, "requirements-nuke.txt")
DEPS_ROOT = os.path.join(TESTS_DIR, ".deps")
RESULTS_DIR = os.path.join(TESTS_DIR, ".results")

# Python version of each supported Nuke major version
PYTHON_BY_NUKE_MAJOR = {14: "3.9", 15: "3.10", 16: "3.11", 17: "3.11"}

_EXECUTABLE_RE = re.compile(r"^Nuke(\d+)\.(\d+)(\.exe)?$")


def _log(message):
    print(f"[run_nuke_tests] {message}", flush=True)


def _install_roots():
    system = platform.system()
    if system == "Darwin":
        return ["/Applications"]
    if system == "Windows":
        return [os.environ.get("PROGRAMFILES", r"C:\Program Files")]
    return ["/usr/local", "/opt"]


def _find_executable_in(path):
    """Return the Nuke executable for a file, `.app` bundle or folder."""
    if os.path.isfile(path):
        return path

    candidates = []
    patterns = (
        os.path.join(path, "Contents", "MacOS", "Nuke*"),
        # The plain "Nuke16.1v1.app", not NukeX, Studio, Assist or the
        # Non-Commercial one (no terminal mode).
        os.path.join(
            path, "Nuke[0-9]*v[0-9]*.app", "Contents", "MacOS", "Nuke*"
        ),
        os.path.join(path, "Nuke*"),
    )
    for pattern in patterns:
        for candidate in glob.glob(pattern):
            if os.path.isfile(candidate) and _EXECUTABLE_RE.match(
                os.path.basename(candidate)
            ):
                candidates.append(candidate)
    return sorted(candidates)[-1] if candidates else None


def _nuke_version(executable):
    match = _EXECUTABLE_RE.match(os.path.basename(executable))
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def find_nuke_executable(app_path=None):
    """Find the Nuke executable.

    Order: `--app`, `AYON_NUKE_EXECUTABLE`, the newest Nuke 15 to 17 install
    in the usual install folder of the platform.
    """
    for path in (app_path, os.environ.get("AYON_NUKE_EXECUTABLE")):
        if not path:
            continue
        executable = _find_executable_in(path)
        if not executable:
            raise SystemExit(f"No Nuke executable found in '{path}'.")
        return executable

    found = []
    for root in _install_roots():
        for folder in glob.glob(os.path.join(root, "Nuke1[4-7]*")):
            executable = _find_executable_in(folder)
            if executable:
                found.append((_nuke_version(executable), executable))
    if not found:
        raise SystemExit(
            "No Nuke found. Pass --app or set AYON_NUKE_EXECUTABLE."
        )
    return sorted(found)[-1][1]


def find_ayon_core_client(core_path=None):
    """Find the `client` folder of an ayon-core checkout.

    Order: `--core`, `AYON_CORE_ROOT`, the ayon-core of the AYON launcher
    this runs in (`ayon run`), an `ayon-core` folder next to this repository
    or next to any of its parent folders (worktrees).
    """
    for path in (core_path, os.environ.get("AYON_CORE_ROOT")):
        if path:
            client = os.path.join(path, "client")
            if not os.path.isdir(os.path.join(client, "ayon_core")):
                raise SystemExit(f"'{path}' is not an ayon-core checkout.")
            return client

    spec = importlib.util.find_spec("ayon_core")
    if spec and spec.submodule_search_locations:
        return os.path.dirname(list(spec.submodule_search_locations)[0])

    current = REPO_ROOT
    while True:
        parent = os.path.dirname(current)
        if parent == current:
            break
        client = os.path.join(parent, "ayon-core", "client")
        if os.path.isdir(os.path.join(client, "ayon_core")):
            return client
        current = parent
    raise SystemExit(
        "No ayon-core checkout found. Pass --core or set AYON_CORE_ROOT."
    )


def ensure_dependencies(python_version):
    """Install the test dependencies for Nuke's Python into a folder."""
    with open(REQUIREMENTS, "rb") as stream:
        requirements_hash = hashlib.sha256(stream.read()).hexdigest()

    target = os.path.join(DEPS_ROOT, "py" + python_version.replace(".", ""))
    stamp = os.path.join(target, ".requirements.sha256")
    if os.path.exists(stamp):
        with open(stamp) as stream:
            if stream.read().strip() == requirements_hash:
                return target

    uv = shutil.which("uv")
    if not uv:
        raise SystemExit("`uv` is needed to install the test dependencies.")
    if os.path.isdir(target):
        shutil.rmtree(target)
    _log(f"Installing test dependencies for Python {python_version}")
    subprocess.run(
        [
            uv,
            "pip",
            "install",
            "--quiet",
            "--python",
            python_version,
            "--target",
            target,
            "-r",
            REQUIREMENTS,
        ],
        check=True,
    )
    with open(stamp, "w") as stream:
        stream.write(requirements_hash)
    return target


def run(executable, test_paths, pytest_args, timeout):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    run_dir = tempfile.mkdtemp(prefix="nuke_tests_")
    log_path = os.path.join(run_dir, "pytest.log")
    result_path = os.path.join(run_dir, "result.json")

    env = dict(os.environ)
    env.update(
        {
            "NUKE_TEST_PATHS": os.pathsep.join(test_paths),
            "NUKE_PYTEST_ARGS": json.dumps(pytest_args),
            "NUKE_PYTEST_LOG": log_path,
            "NUKE_TEST_RESULT": result_path,
        }
    )
    command = [executable, "-t", BOOTSTRAP]
    _log("Starting: " + " ".join(command))
    nuke_output = open(os.path.join(run_dir, "nuke.log"), "w")
    process = subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        env=env,
        stdout=nuke_output,
        stderr=subprocess.STDOUT,
    )

    deadline = time.time() + timeout
    try:
        while process.poll() is None:
            if time.time() > deadline:
                _log(f"Timed out after {timeout} s, stopping Nuke.")
                process.kill()
                break
            time.sleep(0.5)
        process.wait()
    finally:
        nuke_output.close()
        try:
            with open(log_path, "r", errors="replace") as stream:
                sys.stdout.write(stream.read())
                sys.stdout.flush()
        except OSError:
            pass

    if not os.path.exists(result_path):
        _log(
            "Nuke exited without a test result (return code "
            f"{process.returncode}). Nuke output: "
            + os.path.join(run_dir, "nuke.log")
        )
        return 3

    with open(result_path) as stream:
        result = json.load(stream)
    exitcode = int(result["exitcode"])
    _log(f"pytest exit code {exitcode}, logs in {run_dir}")
    return exitcode


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    pytest_args = []
    if "--" in argv:
        index = argv.index("--")
        argv, pytest_args = argv[:index], argv[index + 1 :]

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--app", help="Nuke executable, .app or folder")
    parser.add_argument("--core", help="ayon-core checkout")
    parser.add_argument(
        "--python",
        help="Python version of the Nuke build (detected from --app)",
    )
    parser.add_argument(
        "--timeout", type=int, default=900, help="seconds (default 900)"
    )
    args = parser.parse_args(argv)

    executable = find_nuke_executable(args.app)
    version = _nuke_version(executable)
    python_version = args.python or PYTHON_BY_NUKE_MAJOR.get(
        version[0] if version else None
    )
    if not python_version:
        raise SystemExit("Unknown Nuke Python version, pass --python.")

    core_client = find_ayon_core_client(args.core)
    test_paths = [
        ensure_dependencies(python_version),
        core_client,
        os.path.join(core_client, "ayon_core", "vendor", "python"),
        os.path.join(REPO_ROOT, "client"),
    ]

    app_tag = os.path.basename(executable).replace(".exe", "")
    junit = os.path.join(RESULTS_DIR, f"junit-{app_tag}.xml")
    if not pytest_args:
        pytest_args = [NUKE_TESTS_DIR]
    pytest_args = pytest_args + ["--junitxml", junit]
    return run(executable, test_paths, pytest_args, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
