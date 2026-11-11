![CertHub Logo](./icon.png)

# CertHub

面向宝塔 Linux 面板的多服务器证书分发与自动部署中心。

CertHub 直接纳管宝塔面板已经签发的证书，并按照客户端权限安全地分发到 Linux、Windows 服务器及 OpenWRT 设备。它不复制证书到数据库，也不要求额外部署 PHP、MySQL、Redis、Nginx 站点或独立 Web 服务。

## 当前版本

[CertHub 1.4.0](https://github.com/kot4ri/certhub/releases/tag/v1.4.0) 新增 OpenWRT 平台，支持新增、修改客户端的平台选择，并自动迁移旧数据库的平台约束。

| 插件 | Linux Agent | Windows Agent | OpenWRT Agent |
| --- | --- | --- | --- |
| 1.4.0 | 0.3.19 | 0.3.13 | 0.3.20 |

## 为什么使用 CertHub

当多台服务器需要使用同一张证书时，手工下载、上传和替换很容易遗漏。CertHub 将证书来源、客户端授权、同步计划和部署行为集中到宝塔面板中管理：

- 自动发现 `/www/server/panel/vhost/ssl/` 中的宝塔证书；
- 一台客户端可授权多张证书，授权可随时编辑、撤销或删除；
- 服务端证书未变化时不重复下载、写入、替换或重载服务；
- Agent 每 5 分钟同步服务端配置，并按照服务端下发的五段 crontab 表达式执行证书同步；
- 支持服务端向选中客户端下发立即拉取和 Agent 更新指令；
- 管理页面展示客户端系统、Agent 版本、在线状态、任务状态及操作日志；
- Linux、Windows 与 OpenWRT Agent 按平台独立分发和更新。

## 工作方式

```text
宝塔证书目录
      │ 实时读取并校验证书与私钥
      ▼
CertHub（宝塔 Flask Hook + SQLite）
      │ HTTPS + 独立客户端凭据 + 证书授权
      ├──────────────► Linux Agent
      ├──────────────► Windows Agent
      └──────────────► OpenWRT Agent（procd）
```

CertHub 通过宝塔启动 Hook 在面板自身地址注册 `/certhub-api`。管理页面使用宝塔登录态；Agent 使用每台设备独立的长期凭据。SQLite 仅保存证书元数据、客户端身份、授权、配置和日志，不保存证书或私钥正文。

## 客户端能力

### Linux

- 安装为 systemd 服务，程序位于 `/usr/local/sbin/certhub-agent`；
- 支持 CertHub 托管目录、自定义目录和宝塔标准证书目录；
- 可将证书注册到客户端宝塔证书夹；
- 可同步更新正在使用相同证书的网站；
- 网站证书只有在主体与完整 SAN 集合完全一致时才会替换；
- 支持固定的 Nginx、Apache 等服务重载配置。

通配符证书与单域名证书不会仅因域名覆盖关系而互相替换。例如，客户端网站当前使用单独签发的 `bpe.example.com` DV 证书时，服务端下发的 `*.example.com` 通配符证书不会替换它。

### Windows

- 支持一条 PowerShell 命令下载安装；
- EXE 自动申请管理员权限并注册 SYSTEM 计划任务；
- 默认下载到首次注册用户目录，也可由服务端指定自定义路径；
- 配置和长期凭据使用 DPAPI LocalMachine 保护；
- 不执行宝塔证书注册或虚拟主机替换。

### OpenWRT

- 使用 procd 管理常驻服务，支持开机启动；
- 安装器由 BusyBox `sh` 启动，通过 opkg 或 apk 安装 bash、精简 Python 和所需依赖，无需完整 Python 环境；
- 支持持久化托管目录和自定义下载目录，不提供客户端宝塔面板路径；
- 默认状态与证书保存在 `/etc/certhub-agent/state`，避免 `/var`、`/tmp` 重启清空导致丢失；
- 支持证书同步、配置更新、撤权清理、客户端撤销和 Agent 在线更新；
- 负责证书文件同步，目标服务的证书路径和重载方式需自行配置。

默认完整链和私钥分别位于 `/etc/certhub-agent/state/certificates/<id>/current/fullchain.pem` 与 `privkey.pem`。详细安装要求、服务命令和日志查看方式见 [OpenWRT Agent 说明](./client/openwrt/README.md)。

## 安装要求

- 宝塔 Linux 面板；
- 宝塔自带的 Python 3 环境；
- 系统已安装 OpenSSL；
- 面板已配置客户端可信的 HTTPS 证书；
- 客户端可以访问面板的 `/certhub-api` 路径。

## 安装

### 使用 Release 安装包

1. 从 [GitHub Releases](https://github.com/kot4ri/certhub/releases/latest) 下载 `certhub-<版本>.zip`；
2. 在宝塔面板中导入第三方插件安装包；
3. 安装完成后打开 CertHub，根据初次使用指引纳管证书并创建第一个客户端；
4. 在设置中确认客户端能够访问的宝塔 HTTPS 地址。

### 已安装版本升级

在 CertHub 管理页检查更新并执行升级。正式 Release 提供插件 ZIP、`.sha256` 校验文件和 `.sig` 数字签名，面板验证校验值及发布签名后才会安装。

1.4.0 会自动扩展旧数据库的平台约束，保留已有客户端、证书授权和配置。插件升级与客户端 Agent 更新是独立操作；需要更新代理时，在客户端管理中下发 Agent 更新指令。

### 从源码构建

```bash
git clone https://github.com/kot4ri/certhub.git
cd certhub
bash bin/build-package.sh
```

生成的安装包和 SHA-256 文件位于 `release/` 目录。构建脚本会拒绝打包数据库、密钥、令牌等运行数据。

## 客户端注册

在“客户端管理”中创建客户端，选择平台、允许使用的证书、部署目录、来源地址限制和同步计划。服务端会生成一次性安装命令：

- 注册令牌使用密码学安全随机数生成；
- 数据库只保存令牌的 SHA-256 哈希；
- 注册令牌 30 分钟后失效且只能成功使用一次；
- 注册完成后交换为该设备独立、可撤销的长期凭据。

OpenWRT 请以 root 在设备终端执行生成的安装命令，首次下载前需已有 `curl` 和可用的 HTTPS CA。新增或修改 OpenWRT 客户端时，只能选择托管证书目录或自定义下载目录；更换平台后，需要安装对应平台的代理。

来源限制可填写 IPv4、IPv6 或域名。填写域名时，服务端会在每次请求时解析其 A/AAAA 记录，只要任一解析地址与请求来源地址完全一致即可放行。

## 数据与文件

```text
/www/server/panel/plugin/certhub/        插件程序
/www/server/panel/hooks/certhub_route.py 宝塔路由 Hook
/www/server/certhub/certhub.db           SQLite 配置与审计数据库
```

取消纳管不会删除宝塔源证书。默认卸载也会保留 SQLite 数据，只有明确执行完全重置或带数据清理的卸载操作才会删除 CertHub 数据。

## 安全边界

- Agent 不会跳过 HTTPS 证书验证；
- 宝塔的域名限制、IP 白名单和入口访问策略仍然生效；
- 服务端只信任实际连接来源 IP，不接受客户端自行声明来源地址；
- 私钥仅在已授权客户端请求时从宝塔目录实时读取；
- 证书目录及文件不允许使用符号链接绕过路径限制；
- 分发前使用 OpenSSL 验证证书与私钥是否匹配；
- 数据库启用 SQLite WAL、外键约束，并使用 `0600` 权限保存。

## 项目文档

- [Linux Agent 说明](./client/linux/README.md)
- [Windows Agent 说明](./client/windows/README.md)
- [OpenWRT Agent 说明](./client/openwrt/README.md)

## License

本项目采用 [MIT License](./LICENSE) 开源。
