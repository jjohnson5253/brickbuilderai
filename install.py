import signal
import subprocess

signal.signal(signal.SIGINT, signal.SIG_IGN)
subprocess.run(["uv", "sync", "--no-progress"], cwd="backend", check=True)
subprocess.run(["npm", "install"], cwd="frontend", check=True)
