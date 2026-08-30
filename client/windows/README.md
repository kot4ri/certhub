# CertHub Windows Agent

Windows Agent 从 CertHub 服务端获取授权证书和客户端配置，适合普通 Windows 主机及 Windows Server。它不会注册宝塔证书，也不会修改网站或 Web 服务配置。

## 功能

- 使用一次性令牌完成客户端注册；
- 按服务端下发的计划同步多张证书；
- 证书内容未变化时不重复下载或写入；
- 支持用户目录和服务端指定的自定义目录；
- 每 5 分钟获取服务端配置和即时任务；
- 接收服务端下发的立即拉取、证书清理和 Agent 更新指令；
- 默认网络请求失败时自动使用 IPv4 重试；
- 上报主机名、Windows 系统信息、架构、Agent 版本和任务结果。

## 安装

在 CertHub 的“客户端管理”中创建 Windows 客户端，然后复制页面生成的 PowerShell 安装命令，以管理员身份执行。

安装程序会：

1. 下载带有服务端地址和一次性身份信息的 EXE；
2. 申请管理员权限；
3. 将程序安装到 `%ProgramData%\CertHub\certhub-agent.exe`；
4. 使用 DPAPI LocalMachine 保护客户端配置；
5. 创建以 SYSTEM 身份运行的 `CertHub Certificate Sync` 计划任务；
6. 注册成功后立即获取配置并执行首次同步。

## 文件与任务

```text
%ProgramData%\CertHub\certhub-agent.exe  Agent 主程序
%ProgramData%\CertHub\config.protected   DPAPI 加密配置
%ProgramData%\CertHub\state.json         同步状态
%ProgramData%\CertHub\agent.log          运行日志
%ProgramData%\CertHub\update.log         更新日志
```

“用户目录”模式由服务端下发，实际证书目录为首次安装用户的 `%USERPROFILE%\CertHub\certificates`。切换服务端下发的保存路径时，Agent 会清理此前由 CertHub 管理的旧目录。

## 从源码构建

构建环境需要 64 位 Windows、Python 和 PyInstaller。Agent 运行时只使用 Python 标准库，PyInstaller 仅为构建依赖：

```powershell
py -m pip install pyinstaller
```

在 `client\windows` 目录执行：

```powershell
pyinstaller --onefile --noconsole --name certhub-agent windows_agent.py
```

生成文件位于 `dist\certhub-agent.exe`。将其上传到服务端项目的 `client/windows/certhub-agent.exe` 后，服务端即可生成一键安装命令和下发更新。

## 命令参数

```text
--sync              立即执行一次同步
--install API TOKEN 执行完整静默安装
--enroll API TOKEN  使用一次性令牌注册
```

通常无需手工使用这些参数，应优先使用 CertHub 页面生成的安装命令。

## 更新

服务端下发更新指令后，Agent 会下载 Windows 更新包、验证 SHA-256、通过独立 SYSTEM 更新任务原子替换主程序，并在新版启动回报后标记更新完成。

Windows 与 Linux Agent 独立发布和更新，服务端只会向对应平台下发更新包。

## 故障排查

检查计划任务：

```powershell
Get-ScheduledTask -TaskName "CertHub Certificate Sync"
Get-ScheduledTaskInfo -TaskName "CertHub Certificate Sync"
```

查看最近日志：

```powershell
Get-Content "$env:ProgramData\CertHub\agent.log" -Tail 100
Get-Content "$env:ProgramData\CertHub\update.log" -Tail 100
```

Agent 不会跳过 HTTPS 证书验证。连接失败时，请同时检查服务端证书、宝塔域名限制、IP 白名单和网络防火墙。
