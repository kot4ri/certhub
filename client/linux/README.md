# CertHub Linux Agent

Linux Agent 以 systemd 服务运行，从 CertHub 服务端获取授权证书和客户端配置，并按照服务端策略部署证书。

## 功能

- 使用一次性令牌完成客户端注册；
- 安装为系统服务，不创建独立 Agent 工作目录；
- 按服务端下发的五段 crontab 表达式调度证书同步；
- 每 5 分钟获取配置和即时任务；
- 证书内容未变化时不重复下载、写入、注册、替换网站证书或重载服务；
- 支持托管证书目录、自定义目录和宝塔标准证书目录；
- 支持注册客户端宝塔证书夹；
- 支持更新正在使用完全相同证书的网站；
- 接收立即拉取、证书清理和 Agent 更新指令；
- 默认网络或 IPv6 请求失败时使用 IPv4 重试；
- 支持 AlmaLinux、Rocky Linux、Ubuntu、Debian 及其他常见 systemd 发行版。

## 安装

在 CertHub 的“客户端管理”中创建 Linux 客户端，复制页面生成的一行安装命令，并在目标服务器终端执行。

安装脚本会：

1. 下载 Agent 和 systemd 服务文件；
2. 将程序安装到 `/usr/local/sbin/certhub-agent`；
3. 将受保护配置写入 `/etc/certhub/`；
4. 注册并启动 `certhub-agent.service`；
5. 完成注册后立即获取配置并执行首次证书同步。

## 运行要求

- Python 3；
- systemd；
- OpenSSL；
- 能够通过可信 HTTPS 访问 CertHub 服务端。

Agent 使用 Python 标准库，不需要安装 pip 包。

## 部署模式

### 服务托管目录

证书保存在 CertHub 管理的系统目录中，适合由其他服务引用固定路径。

### 自定义目录

证书写入服务端配置的绝对路径。修改路径时，Agent 会清理此前由 CertHub 管理的旧目录。

### 宝塔面板

证书写入客户端宝塔的标准证书目录并完成证书注册。启用网站自动更新后，Agent 只替换当前证书主体和完整 SAN 集合与下发证书完全一致的网站。

例如，网站当前使用单独签发的 `bpe.example.com` 证书时，不会被 `*.example.com` 通配符证书替换。

## 文件与服务

```text
/usr/local/sbin/certhub-agent  Agent 主程序
/etc/certhub/                  客户端配置与状态
certhub-agent.service          systemd 服务
```

查看服务状态和日志：

```bash
sudo systemctl status certhub-agent
sudo journalctl -u certhub-agent -n 100 --no-pager
```

重启 Agent：

```bash
sudo systemctl restart certhub-agent
```

## 更新

服务端下发更新指令后，Agent 会下载 Linux 更新包、验证 SHA-256、原子替换 `/usr/local/sbin/certhub-agent` 并重启服务。新版 Agent 启动并回报后，服务端才会标记更新完成。

Linux 与 Windows Agent 独立发布和更新，服务端只会向对应平台下发更新包。

## 安全说明

- Agent 不会跳过 HTTPS 证书验证；
- 长期凭据不会写入日志；
- 服务端按客户端身份、证书授权及来源地址限制处理请求；
- 证书相同时不会进行重复部署；
- 清理指令只删除 CertHub 记录并管理的证书路径。
