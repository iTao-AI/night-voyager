# Night Voyager

Night Voyager 将一组三国留学比较转化为可追溯的 advisor-to-family decision：以 durable Agent task 执行流程，经过明确的人工复核，并持久化 decision receipt 与 timeline。当前 v0.1.3 local synthetic portfolio release 在 `/` 提供 high-end Chinese-first“虚幻夜航”入口，并保留显式、持久的 English 切换。这个 root 是 static、local synthetic、provider-free 展示面，不发起 API、session、task 或 EventSource。运行时图片使用响应式 AVIF 与 WebP；仓库中的 source PNG 只用于 provenance。

完整 governed walkthrough 从 `/demo/collaboration` 开始，并将同一个 Case 继续交给显式 planning。focused advisor-family/evidence route 保留在 `/demo`，也可独立使用。两个 governed demo route 都保留既有 warm-paper ledger 视觉。

![Chinese-first Night Voyager 作品集入口](docs/assets/night-voyager-portfolio-entry.png)

![review-required 阶段的 Advisor Ledger](docs/assets/m5-advisor-ledger.png)

![Family decision receipt 与 timeline](docs/assets/m5-family-receipt-timeline.png)

![Governed collaboration confirmed fact](docs/assets/collaboration-confirmed-fact.png)

## 工程证据

- **PostgreSQL 与 forced RLS：** tenant-scoped runtime role 通过狭窄 authority path 读写，migration graph 固定为 `0001 -> 0002 -> 0003 -> 0004 -> 0005 -> 0006 -> 0007 -> 0008 -> 0009`。
- **Durable task 与 SSE：** `AgentTask` 可跨 worker/API restart 保持，使用 bounded lease 与 generation fencing，并恢复授权 event stream。
- **Human gates：** deterministic evidence policy、advisor review 与显式 family confirmation 相互分离；模型或 adapter 输出不能自行获得 promotion authority。
- **Governed DRA mixed planning：** optional offline proof 只导入 `UNTRUSTED_CANDIDATE`；assigned-advisor verification 与 promotion 共用一个原子数据库 gate，并通过既有 durable worker 物化一个 governed mixed PlanningRun。
- **Governed collaboration authority：** v0.1.2 release 将共享 `MessageEvent` communication、typed `MemoryCandidate` proposal、assigned-advisor verification 与 atomic versioned `ConfirmedFact` publication 分离。
- **Versioned Skill runtime：** v0.1.2 release 治理 exact six-key catalog、deterministic evaluation、owner activation/rollback、five-field task/execution pin，以及 start 前的 packaged-registry validation。
- **Explicit fact-to-plan authority：** v0.1.3 migration `0009` 把 first deterministic task creation 固定为 atomic `intake -> planning` authority，并在同一 transaction 写入 pinned task、dispatch、first event 与 idempotency result；legacy runtime transition authority 继续被撤回。
- **Browser to database：** v0.1.3 `/demo/collaboration` 现在可在不创建 task 的情况下，把已确认的同一 Case 交给 `/demo`；advisor 随后显式启动真实 pinned task、SSE、review、parent decision、receipt 与 timeline 路径。整条 provider-free chain 在真实 Chromium 与 PostgreSQL 上运行，同时两个 route 仍可独立使用。
- **Portfolio 与 dependency boundary：** v0.1.3 包含 responsive AVIF/WebP root presentation 和 Next.js / `eslint-config-next` `16.2.11`。optional/transitive `sharp@0.34.5` advisory `GHSA-f88m-g3jw-g9cj` 仍 deferred，因此不能声称 audit-zero。

## 验证 release

Evaluator 只需要 Docker Desktop、Docker Compose 与 GNU Make：

```bash
make help
make doctor
make demo
make proof
make down
```

当前作品集入口位于 `http://127.0.0.1:3000/`，SSR 使用 exact `zh-CN`；页头 `中文` / `English` 控件可显式选择 exact `en`。仅展示使用的 preference key 是 `night-voyager:presentation-locale:v1`，不会进入 session journey、HTTP/BFF request、task、SSE 或 domain authority。完整 governed walkthrough 按 [collaboration runbook](docs/operations/collaboration-walkthrough.md)从 `/demo/collaboration` 进入 `/demo`；focused advisor-family/evidence route 可按 [connected demo runbook](docs/operations/connected-demo.md)直接从 `/demo` 开始。[v0.1.3 release/source-archive verification guide](docs/how-to/verify-v0.1.3-release.md)定义 current release gates。

如需验证当前 same-Case development walkthrough，请从
`/demo/collaboration` 开始，确认 synthetic family fact，选择
`继续进入受治理规划`（English 为 `Continue to governed planning`），再在 `/demo` 执行显式 task action。Handoff
本身只做 read-only validation，creates no task。

`make doctor` 检查 Docker、Compose capability、本地端口、host project filesystem 至少 5 GiB，以及 Docker VM filesystem 至少 8 GiB。运维人员只能通过 `NIGHT_VOYAGER_DOCKER_MINIMUM_KB` 调整 Docker VM 门槛；检查会 fail closed，且绝不会自动删除 Docker 资源。`make demo` 迁移并 seed fresh synthetic stack。`make proof` 验证配置、public hygiene 与隔离 installed wheel，不要求 host Python、uv、Node.js 或 npm。`make compose-proof` 还会在真实 Chromium 中执行 browser-to-database flow。

## 合成与本地边界

- v0.1.3 是 local synthetic portfolio release，包含 Governed Collaboration Core v1、explicit fact-to-plan authority、Chinese-first bilingual presentation、High-End Portfolio Entry、deterministic offline governed DRA capability 与既有 advisor-to-family workflow；不代表 production deployment 或 production tenancy。
- 仓库不包含真实学生记录，也不宣称录取结果、真实用户、SLA、可用性或业务收益。
- worker 与 SSE 仅提供 deterministic local proof，不代表 distributed high availability。
- Live DRA、OpenClaw、remote provider、消息通道与 product-path MKE 均未连接。Deterministic offline DRA candidate import、atomic promotion 与 governed mixed PlanningRun generation 已在本地实现；live provider proof 未运行，仍需单独授权。M4B 仍是 optional read-only compatibility adapter，所有投影保持 `UNTRUSTED_CANDIDATE`。
- Governed collaboration PR A、versioned Skill governance PR B 与 browser walkthrough/inspector PR C 已在 v0.1.2 作为 local synthetic capability 发布。`/demo/collaboration` 本身不创建 `AgentTask`；只有 same-Case handoff 后在 `/demo` 执行显式 action，才会启动既有 governed planning path。
- v0.1.3 包含已合并 PR #57–#62。它不新增 live provider、production deployment、distributed HA、SLA、真实学生数据、真实学校覆盖、顾问团队采用或录取结果。

## Milestone 与历史

- [v0.1.3 release notes](docs/releases/v0.1.3.md)
- [v0.1.2 历史 release notes](docs/releases/v0.1.2.md)
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
- [Governed fact-to-plan walkthrough](docs/operations/collaboration-walkthrough.md)与 [connected continuation](docs/operations/connected-demo.md)；同一 confirmed Case 现在可在本地进入显式 deterministic planning，且不依赖 provider。

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
