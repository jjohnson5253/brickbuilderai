import signal
import subprocess
import sys

signal.signal(signal.SIGINT, signal.SIG_IGN)
shell = sys.platform == "win32"
subprocess.run(["uv", "sync", "--no-progress"], cwd="backend", check=True, shell=shell)
subprocess.run(["npm", "install"], cwd="frontend", check=True, shell=shell)
