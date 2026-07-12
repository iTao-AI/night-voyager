# Night Voyager

Night Voyager 已具备 **M0 bootstrap 基线**、**M1 fixture-only design contract** 与 **M2 backend identity/session/RLS security foundation**。仓库提供可复现的 Python API、Next.js Web、PostgreSQL 与持久 worker 本地工程基线；`/demo` 使用合成 fixture 演示已批准的 advisor-to-family 产品流程，但不连接 domain backend，也不实现 mutation、生产租户能力或真实 provider 集成。

## Evaluator 路径

Evaluator 只需要 Docker Desktop、Docker Compose 与 GNU Make。固定命令序列为：

```bash
make help
make doctor
make demo
make proof
make down
```

`make doctor` 检查 Docker daemon、必要的 Compose capability、磁盘空间与本地端口。`make proof` 在 Docker 内运行配置、public-hygiene 与 installed-wheel 检查，不依赖 host Python、uv、Node.js 或 npm。

`make demo` 先迁移本地数据库，再运行 fail-closed、幂等的 `demo-seed`
service，随后等待合成 bootstrap stack ready。API 健康检查为
`http://127.0.0.1:8000/health`，Web bootstrap 页面为
`http://127.0.0.1:3000`。所有 host publish 均只绑定 IPv4 loopback。运行
`make compose-proof` 可验证 health 以及真实 bootstrap/session-mint API 路径，
但不会连接 fixture-only UI。

M1 fixture-only prototype 位于 `http://127.0.0.1:3000/demo`。视觉与产品合同见 [DESIGN.md](DESIGN.md) 和 [docs/design/](docs/design/)。

## Contributor 路径

Contributor 还需要由 [uv](https://docs.astral.sh/uv/) 管理的 Python 3.12.13、Node.js 24.18.0 与 npm。

```bash
make doctor MODE=dev
make check
make db-check
```

更多信息见 [CONTRIBUTING.md](CONTRIBUTING.md)、[SECURITY.md](SECURITY.md) 与 [docs/README.md](docs/README.md)。

`make db-check` 使用 disposable PostgreSQL 18 volume 验证 migration、合成 identity seed 幂等性、非 owner runtime roles、受限 auth functions、forced RLS、session lifecycle 与 pool cleanup，并始终删除测试 volume。

## 当前边界

- M2 backend security foundation 尚未连接 fixture-only `/demo`；没有领域状态机、证据工作流 backend 或顾问/家庭 mutation。
- 没有真实 DRA、MKE、OpenClaw、模型或消息适配器。
- 不代表生产部署、真实用户或录取结果。

## License

MIT
