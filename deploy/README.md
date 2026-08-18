# 部署说明（P2 经营归因分析系统）

参考课程文档：《应用服务部署.md》

## 文件结构

```text
deploy/
├── Dockerfile               # 业务服务镜像（python:3.11-slim + uvicorn，端口 8001）
├── docker-compose.yml       # 最小可跑版：仅 kb-p2-app
├── docker-compose.prod.yml  # 生产参考版：加资源约束与健康检查
├── .env.prod.example        # 生产环境变量模板
└── README.md
```

## 快速启动

```bash
cd deploy
cp .env.prod.example .env.prod
# 编辑 .env.prod，填写 DEEPSEEK_API_KEY（无 key 走离线降级）

docker compose up -d --build

# 生成演示数据（3 个月双场景 + 管理员 admin/admin123）
docker compose run --rm kb-p2-app python scripts/gen_data.py

# 健康检查（WebSocket 与 REST 共用 8001 端口）
curl http://127.0.0.1:8001/health

# 查看日志 / 停止
docker compose logs -f kb-p2-app
docker compose down
```

## 端口规划

- 公网开放：`8001`（业务服务，REST + WebSocket）、`22`（SSH）
- 生产参考版按需调整：`docker-compose.prod.yml`

## 注意事项

- 首次启动必须先执行 `gen_data.py`，否则演示表为空
- 演示数据持久化在 `deploy/volumes/data/`，删除前请备份
- 配置热更新：登录后调用 `POST /api/admin/reload` 重载 `system_configs`
- 生产扩展（PostgreSQL/Redis/对象存储）需在代码中新增适配器后接入
