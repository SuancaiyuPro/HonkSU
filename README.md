# HonkSU

面向 KernelSU 的 **honk Android 核心管理模块**，首版使用 KernelSU 内置 WebUI。仓库：[SuancaiyuPro/HonkSU](https://github.com/SuancaiyuPro/HonkSU)。

## 当前状态

当前 `0.1.0-alpha.3` 固定使用 `c4956ef` 核心，新增 WebUI 一键隔离 eBPF 验证，保留原生热安装。**私有网络中的 socket 身份旁路已通过目标手机验证；生产 socket 登记及完整转发仍需接入，模块继续使用 `--mock-ebpf` 测试模式，不接管手机流量。** 当前没有 SOCKS5 / HTTP / TUN 入站，也没有独立 APK。TCP / UDP 端口用于 honk 自身的测试监听。

- WebUI：概览、订阅、入站设置、日志。
- 订阅：导入、移除 HTTP / HTTPS 链接，最多 32 个；生成 honk `.dae` 配置，由核心在启动时获取和解析，支持范围以 honk 为准。保存成功不表示已经下载或成功识别节点。
- 核心：测试启动、停止、重启、进程身份校验、启动失败日志、可选开机启动（默认关闭）。
- 隔离验证：手动检查透明监听、BTF/maps、验证器、TCX 和 socket 身份旁路的真实报文正反例，最长 45 秒。结果与核心摘要及本次开机绑定，换核心或重启后提示重新验证。此通过状态不表示完整透明代理可用。
- 热安装：使用官方 KernelSU 原生接口；原本运行中的测试核心更新后恢复运行，原本停止则保持停止。订阅、设置、认证令牌和开机自启设置均保留。
- 设置：测试监听端口、Clash API 端口、节点解析 DNS。Clash API 固定在 `127.0.0.1`，使用自动生成的随机令牌。
- 默认测试监听端口为 `12346`，Clash API 为 `9091`，避开其他代理常用的默认端口；仍可在入站页修改。
- 数据：保存在 `/data/adb/honksu`，更新模块不覆盖，卸载时默认保留，便于重新安装。
- 不修改系统分区，不添加 iptables、策略路由或 eBPF 接管规则。

## 设备范围与验证状态

打包目标为 ARM64、Android API 35 以上。目标手机为 Android 17 / SDK 37、4 KiB 页、6.12.69 Android 内核。已在手机临时模块和数据目录中验证隔离探针、真实核心测试进程启停、Clash API 认证，以及热安装控制器的运行状态恢复；没有替换手机已安装模块。完整 KernelSU 管理器安装及 WebView 内的本版交互仍需验证。内核版本满足门槛不代表所有 eBPF 路径均已可用。

## 安装与使用

1. 使用完整的 `HonkSU_0.1.0-alpha.3_arm64.zip`，不要把外层 Actions 下载 ZIP 或 `_source.zip` 当成安装包。
2. 在支持原生热安装的官方 KernelSU 管理器中安装模块。此版本要求安装器提供 `KSU_HAS_HOT_INSTALL=true`；旧框架会提示升级并终止安装。正常热安装无需重启，安装后重新打开模块 WebUI。
3. 在“订阅”页导入链接；在“入站”页保存端口和 DNS。
4. 在“概览”启动**测试核心**；更改配置后点击“重启核心并应用配置”。
5. 如果启动失败，在“日志”查看原因。“运行中”只表示进程存活，不代表代理或透明接管已可用。
6. 在“概览”的 eBPF 能力验证卡片中点击“运行隔离验证”。保持 SELinux Enforcing；运行完成后查看结果。验证不会自动在开机或热安装时执行，也不改变现有订阅和启动设置。

终端也可执行 `/data/adb/modules/honksu/scripts/honksuctl probe`，再用 `probe-log` 查看详细输出。日志和状态保存在 `/data/adb/honksu/logs/probe.log` 与 `/data/adb/honksu/run/probe.status`。验证命令不接受额外参数；服务启停和验证使用同一控制锁，防止同时操作。

WebUI 不在浏览器中执行 Root 操作，也不通过网络提供管理服务。请从 KernelSU 打开。订阅 URL 和配置以明文保存在 Root 私有目录中；日志界面会隐藏 HTTP(S) URL，分享日志前仍应检查节点信息。

KernelSU 会把旧模块移到自己的热安装暂存目录，模块通过 PID、进程启动时间和限定的本模块程序路径识别旧进程，再停止并恢复测试核心。新程序无法执行时保留旧进程并记录失败；恢复失败会在管理器中显示。KernelSU 在安全模式、目录替换失败等情况下仍可能回退到重启生效，以安装器输出为准。框架即使热安装脚本失败也可能报告模块已安装，因此请同时检查安装日志和管理器状态。此行为遵循 [官方热安装接口](https://kernelsu.org/guide/module.html#hot-install)。

## 构建

核心版本固定在 `core.lock.json`。`.github/workflows/build.yml` 会校验管理器与脚本，再从固定版本源码构建 Android honk 并打包模块。

本地已有 Android 核心时：

```sh
python3 tools/package.py --core /absolute/path/to/honk-core --ebpf-object /absolute/path/to/honk-ebpf --out dist
```

输出安装包、模块源码包和 `SHA256SUMS`。核心二进制不提交到 Git；核心的完整对应源码和构建说明见 [CORE_SOURCE.md](CORE_SOURCE.md)。

## 验证

```sh
node --test tests/domain.test.cjs
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 tools/check.py
```

测试覆盖订阅/配置输入、命令注入防护、进程启停、PID 误认、热安装目录替换与状态恢复、安装器能力检查、BTF 对象与核心对应性及模块结构；不模拟成 Android 真机或真实 eBPF 验证。热安装的进程测试使用普通 C 测试程序和临时目录，仍须在真实 KernelSU 上验证此版本。

`tests/ui-smoke.cjs` 是界面冒烟检查，使用 Playwright 和 Chromium，或以 `HONKSU_TEST_BROWSER_CHANNEL=msedge` 选择本机 Edge。它只使用测试桥接，不接触真实 KernelSU。本版已在 393px 手机宽度下检查浅色与深色界面、诊断成功/失败/过期、订阅导入和核心启停；这不替代真实 KernelSU WebView 验证。

热安装的锁等待兼容不支持 `flock -w` 的 KernelSU BusyBox，采用最多约十秒的非阻塞重试；不会因缺少该选项直接报告安装恢复失败。

## 下一阶段

移植 honk 的 Android eBPF 后端与入站所需的 socket、网络命名空间、接口和路由流程，在实机上验证移动数据、Wi-Fi、DNS、上传和下载后，再开放真实透明接管选项。

## 许可

GPL-3.0-only。作者：SuancaiyuPro；实现由 ChatGPT 协助。honk 原作者及依赖的归属、许可继续保留。
