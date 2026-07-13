# Night Voyager

Night Voyager 已具备 **M0 bootstrap 基线**、**M1 fixture-only design contract**、**M2 identity/session/RLS boundary**、**M3A deterministic planning foundation**、**M3B local synthetic advisor-to-family backend proof** 与 **M4A deterministic durable task/worker/SSE proof**。M4A 创建版本固定的 planning task，在 PostgreSQL 中持久化 worker lifecycle，并授权重放事件，不绕过顾问审核；`/demo` 仍是未连接 backend 的 fixture-only 页面。

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
`make compose-proof` 可验证 health、真实 identity 与 M3B 路径、M4A
HTTP-to-worker-to-PlanningRun-to-SSE 路径，以及 API/worker restart durability，
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

`make db-check` 使用 disposable PostgreSQL 18 volume 执行精确
`0001 -> 0002 -> 0003 -> 0004` migration、canonical synthetic seed 幂等性、
双租户 forced RLS、runtime grants、Case 与 PlanningRun authority、payload-free
dispatch、lease、generation fencing、retry/cancel/reclaim race、SSE replay、
bounded local concurrency、downgrade/re-upgrade 与 pool cleanup。
`accepted_synthetic_demo`
Evidence 只代表本地合成 proof；caller 不能声明 `externally_verified`。

## 当前边界

- M3B/M4A backend path 尚未连接 fixture-only `/demo`；没有 task 或 decision frontend mutation。
- worker/SSE proof 是本地确定性证据，不代表 distributed high availability 或 production SLA。
- 没有真实 DRA、MKE、OpenClaw、模型或消息适配器。
- 不代表生产部署、真实用户或录取结果。

## License

MIT
