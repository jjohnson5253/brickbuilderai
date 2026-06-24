import subprocess
import sys

shell = sys.platform == "win32"
subprocess.run(["uv", "sync"], cwd="backend", check=True, shell=shell)
subprocess.run(["npm", "install"], cwd="frontend", check=True, shell=shell)
