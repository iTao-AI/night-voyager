# Night Voyager

Night Voyager 当前处于 **M0 bootstrap 阶段**。仓库只提供可复现的 Python API、Next.js Web、PostgreSQL 与持久 worker 本地工程基线；尚未实现留学决策工作流、生产租户能力或真实 provider 集成。

## 前置条件

- 由 [uv](https://docs.astral.sh/uv/) 管理的 Python 3.12.13
- Node.js 24.18.0 与 npm
- Docker Desktop 与 Docker Compose
- GNU Make

## Bootstrap 验证

```bash
cp .env.example .env
make doctor MODE=dev
make check
make demo
make proof
make down
```

`make demo` 只启动合成的 bootstrap 服务。API 健康检查为 `http://localhost:8000/health`，Web bootstrap 页面为 `http://localhost:3000`。

更多信息见 [CONTRIBUTING.md](CONTRIBUTING.md)、[SECURITY.md](SECURITY.md) 与 [docs/README.md](docs/README.md)。

## 当前边界

- 没有领域状态机、证据工作流、顾问/家庭 UI 或 tenant/RLS migration。
- 没有真实 DRA、MKE、OpenClaw、模型或消息适配器。
- 不代表生产部署、真实用户或录取结果。

## License

MIT
