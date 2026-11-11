# OpenWRT 客户端

适用于 CertHub 1.4.0 及以上版本，当前 OpenWRT Agent 为 0.3.20。

在新增客户端时选择 **OpenWRT**，以 root 在路由器终端执行生成的命令。
首次下载需要 curl 和可用的 HTTPS CA，设备还需具备可用的软件源、安装依赖所需的存储空间以及正确的系统时间；安装器会通过 opkg 或 apk 安装 bash、curl、ca-bundle、flock、python3-light、python3-openssl 和 openssl-util，并检查实际需要的 Python 模块。无需完整 Python 或宝塔面板。

支持服务托管目录和自定义下载目录，不支持宝塔面板标准路径或网站自动替换。
默认状态及证书持久化在 `/etc/certhub-agent/state`，不会因为 OpenWRT 的 `/var`、`/tmp` 重启清空而丢失。

- 默认完整链：`/etc/certhub-agent/state/certificates/<id>/current/fullchain.pem`
- 默认私钥：`/etc/certhub-agent/state/certificates/<id>/current/privkey.pem`
- 自定义目录：`<下载根目录>/<证书名称>/fullchain.pem` 和 `privkey.pem`
- 配置：`/etc/certhub-agent/config.json`（重复安装保留注册身份）
- 服务：`/etc/init.d/certhub-agent {start|stop|restart|status}`
- 手动同步：`/usr/local/sbin/certhub-agent sync`
- 日志：`logread -e certhub-agent`

使用 procd 管理常驻同步进程，支持后台配置同步、证书更新、授权移除清理、客户端撤销和在线代理更新。
本版本只负责证书文件同步；请按目标服务配置证书路径及其重载方式。
已有客户端可在“修改客户端”中选择 OpenWRT，并设置托管目录或自定义目录。平台选择不会自动替换设备上的运行环境和服务，需要配合安装对应平台的代理。

使用临时适配脚本的设备迁移时，请先将服务端客户端登记为 OpenWRT；不要用 Linux 注册凭据安装新适配器。安装器重复运行会保留已有配置；若已有配置指向其他面板或已损坏，安装器会停止并提示检查。

参考：[OpenWrt Python 包](https://github.com/openwrt/packages/tree/master/lang/python)、[procd 初始化脚本](https://openwrt.org/docs/guide-developer/procd-init-scripts)。

[返回项目说明](../../README.md)
