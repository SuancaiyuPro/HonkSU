#!/usr/bin/env python3
import json
import re
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
for path in (root / "module").rglob("*"):
    if path.is_file() and (path.suffix == ".sh" or path.name == "honksuctl"):
        subprocess.run(["sh", "-n", str(path)], check=True)
for path in (root / "module/webroot").glob("*.js"):
    subprocess.run(["node", "--check", str(path)], check=True)
properties = dict(line.split("=", 1) for line in (root / "module/module.prop").read_text().splitlines() if "=" in line)
assert re.fullmatch(r"[a-zA-Z][a-zA-Z0-9._-]+", properties["id"])
assert properties["versionCode"].isdigit()
assert (root / "module/webroot/index.html").is_file()
assert (root / "module/skip_mount").exists()
metadata = json.loads((root / "core.lock.json").read_text())
assert metadata["target"] == "aarch64-linux-android" and not metadata["ebpf"]
assert re.fullmatch(r"[a-f0-9]{40}", metadata["commit"])
print("Module structure, shell syntax, JavaScript syntax and core lock checks passed")
