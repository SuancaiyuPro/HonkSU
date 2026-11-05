# honk core source and build provenance

The module includes `honk-core`, licensed GPL-3.0-only. Its complete corresponding source is the Android port at:

- Repository: https://github.com/SuancaiyuPro/honk
- Exact revision: `9e4fbe878a92183fb0be93380725daa4e9e98f32`
- Source tree: https://github.com/SuancaiyuPro/honk/tree/9e4fbe878a92183fb0be93380725daa4e9e98f32
- Source archive: https://github.com/SuancaiyuPro/honk/archive/9e4fbe878a92183fb0be93380725daa4e9e98f32.tar.gz
- Original project: https://github.com/daeuniverse/honk

Use the source's pinned compiler, Cargo.lock and patched dependencies. Build for `aarch64-linux-android` with Android NDK/API 35, `--no-default-features --features clash-api,rprx`, and the source's `ci/android-toolchain.cmake`. The exact build procedure is in this project's `.github/workflows/build.yml`. The per-package binary digest and source revision are recorded in `core.prop` and `bin/SHA256SUMS`.

This core has no real eBPF backend. HonkSU invokes it with `--mock-ebpf` for process and configuration testing. The module's start action does not enable Android traffic interception.

HonkSU's module scripts and WebUI are GPL-3.0-only. The KernelSU JavaScript bridge is invoked through its documented API; no external JavaScript or telemetry is loaded by the manager. KernelSU itself is a separate project: https://github.com/tiann/KernelSU.
