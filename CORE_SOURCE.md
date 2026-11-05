# honk core source and build provenance

The module includes `honk-core`, licensed GPL-3.0-only. Its complete corresponding source is the Android port at:

- Repository: https://github.com/SuancaiyuPro/honk-for-Android
- Exact revision: `84c41144e8aa0db1a93094e0a8568e3cc6fdbdf2`
- Source tree: https://github.com/SuancaiyuPro/honk-for-Android/tree/84c41144e8aa0db1a93094e0a8568e3cc6fdbdf2
- Source archive: https://github.com/SuancaiyuPro/honk-for-Android/archive/84c41144e8aa0db1a93094e0a8568e3cc6fdbdf2.tar.gz
- Original project: https://github.com/daeuniverse/honk

Use the source's pinned compiler, Cargo.lock and patched dependencies. First build its standalone eBPF object with the pinned nightly and checksum-verified bpf-linker, preserving `.BTF` and the exact `.toolchain` sidecar. Then build for `aarch64-linux-android` with Android NDK/API 35, `--no-default-features --features clash-api,rprx,ebpf`, and the source's `ci/android-toolchain.cmake`. The exact build procedure is in this project's `.github/workflows/build.yml`. Packaging verifies that the supplied Android binary contains the matching BTF-bearing kernel object. Binary/object digests, source revision, features and runtime readiness are recorded in `core.prop`; the executable checksum is also in `bin/SHA256SUMS`.

This core compiles the real eBPF backend. Its Android transparent-socket, network-mark and runtime-path integration remains incomplete. HonkSU explicitly invokes it with `--mock-ebpf` for process and configuration testing, including after hot installation. Compiled eBPF support is separate from Android traffic interception readiness; the module does not enable interception.

HonkSU's module scripts and WebUI are GPL-3.0-only. The KernelSU JavaScript bridge is invoked through its documented API; no external JavaScript or telemetry is loaded by the manager. KernelSU itself is a separate project: https://github.com/tiann/KernelSU.
