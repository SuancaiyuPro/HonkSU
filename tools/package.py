#!/usr/bin/env python3
"""Package the KernelSU module from an explicitly supplied Android core."""
import argparse
import hashlib
import json
import shutil
import struct
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write_zip(source, target):
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source).as_posix())


def build(core, output):
    metadata = json.loads((ROOT / "core.lock.json").read_text())
    binary = core.read_bytes()
    if binary[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", binary, 18)[0] != 183:
        raise ValueError("The supplied core must be an ARM64 little-endian ELF executable")
    if b"/system/bin/linker64\x00" not in binary:
        raise ValueError("The supplied core must use the Android linker")
    digest = hashlib.sha256(binary).hexdigest()
    properties = dict(line.split("=", 1) for line in (ROOT / "module/module.prop").read_text().splitlines() if "=" in line)
    version = properties["version"]
    output.mkdir(parents=True, exist_ok=True)
    destination = output / f"HonkSU_{version}_arm64.zip"
    with tempfile.TemporaryDirectory(prefix="honksu-package-") as directory:
        stage = Path(directory) / "module"
        shutil.copytree(ROOT / "module", stage)
        (stage / "bin").mkdir(exist_ok=True)
        shutil.copy2(core, stage / "bin/honk-core")
        (stage / "bin/honk-core").chmod(0o755)
        (stage / "bin/SHA256SUMS").write_text(f"{digest}  honk-core\n")
        (stage / "core.prop").write_text(f"core_commit={metadata['commit']}\ncore_target={metadata['target']}\ncore_api={metadata['api']}\ncore_sha256={digest}\n")
        shutil.copy2(ROOT / "LICENSE", stage / "LICENSE")
        shutil.copy2(ROOT / "CORE_SOURCE.md", stage / "CORE_SOURCE.md")
        write_zip(stage, destination)
    source_zip = output / f"HonkSU_{version}_source.zip"
    with zipfile.ZipFile(source_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(ROOT.rglob("*")):
            relative = path.relative_to(ROOT)
            if not path.is_file() or set(relative.parts) & {".git", ".build", "dist", "__pycache__", "node_modules"}:
                continue
            if relative.as_posix() == "module/bin/honk-core":
                continue
            archive.write(path, Path("HonkSU", relative).as_posix())
    hashes = [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in (destination, source_zip)]
    (output / "SHA256SUMS").write_text("\n".join(hashes) + "\n")
    print(json.dumps({"module": str(destination.resolve()), "source": str(source_zip.resolve()), "core_sha256": digest}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    options = parser.parse_args()
    build(options.core.resolve(), options.out.resolve())
