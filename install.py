import subprocess

subprocess.run(["uv", "sync"], cwd="backend", check=True)
subprocess.run(["npm", "install"], cwd="frontend", check=True)
