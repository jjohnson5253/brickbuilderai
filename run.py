"""Launches the backend and frontend dev servers together.

Each dev server is started via a wrapper (``uv run`` / ``npm run``) that
spawns its own child process (the real Python/Node process). If we only
ever signal the wrapper, the grandchild can survive as an orphan after the
terminal closes - which is how stale processes end up squatting on
ports 8002/3000. To avoid that, each process is started in its own process
group so we can terminate the *entire* tree, and cleanup is guaranteed via
signal handlers plus an ``atexit`` hook.
"""

import atexit
import os
import signal
import subprocess
import sys

IS_WINDOWS = sys.platform == "win32"

# On POSIX, start each child in a new session (os.setsid) so we can kill the
# whole process group with os.killpg, reaching grandchildren too. On
# Windows, use a new process group so CTRL_BREAK_EVENT can be delivered.
_popen_kwargs = (
    {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    if IS_WINDOWS
    else {"start_new_session": True}
)

processes: list[subprocess.Popen] = []


def _start(cmd, cwd):
    proc = subprocess.Popen(cmd, cwd=cwd, shell=IS_WINDOWS, **_popen_kwargs)
    processes.append(proc)
    return proc


def _terminate_all():
    for proc in processes:
        if proc.poll() is not None:
            continue  # already exited
        try:
            if IS_WINDOWS:
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(proc.pid, signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass

    for proc in processes:
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                if IS_WINDOWS:
                    proc.kill()
                else:
                    os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass


atexit.register(_terminate_all)


def _handle_signal(signum, frame):
    _terminate_all()
    sys.exit(0)


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


if __name__ == "__main__":
    backend = _start(["uv", "run", "local_run.py"], cwd="backend")
    frontend = _start(["npm", "run", "dev"], cwd="frontend")

    # Exit (and clean up both) as soon as either process stops on its own.
    while backend.poll() is None and frontend.poll() is None:
        try:
            backend.wait(timeout=1)
        except subprocess.TimeoutExpired:
            continue
