import base64
import fcntl
import os
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix="honksu-fixture-")
        cls.fixture = Path(cls.build.name) / "honk-core"
        subprocess.run(["cc", "-O2", str(ROOT / "tests/fake_core.c"), "-o", str(cls.fixture)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="honksu-test-")
        self.root = Path(self.directory.name)
        self.module = self.root / "module"
        self.data = self.root / "data"
        self.proc = self.root / "proc"
        self.proc.mkdir()
        shutil.copytree(ROOT / "module", self.module)
        (self.module / "bin").mkdir(exist_ok=True)
        shutil.copy2(self.fixture, self.module / "bin/honk-core")
        self.env = dict(os.environ, HONKSU_TEST_MODE="1", HONKSU_TEST_DATA=str(self.data), HONKSU_TEST_PROC_ROOT=str(self.proc))

    def tearDown(self):
        self.run_ctl("stop", check=False)
        self.directory.cleanup()

    def run_ctl(self, *args, check=True):
        result = subprocess.run(["sh", str(self.module / "scripts/control.sh"), *args], env=self.env, capture_output=True, text=True, timeout=20)
        if check and result.returncode:
            self.fail(f"controller failed: {result.stderr}")
        return result

    @staticmethod
    def encoded(value):
        return base64.b64encode(value.encode()).decode()

    def add(self, url="https://example.com/sub?token=secret&key=x", name="主订阅", check=True):
        return self.run_ctl("add", self.encoded(name), self.encoded(url), check=check)

    def status(self):
        return dict(line.split("=", 1) for line in self.run_ctl("status").stdout.splitlines())

    def test_initial_state_does_not_enable_interception_or_autostart(self):
        data = self.status()
        self.assertEqual(data["running"], "0")
        self.assertEqual(data["ebpf_available"], "0")
        self.assertEqual(data["autostart"], "0")
        self.assertEqual(len((self.data / "settings/api_secret").read_text().strip()), 48)

    def test_subscription_roundtrip_and_config_without_direct_fallback(self):
        self.add()
        identifier, name, url = self.run_ctl("providers").stdout.strip().split("\t")
        self.assertEqual(identifier, "p1")
        self.assertEqual(base64.b64decode(name).decode(), "主订阅")
        self.assertEqual(base64.b64decode(url).decode(), "https://example.com/sub?token=secret&key=x")
        config = (self.data / "config/config.dae").read_text()
        self.assertIn("p1: 'https://example.com/sub?token=secret&key=x'", config)
        self.assertIn("fallback: PROXY", config)
        self.assertNotIn("fallback: direct", config)
        self.assertIn("external_controller: '127.0.0.1:9091'", config)
        self.assertEqual((self.data / "config/config.dae").stat().st_mode & 0o777, 0o600)

    def test_invalid_subscription_cannot_inject_config(self):
        for url in ["file:///data/a", "https://example.com/'\n}\nrouting { fallback: direct }", "https://example.com/sub\ninjected", "https://example.com/a b", "https://example.com/sub\rnode"]:
            self.assertNotEqual(self.add(url, check=False).returncode, 0, url)
        self.assertEqual(self.status()["providers"], "0")

    def test_shell_metacharacters_are_data(self):
        marker = self.root / "injected"
        url = f"https://example.com/$(touch%20{marker})?token=a;b"
        self.add(url)
        self.assertFalse(marker.exists())
        self.assertIn(url, (self.data / "config/config.dae").read_text())

    def test_duplicate_and_invalid_base64_are_rejected(self):
        self.add()
        self.assertNotEqual(self.add(check=False).returncode, 0)
        self.assertNotEqual(self.run_ctl("add", "***", "***", check=False).returncode, 0)
        self.assertEqual(self.status()["providers"], "1")

    def test_removal_cannot_escape_provider_directory(self):
        self.add()
        self.assertNotEqual(self.run_ctl("remove", "p1/../../settings/api_secret", check=False).returncode, 0)
        self.assertTrue((self.data / "settings/api_secret").exists())
        self.run_ctl("remove", "p1")
        self.assertIn("fallback: block", (self.data / "config/config.dae").read_text())

    def test_settings_validate_before_writing(self):
        self.status()
        for args in [("ebpf", "12345", "9090", "1.1.1.1:53", "0"), ("test", "9090", "9090", "1.1.1.1:53", "0"), ("test", "12345", "9090", "999.1.1.1:53", "0")]:
            self.assertNotEqual(self.run_ctl("settings", *args, check=False).returncode, 0)
        self.assertEqual(self.status()["port"], "12346")
        self.run_ctl("settings", "test", "12346", "9091", "1.1.1.1:53", "1")
        self.assertEqual(self.status()["port"], "12346")
        self.assertEqual(self.status()["autostart"], "1")

    def test_start_stop_and_lock_release(self):
        self.run_ctl("start")
        self.assertEqual(self.status()["running"], "1")
        self.assertEqual(self.status()["pending_restart"], "0")
        self.run_ctl("stop")
        self.assertEqual(self.status()["running"], "0")

    def test_config_changes_require_restart(self):
        self.run_ctl("start")
        self.add()
        self.assertEqual(self.status()["pending_restart"], "1")
        self.run_ctl("restart")
        self.assertEqual(self.status()["running"], "1")
        self.assertEqual(self.status()["pending_restart"], "0")

    def test_foreign_pid_is_not_signalled(self):
        self.status()
        foreign = self.root / "foreign-core"
        shutil.copy2(self.fixture, foreign)
        process = subprocess.Popen([str(foreign)], env=self.env, stdout=subprocess.DEVNULL)
        try:
            record = self.proc / str(process.pid) / "stat"
            for _ in range(30):
                if record.exists(): break
                time.sleep(0.05)
            fields = record.read_text().rsplit(") ", 1)[1].split()
            (self.data / "run/core.pid").write_text(f"{process.pid}:{fields[19]}\n")
            self.assertEqual(self.status()["running"], "0")
            self.run_ctl("stop")
            self.assertIsNone(process.poll())
        finally:
            process.terminate()
            process.wait(timeout=3)

    def test_stale_start_time_does_not_match_a_live_core(self):
        self.run_ctl("start")
        original = (self.data / "run/core.pid").read_text()
        pid = original.split(":")[0]
        (self.data / "run/core.pid").write_text(f"{pid}:1\n")
        self.assertEqual(self.status()["running"], "0")
        (self.data / "run/core.pid").write_text(original)

    def test_control_lock_rejects_concurrent_mutation(self):
        self.status()
        with (self.data / "run/controller.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            result = self.add(check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("in progress", result.stderr)

    def test_log_display_masks_urls(self):
        self.status()
        (self.data / "logs/core.log").write_text("fetch https://example.com/?token=secret failed\n")
        log = self.run_ctl("logs").stdout
        self.assertNotIn("token=secret", log)
        self.assertIn("[subscription URL]", log)

    def test_boot_does_not_start_without_opt_in(self):
        self.run_ctl("boot")
        self.assertEqual(self.status()["running"], "0")


if __name__ == "__main__":
    unittest.main()
