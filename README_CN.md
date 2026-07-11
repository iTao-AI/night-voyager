# Night Voyager

Night Voyager 当前处于 **M0 bootstrap 阶段**。仓库只提供可复现的 Python API、Next.js Web、PostgreSQL 与持久 worker 本地工程基线；尚未实现留学决策工作流、生产租户能力或真实 provider 集成。

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

`make demo` 只启动合成的 bootstrap 服务。API 健康检查为 `http://127.0.0.1:8000/health`，Web bootstrap 页面为 `http://127.0.0.1:3000`。所有 host publish 均只绑定 IPv4 loopback。

## Contributor 路径

Contributor 还需要由 [uv](https://docs.astral.sh/uv/) 管理的 Python 3.12.13、Node.js 24.18.0 与 npm。

```bash
make doctor MODE=dev
make check
```

更多信息见 [CONTRIBUTING.md](CONTRIBUTING.md)、[SECURITY.md](SECURITY.md) 与 [docs/README.md](docs/README.md)。

## 当前边界

- 没有领域状态机、证据工作流、顾问/家庭 UI 或 tenant/RLS migration。
- 没有真实 DRA、MKE、OpenClaw、模型或消息适配器。
- 不代表生产部署、真实用户或录取结果。

## License

MIT
