import subprocess

subprocess.run(["uv", "sync", "--no-progress"], cwd="backend", check=True)
subprocess.run(["npm", "install"], cwd="frontend", check=True)
