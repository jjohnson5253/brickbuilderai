import subprocess

backend = subprocess.Popen(["uv", "run", "local_run.py"], cwd="backend")
frontend = subprocess.Popen(["npm", "run", "dev"], cwd="frontend")

backend.wait()
frontend.wait()
