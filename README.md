# HonkSU

面向 KernelSU 的 **honk Android 核心管理模块**，首版使用 KernelSU 内置 WebUI。仓库：[SuancaiyuPro/HonkSU](https://github.com/SuancaiyuPro/HonkSU)。

## 当前状态

当前 `0.1.0-alpha.2` 接入新的 ARM64 honk eBPF 构建与原生热安装。**核心已编译真实 eBPF 后端，Android 透明 socket、路由标记及运行路径仍未适配完成；模块继续使用 `--mock-ebpf` 测试模式，不接管手机流量。** 当前没有 SOCKS5 / HTTP / TUN 入站，也没有独立 APK。TCP / UDP 端口用于 honk 自身的测试监听。

- WebUI：概览、订阅、入站设置、日志。
- 订阅：导入、移除 HTTP / HTTPS 链接，最多 32 个；生成 honk `.dae` 配置，由核心在启动时获取和解析，支持范围以 honk 为准。保存成功不表示已经下载或成功识别节点。
- 核心：测试启动、停止、重启、进程身份校验、启动失败日志、可选开机启动（默认关闭）。
- 热安装：使用官方 KernelSU 原生接口；原本运行中的测试核心更新后恢复运行，原本停止则保持停止。订阅、设置、认证令牌和开机自启设置均保留。
- 设置：测试监听端口、Clash API 端口、节点解析 DNS。Clash API 固定在 `127.0.0.1`，使用自动生成的随机令牌。
- 默认测试监听端口为 `12346`，Clash API 为 `9091`，避开其他代理常用的默认端口；仍可在入站页修改。
- 数据：保存在 `/data/adb/honksu`，更新模块不覆盖，卸载时默认保留，便于重新安装。
- 不修改系统分区，不添加 iptables、策略路由或 eBPF 接管规则。

## 设备范围与验证状态

打包目标为 ARM64、Android API 35 以上。用户目标设备为 Android 17 / SDK 37、4 KiB 页、6.12.69 Android 内核。核心已在 GitHub Actions 完成交叉编译；模块仍需要在真实 KernelSU 设备上安装、启动和联网验证。内核版本满足某个版本门槛不代表 eBPF 所需配置和权限已经可用。

## 安装与使用

1. 使用完整的 `HonkSU_0.1.0-alpha.2_arm64.zip`，不要把外层 Actions 下载 ZIP 或 `_source.zip` 当成安装包。
2. 在支持原生热安装的官方 KernelSU 管理器中安装模块。此版本要求安装器提供 `KSU_HAS_HOT_INSTALL=true`；旧框架会提示升级并终止安装。正常热安装无需重启，安装后重新打开模块 WebUI。
3. 在“订阅”页导入链接；在“入站”页保存端口和 DNS。
4. 在“概览”启动**测试核心**；更改配置后点击“重启核心并应用配置”。
5. 如果启动失败，在“日志”查看原因。“运行中”只表示进程存活，不代表代理或透明接管已可用。

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

`tests/ui-smoke.cjs` 是可选的界面冒烟检查，需要预先安装 Playwright 和 Chromium。它仅使用测试桥接，不接触真实 KernelSU。当前交付未完成浏览器视觉检查，亦未完成真机 WebUI 验证。

## 下一阶段

移植 honk 的 Android eBPF 后端与入站所需的 socket、网络命名空间、接口和路由流程，在实机上验证移动数据、Wi-Fi、DNS、上传和下载后，再开放真实透明接管选项。

## 许可

GPL-3.0-only。作者：SuancaiyuPro；实现由 ChatGPT 协助。honk 原作者及依赖的归属、许可继续保留。
