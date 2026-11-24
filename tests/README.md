# Tests inside Nuke

The tests in `tests/nuke` run in a real Nuke session in terminal mode
(`Nuke -t`), so no window opens. They are not part of CI: they need a Nuke
licence that allows terminal mode (not Non-Commercial) and are not in the
addon package.

## Run

```shell
python tests/run_nuke_tests.py
python tests/run_nuke_tests.py --app /Applications/Nuke16.1v1
python tests/run_nuke_tests.py -- tests/nuke/test_load_effects_expose_knobs.py -k update
```

With the AYON launcher, `ayon run tests/run_nuke_tests.py` uses its
ayon-core. Arguments after `--` go to pytest. The exit code is pytest's.

What the runner needs:

- **Nuke**: `--app` (an executable, `.app` bundle or install folder),
  `AYON_NUKE_EXECUTABLE`, or the newest Nuke 14 to 17 in the usual install
  folder. Tested with Nuke 15.2, 16.1 and 17.0.
- **ayon-core**: `--core`, `AYON_CORE_ROOT`, the launcher's ayon-core
  (`ayon run`), or an `ayon-core` checkout next to this repository (or next
  to a parent folder, for worktrees).
- **uv**: installs `requirements-nuke.txt` into `tests/.deps/` for the
  Python of the Nuke build, again when the file changes.

## How it works

`run_nuke_tests.py` starts `Nuke -t tests/nuke/bootstrap.py`. The bootstrap
adds the paths from `NUKE_TEST_PATHS` to `sys.path`, runs pytest with the
arguments from `NUKE_PYTEST_ARGS`, writes pytest's output to the log the
runner prints and exits with pytest's exit code. A JUnit report goes to
`tests/.results/`. Every test starts with an empty script
(`nuke.scriptClear()`), see `tests/nuke/conftest.py`.
