# Night Voyager

Night Voyager 将一组三国留学比较转化为可追溯的 advisor-to-family decision：以 durable Agent task 执行流程，经过明确的人工复核，并持久化 decision receipt 与 timeline。

![review-required 阶段的 Advisor Ledger](docs/assets/m5-advisor-ledger.png)

![Family decision receipt 与 timeline](docs/assets/m5-family-receipt-timeline.png)

## 工程证据

- **PostgreSQL 与 forced RLS：** tenant-scoped runtime role 通过狭窄 authority path 读写，migration graph 固定为 `0001 -> 0002 -> 0003 -> 0004`。
- **Durable task 与 SSE：** `AgentTask` 可跨 worker/API restart 保持，使用 bounded lease 与 generation fencing，并恢复授权 event stream。
- **Human gates：** deterministic evidence policy、advisor review 与显式 family confirmation 相互分离；模型或 adapter 输出不能自行获得 promotion authority。
- **Browser to database：** connected `/demo` 在 Chromium 中执行真实 Next.js BFF、FastAPI、worker、SSE 与 PostgreSQL synthetic flow。

## 验证 release

Evaluator 只需要 Docker Desktop、Docker Compose 与 GNU Make：

```bash
make help
make doctor
make demo
make proof
make down
```

connected local synthetic demo 位于 `http://127.0.0.1:3000/demo`。按 [connected demo runbook](docs/operations/connected-demo.md)完成 advisor-to-family walkthrough；需要完整 release-candidate 证据时，使用 [v0.1.0 verification guide](docs/how-to/verify-v0.1.0-release.md)。

`make doctor` 检查 Docker、Compose capability、磁盘空间与本地端口。`make demo` 迁移并 seed fresh synthetic stack。`make proof` 验证配置、public hygiene 与隔离 installed wheel，不要求 host Python、uv、Node.js 或 npm。`make compose-proof` 还会在真实 Chromium 中执行 browser-to-database flow。

## 合成与本地边界

- v0.1.0 是 local synthetic portfolio release，不代表 production deployment 或 production tenancy。
- 仓库不包含真实学生记录，也不宣称录取结果、真实用户、SLA、可用性或业务收益。
- worker 与 SSE 仅提供 deterministic local proof，不代表 distributed high availability。
- DRA、OpenClaw、remote provider、消息通道与 product-path MKE 均未连接；M4B 仍是 optional read-only compatibility adapter，所有投影保持 `UNTRUSTED_CANDIDATE`。

## Milestone 与历史

- [v0.1.0 release notes](docs/releases/v0.1.0.md)
- [架构与 milestone 历史](DESIGN.md)
- [文档索引](docs/README.md)
- [历史 M1 fixture-only visual contract](docs/superpowers/specs/2026-07-11-m1-demo-design.md)
- M5 connected advisor-to-family demo 已实现为 [runbook](docs/operations/connected-demo.md)所述的 local synthetic walkthrough。
- [M4B optional read-only MKE candidate proof](docs/operations/mke-candidate-proof.md)；输出保持 `UNTRUSTED_CANDIDATE`。

## Contributor 路径

Contributor 还需要由 [uv](https://docs.astral.sh/uv/) 管理的 Python 3.12.13、Node.js 24.18.0 与 npm：

```bash
make doctor MODE=dev
make check
make db-check
make mke-check
```

更多信息见 [CONTRIBUTING.md](CONTRIBUTING.md) 与 [SECURITY.md](SECURITY.md)。

## License

MIT
