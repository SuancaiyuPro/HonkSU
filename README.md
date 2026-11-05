# HonkSU

面向 KernelSU 的 **honk Android 核心管理模块**，首版使用 KernelSU 内置 WebUI。仓库：[SuancaiyuPro/HonkSU](https://github.com/SuancaiyuPro/HonkSU)。

## 当前状态

首版是核心测试版，包含 ARM64 honk 原生程序与管理界面。**Android eBPF 透明接管还没有实现，安装和启动此模块不会让手机流量自动走代理。** 当前没有 SOCKS5 / HTTP / TUN 入站，也没有独立 APK。TCP / UDP 端口用于 honk 自身的测试监听。

- WebUI：概览、订阅、入站设置、日志。
- 订阅：导入、移除 HTTP / HTTPS 链接，最多 32 个；生成 honk `.dae` 配置，由核心在启动时获取和解析，支持范围以 honk 为准。保存成功不表示已经下载或成功识别节点。
- 核心：测试启动、停止、重启、进程身份校验、启动失败日志、可选开机启动（默认关闭）。
- 设置：测试监听端口、Clash API 端口、节点解析 DNS。Clash API 固定在 `127.0.0.1`，使用自动生成的随机令牌。
- 默认测试监听端口为 `12346`，Clash API 为 `9091`，避开其他代理常用的默认端口；仍可在入站页修改。
- 数据：保存在 `/data/adb/honksu`，更新模块不覆盖，卸载时默认保留，便于重新安装。
- 不修改系统分区，不添加 iptables、策略路由或 eBPF 接管规则。

## 设备范围与验证状态

打包目标为 ARM64、Android API 35 以上。用户目标设备为 Android 17 / SDK 37、4 KiB 页、6.12.69 Android 内核。核心已在 GitHub Actions 完成交叉编译；模块仍需要在真实 KernelSU 设备上安装、启动和联网验证。内核版本满足某个版本门槛不代表 eBPF 所需配置和权限已经可用。

## 安装与使用

1. 使用完整的 `HonkSU_0.1.0-alpha.1_arm64.zip`，不要把 GitHub 源码 ZIP 当成安装包。
2. 在 KernelSU 管理器中安装模块，重启后打开模块的 WebUI。
3. 在“订阅”页导入链接；在“入站”页保存端口和 DNS。
4. 在“概览”启动**测试核心**；更改配置后点击“重启核心并应用配置”。
5. 如果启动失败，在“日志”查看原因。“运行中”只表示进程存活，不代表代理或透明接管已可用。

WebUI 不在浏览器中执行 Root 操作，也不通过网络提供管理服务。请从 KernelSU 打开。订阅 URL 和配置以明文保存在 Root 私有目录中；日志界面会隐藏 HTTP(S) URL，分享日志前仍应检查节点信息。

## 构建

核心版本固定在 `core.lock.json`。`.github/workflows/build.yml` 会校验管理器与脚本，再从固定版本源码构建 Android honk 并打包模块。

本地已有 Android 核心时：

```sh
python3 tools/package.py --core /absolute/path/to/honk-core --out dist
```

输出安装包、模块源码包和 `SHA256SUMS`。核心二进制不提交到 Git；核心的完整对应源码和构建说明见 [CORE_SOURCE.md](CORE_SOURCE.md)。

## 验证

```sh
node --test tests/domain.test.cjs
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 tools/check.py
```

测试覆盖订阅/配置输入、命令注入防护、错误与重复订阅、进程启停、PID 误认、配置生效提示及模块结构；不模拟成 Android 真机或真实 eBPF 验证。

`tests/ui-smoke.cjs` 是可选的界面冒烟检查，需要预先安装 Playwright 和 Chromium。它仅使用测试桥接，不接触真实 KernelSU。当前交付未完成浏览器视觉检查，亦未完成真机 WebUI 验证。

## 下一阶段

移植 honk 的 Android eBPF 后端与入站所需的 socket、网络命名空间、接口和路由流程，在实机上验证移动数据、Wi-Fi、DNS、上传和下载后，再开放真实透明接管选项。

## 许可

GPL-3.0-only。作者：SuancaiyuPro；实现由 ChatGPT 协助。honk 原作者及依赖的归属、许可继续保留。
