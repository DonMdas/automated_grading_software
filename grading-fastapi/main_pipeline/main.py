import yaml
import subprocess
import os

def load_version():
    with open("main_pipeline/config.yaml", "r") as f:
        config = yaml.safe_load(f)
    return config.get("version")

def run_version(version):
    path = os.path.join("main_pipeline", version, "main.py")
    if not os.path.exists(path):
        print(f"Error: {path} not found.")
        return

    subprocess.run(["python", path], check=True)

if __name__ == "__main__":
    version = load_version()
    print(f"🔧 Running version: {version}")
    run_version(version)
