# secrets/ 目录说明

此目录存放生产环境密钥文件。`.gitignore` 已通过 `*.pem` / `*.key` 规则排除，**任何私钥文件都不得提交到 git**。

## JWT 签名私钥（生产必配）

docker-compose 会把 `secrets/oidc_rsa_private.pem` 挂载到 backend 容器，
entrypoint 启动时自动注入为 `OIDC_RSA_PRIVATE_KEY` 环境变量。

**不配置的后果**：应用每次重启生成临时 RSA 密钥，所有用户的登录态（JWT）全部失效，需重新登录。

生成（在项目根目录执行）：

```bash
mkdir -p secrets
openssl genrsa -out secrets/oidc_rsa_private.pem 2048
chmod 600 secrets/oidc_rsa_private.pem
```

更换私钥同样会使所有已签发 JWT 失效，属正常现象。

## 备份建议

- `.env` 与本目录文件是恢复系统所需的全部敏感材料，请离线备份（如密码管理器）。
- 备份 `mysql_data` 卷时注意：其中数据源连接密码用 `APP_ENCRYPTION_KEY` 加密，
  丢失该密钥则无法解密，二者必须一起备份。
