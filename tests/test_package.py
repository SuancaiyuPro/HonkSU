import hashlib
import importlib.util
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("honksu_package", ROOT / "tools/package.py")
PACKAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGE)


def elf(machine):
    header = bytearray(64)
    header[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<H", header, 18, machine)
    return bytes(header)


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="honksu-package-test-")
        self.directory = Path(self.temporary.name)
        self.core = self.directory / "honk-core"
        self.object = self.directory / "honk-ebpf.o"
        self.object.write_bytes(elf(247) + b".BTF\x00kernel-object-fixture")
        self.core.write_bytes(elf(183) + b"/system/bin/linker64\x00socket-identity\x00" + self.object.read_bytes())
        self.out = self.directory / "dist"

    def tearDown(self):
        self.temporary.cleanup()

    def test_missing_or_unembedded_object_cannot_be_labeled_as_ebpf_core(self):
        with self.assertRaisesRegex(ValueError, "requires its matching"):
            PACKAGE.build(self.core, self.out)
        self.core.write_bytes(elf(183) + b"/system/bin/linker64\x00ordinary-core")
        with self.assertRaisesRegex(ValueError, "does not embed"):
            PACKAGE.build(self.core, self.out, self.object)
        self.assertFalse(self.out.exists())

    def test_wrong_architecture_and_non_btf_objects_are_rejected(self):
        for value in [b"\x7fELF", elf(62) + b"/system/bin/linker64\x00", elf(183) + b"/lib/ld-linux-aarch64.so.1\x00"]:
            self.core.write_bytes(value)
            with self.assertRaises(ValueError):
                PACKAGE.build(self.core, self.out, self.object)
        self.core.write_bytes(elf(183) + b"/system/bin/linker64\x00")
        self.object.write_bytes(elf(247) + b"no-BTF")
        with self.assertRaisesRegex(ValueError, "BTF-bearing"):
            PACKAGE.build(self.core, self.out, self.object)

    def test_module_records_provenance_and_keeps_runtime_interception_disabled(self):
        PACKAGE.build(self.core, self.out, self.object)
        module = next(self.out.glob("*_arm64.zip"))
        metadata = json.loads((ROOT / "core.lock.json").read_text())
        with zipfile.ZipFile(module) as archive:
            props = dict(line.split("=", 1) for line in archive.read("core.prop").decode().splitlines())
            self.assertEqual(props["core_commit"], metadata["commit"])
            self.assertEqual(props["core_repository"], metadata["repository"])
            self.assertEqual(props["core_ebpf_compiled"], "1")
            self.assertEqual(props["core_android_interception"], "0")
            self.assertEqual(props["core_socket_identity_probe"], "1")
            self.assertEqual(props["core_sha256"], hashlib.sha256(archive.read("bin/honk-core")).hexdigest())
            self.assertIn("hotinstall.sh", archive.namelist())
            self.assertIn(metadata["commit"], archive.read("CORE_SOURCE.md").decode())
        for line in (self.out / "SHA256SUMS").read_text().splitlines():
            digest, name = line.split("  ")
            self.assertEqual(hashlib.sha256((self.out / name).read_bytes()).hexdigest(), digest)

    def test_old_core_cannot_be_labeled_as_supporting_identity_probe(self):
        self.core.write_bytes(elf(183) + b"/system/bin/linker64\x00" + self.object.read_bytes())
        with self.assertRaisesRegex(ValueError, "socket-identity"):
            PACKAGE.build(self.core, self.out, self.object)


if __name__ == "__main__":
    unittest.main()
