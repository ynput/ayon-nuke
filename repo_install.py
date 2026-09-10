import subprocess


def main():
    subprocess.run(
        ["git", "config", "core.hooksPath", ".githooks"],
        check=True,
    )
