import subprocess
import sys

shell = sys.platform == "win32"
backend = subprocess.Popen(["uv", "run", "local_run.py"], cwd="backend", shell=shell)
frontend = subprocess.Popen(["npm", "run", "dev"], cwd="frontend", shell=shell)

backend.wait()
frontend.wait()
