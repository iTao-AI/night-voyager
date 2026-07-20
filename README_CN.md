# Night Voyager

Night Voyager 将一组三国留学比较转化为可追溯的 advisor-to-family decision：以 durable Agent task 执行流程，经过明确的人工复核，并持久化 decision receipt 与 timeline。

![review-required 阶段的 Advisor Ledger](docs/assets/m5-advisor-ledger.png)

![Family decision receipt 与 timeline](docs/assets/m5-family-receipt-timeline.png)

![Governed collaboration confirmed fact](docs/assets/collaboration-confirmed-fact.png)

## 工程证据

- **PostgreSQL 与 forced RLS：** tenant-scoped runtime role 通过狭窄 authority path 读写，migration graph 固定为 `0001 -> 0002 -> 0003 -> 0004 -> 0005 -> 0006 -> 0007 -> 0008`。
- **Durable task 与 SSE：** `AgentTask` 可跨 worker/API restart 保持，使用 bounded lease 与 generation fencing，并恢复授权 event stream。
- **Human gates：** deterministic evidence policy、advisor review 与显式 family confirmation 相互分离；模型或 adapter 输出不能自行获得 promotion authority。
- **Governed DRA mixed planning：** optional offline proof 只导入 `UNTRUSTED_CANDIDATE`；assigned-advisor verification 与 promotion 共用一个原子数据库 gate，并通过既有 durable worker 物化一个 governed mixed PlanningRun。
- **Governed collaboration authority：** v0.1.2 release 将共享 `MessageEvent` communication、typed `MemoryCandidate` proposal、assigned-advisor verification 与 atomic versioned `ConfirmedFact` publication 分离。
- **Versioned Skill runtime：** v0.1.2 release 治理 exact six-key catalog、deterministic evaluation、owner activation/rollback、five-field task/execution pin，以及 start 前的 packaged-registry validation。
- **Browser to database：** primary `/demo` 在 Chromium 中执行真实 Next.js BFF、FastAPI、worker、SSE 与 PostgreSQL synthetic flow；secondary `/demo/collaboration` 在不创建 task 的前提下证明 parent proposal、advisor confirmation 与 authoritative fact/revision reload。

## 验证 release

Evaluator 只需要 Docker Desktop、Docker Compose 与 GNU Make：

```bash
make help
make doctor
make demo
make proof
make down
```

primary connected local synthetic demo 位于 `http://127.0.0.1:3000/demo`，按 [connected demo runbook](docs/operations/connected-demo.md)完成 advisor-to-family walkthrough。Secondary governed-memory walkthrough 位于 `http://127.0.0.1:3000/demo/collaboration`，操作见[独立 runbook](docs/operations/collaboration-walkthrough.md)。[v0.1.2 release/source-archive verification guide](docs/how-to/verify-v0.1.2-release.md)描述当前 release。

`make doctor` 检查 Docker、Compose capability、本地端口、host project filesystem 至少 5 GiB，以及 Docker VM filesystem 至少 8 GiB。运维人员只能通过 `NIGHT_VOYAGER_DOCKER_MINIMUM_KB` 调整 Docker VM 门槛；检查会 fail closed，且绝不会自动删除 Docker 资源。`make demo` 迁移并 seed fresh synthetic stack。`make proof` 验证配置、public hygiene 与隔离 installed wheel，不要求 host Python、uv、Node.js 或 npm。`make compose-proof` 还会在真实 Chromium 中执行 browser-to-database flow。

## 合成与本地边界

- v0.1.2 是 local synthetic portfolio release，包含 Governed Collaboration Core v1、deterministic offline governed DRA capability 与既有 advisor-to-family workflow；不代表 production deployment 或 production tenancy。
- 仓库不包含真实学生记录，也不宣称录取结果、真实用户、SLA、可用性或业务收益。
- worker 与 SSE 仅提供 deterministic local proof，不代表 distributed high availability。
- Live DRA、OpenClaw、remote provider、消息通道与 product-path MKE 均未连接。Deterministic offline DRA candidate import、atomic promotion 与 governed mixed PlanningRun generation 已在本地实现；live provider proof 未运行，仍需单独授权。M4B 仍是 optional read-only compatibility adapter，所有投影保持 `UNTRUSTED_CANDIDATE`。
- Governed collaboration PR A、versioned Skill governance PR B 与 browser walkthrough/inspector PR C 已在 v0.1.2 作为 local synthetic capability 发布。`/demo` 仍是 primary advisor-family route；secondary `/demo/collaboration` 不创建 `AgentTask`。

## Milestone 与历史

- [v0.1.2 release notes](docs/releases/v0.1.2.md)
- [v0.1.1 历史 release notes](docs/releases/v0.1.1.md)
- [v0.1.0 历史 release notes](docs/releases/v0.1.0.md)
- [架构与 milestone 历史](DESIGN.md)
- [文档索引](docs/README.md)
- [Connected demo storyboard](docs/design/demo-storyboard.md)
- M5 connected advisor-to-family demo 已实现为 [runbook](docs/operations/connected-demo.md)所述的 local synthetic walkthrough。
- [M4B optional read-only MKE candidate proof](docs/operations/mke-candidate-proof.md)；输出保持 `UNTRUSTED_CANDIDATE`。
- [Governed DRA mixed-evidence proof](docs/operations/dra-consumer-proof.md)；candidate import、atomic human promotion 与 governed mixed PlanningRun generation 已形成 deterministic local closure，connected synthetic `/demo` 保持不变。
- [Governed collaboration 与 confirmed-fact reference](docs/reference/collaboration-and-confirmed-facts.md)、[authority runbook](docs/operations/collaboration-authority.md)及 [browser walkthrough](docs/operations/collaboration-walkthrough.md)；PR A 与 PR C 已在 v0.1.2 作为 authority 与 presentation layer 发布。
- [Versioned Skills 与 runtime pins](docs/reference/versioned-skills-and-runtime-pins.md)及 [Skill governance runbook](docs/operations/skill-governance.md)；PR B 已在 v0.1.2 发布，PR C 已实现其 read-only server projection。

## Contributor 路径

Contributor 还需要由 [uv](https://docs.astral.sh/uv/) 管理的 Python 3.12.13、Node.js 24.18.0 与 npm：

```bash
make doctor MODE=dev
make check
make db-check
make collaboration-check
make skills-check
make dra-check
make mke-check
```

更多信息见 [CONTRIBUTING.md](CONTRIBUTING.md) 与 [SECURITY.md](SECURITY.md)。

## License

MIT
