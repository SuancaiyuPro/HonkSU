import base64
import fcntl
import hashlib
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
        self.trash = self.root / "hot-install-trash"
        self.trash.mkdir()
        shutil.copytree(ROOT / "module", self.module)
        (self.module / "bin").mkdir(exist_ok=True)
        shutil.copy2(self.fixture, self.module / "bin/honk-core")
        digest = hashlib.sha256(self.fixture.read_bytes()).hexdigest()
        (self.module / "bin/SHA256SUMS").write_text(f"{digest}  honk-core\n")
        self.env = dict(os.environ, HONKSU_TEST_MODE="1", HONKSU_TEST_DATA=str(self.data), HONKSU_TEST_PROC_ROOT=str(self.proc), HONKSU_TEST_HOT_TRASH_ROOT=str(self.trash))

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

    def stash_module(self, name="honksu.123456789"):
        archived = self.trash / name
        self.module.rename(archived)
        shutil.copytree(archived, self.module)
        return archived

    def test_hot_install_replaces_archived_core_and_preserves_data(self):
        self.add()
        self.run_ctl("start")
        previous = self.status()["pid"]
        secret = (self.data / "settings/api_secret").read_bytes()
        self.stash_module()
        self.assertEqual(self.status()["pid"], previous)
        self.assertEqual(self.status()["running_core_current"], "0")
        self.run_ctl("hot-install")
        state = self.status()
        self.assertEqual(state["running"], "1")
        self.assertNotEqual(state["pid"], previous)
        self.assertEqual(state["running_core_current"], "1")
        self.assertEqual(state["hot_install"], "complete")
        self.assertEqual(state["autostart"], "0")
        self.assertEqual(state["providers"], "1")
        self.assertEqual((self.data / "settings/api_secret").read_bytes(), secret)
        self.assertFalse((self.proc / previous / "stat").exists())

    def test_hot_install_preserves_stopped_state_even_with_autostart(self):
        self.run_ctl("settings", "test", "12346", "9091", "223.5.5.5:53", "1")
        self.run_ctl("hot-install")
        self.assertEqual(self.status()["running"], "0")
        self.assertEqual(self.status()["autostart"], "1")

    def test_first_hot_install_does_not_start_core_or_enable_autostart(self):
        result = subprocess.run(["sh", str(self.module / "hotinstall.sh")], env=self.env, text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.status()["running"], "0")
        self.assertEqual(self.status()["autostart"], "0")

    def test_failed_new_binary_keeps_archived_process_running(self):
        self.run_ctl("start")
        previous = self.status()["pid"]
        self.stash_module()
        self.env["HONKSU_TEST_CORE_FAIL_VERSION"] = "1"
        result = self.run_ctl("hot-install", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.status()["pid"], previous)
        self.assertEqual(self.status()["hot_install"], "failed")

    def test_foreign_archive_name_is_not_accepted_as_owned(self):
        self.run_ctl("start")
        previous = self.status()["pid"]
        archived = self.stash_module("another-module.123")
        try:
            self.run_ctl("hot-install")
            self.assertEqual(self.status()["running"], "0")
            self.assertTrue((self.proc / previous / "stat").exists())
        finally:
            self.module.rename(self.root / "new-module")
            archived.rename(self.module)
            self.run_ctl("stop")

    def test_real_backend_metadata_cannot_enable_interception(self):
        (self.module / "core.prop").write_text("core_ebpf_compiled=1\ncore_android_interception=0\n")
        self.run_ctl("start")
        state = self.status()
        self.assertEqual(state["core_ebpf_compiled"], "1")
        self.assertEqual(state["ebpf_available"], "0")
        argv = (self.proc / state["pid"] / "cmdline").read_bytes().split(b"\0")
        self.assertIn(b"--mock-ebpf", argv)

    def test_hot_install_waits_for_an_existing_controller_operation(self):
        self.status()
        with (self.data / "run/controller.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            process = subprocess.Popen(["sh", str(self.module / "scripts/control.sh"), "hot-install"], env=self.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(0.15)
            self.assertIsNone(process.poll())
            fcntl.flock(lock, fcntl.LOCK_UN)
            stdout, stderr = process.communicate(timeout=20)
        self.assertEqual(process.returncode, 0, stderr)
        self.assertIn("Hot installation complete", stdout)

    def run_installer(self, supported):
        script = '''
          abort() { printf '%s\\n' "$*" >&2; exit 1; }
          ui_print() { printf '%s\\n' "$*"; }
          getprop() { printf 'arm64-v8a\\n'; }
          set_perm() { :; }
          set_perm_recursive() { :; }
          . "$MODPATH/customize.sh"
          printf 'request=%s script=%s\\n' "$MODULE_HOT_INSTALL_REQUEST" "$MODULE_HOT_RUN_SCRIPT"
        '''
        env = dict(self.env, KSU="true", KSU_HAS_HOT_INSTALL="true" if supported else "false", MODPATH=str(self.module), API="37")
        return subprocess.run(["sh", "-c", script], env=env, text=True, capture_output=True, timeout=10)

    def test_installer_requests_native_hot_installation(self):
        result = self.run_installer(True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("request=true script=hotinstall.sh", result.stdout)

    def test_installer_rejects_missing_framework_support(self):
        result = self.run_installer(False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Update official KernelSU", result.stderr)


if __name__ == "__main__":
    unittest.main()
