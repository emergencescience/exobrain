# 🧠 Exobrain（中文开发说明）

Exobrain 是面向科学写作与计算证据的 Markdown/LaTeX 工作台：通过对话创建或修改文档，验证公式推导，并将一次代码运行结果显式关联到论文 claim。

> [English README](README.md) 是完整的开源项目说明；本文件侧重中文用户的本地开发与安全边界。新增功能时，两份 README 的启动命令和安全说明必须同步更新。

## 本地开发与测试

[公开 Exobrain 仓库](https://github.com/emergencescience/exobrain) 只由 `frontend/` 和 `backend/` 构成。它不要求账户、积分或 JWT；未提供 `X-User-Id` 时，后端使用本地开发用的 `local` 命名空间。

### 1. 启动后端

```bash
cd backend

# 首次执行：建立虚拟环境并安装运行/测试依赖
uv sync --extra test

# 对话需要 OpenAI 兼容模型 API key；内置示例不需要
export EXOBRAIN_CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:3000"
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

验证：

```bash
curl http://127.0.0.1:8080/health
```

若 `uv sync` 报 `tls handshake eof`，这是 PyPI 下载连接中断，不是依赖冲突。`uv` 已解析依赖时可直接稍后重试；不要手动修改 lockfile 或随意降级 FastAPI。可先执行 `uv cache clean fastapi` 后重试，或在网络稳定时执行：

```bash
uv sync --extra test --refresh
```

`sentence-transformers` 会带来较大的 PyTorch 下载；RAG 是可选能力，本地验证编辑、验证、代码运行和证据链接前不应因它而改动项目依赖版本。

需要本地 RAG 时再安装：

```bash
uv sync --extra rag
```

### 2. 在另一个终端启动独立前端

```bash
cd frontend
npm install
npm run dev
```

打开 `http://localhost:3000`。前端默认直接访问 `http://localhost:8080`，可独立测试 Markdown 编辑、LaTeX 渲染、文档存储、对话和公式验证。

如需使用其他后端地址，在启动前端前设置 `NEXT_PUBLIC_EXOBRAIN_API_URL`。

### 3. 后端测试

```bash
cd backend
uv run pytest tests/test_verify_api_integration.py
```

也可以不启动前端，直接验证 API：

```bash
curl -X POST http://127.0.0.1:8080/api/verify \
  -H 'Content-Type: application/json' \
  -d '{"markdown":"For $x=2$, $x^2=4$.","locale":"en"}'
```

## Notebook 与代码运行安全

当前 Python runner 仅适合开发演示，不是公网多租户 Jupyter 沙箱。它有超时与输出限制，但不能可靠阻止文件访问、子进程或资源滥用。

产品路线：

1. 先导入并展示 `.ipynb` 的既有 cell、输出、图表和元数据，作为可关联的 evidence，不执行任意 Notebook。
2. 再提供固定科学镜像中的按需重跑（SymPy、NumPy、SciPy、Pandas、Matplotlib）。
3. 面向公网执行前，每个 job 使用临时隔离环境、无默认网络、资源配额、固定镜像和自动清理。

完整的实体关系模型、分享能力与证据模型见 [`internal/exobrain/tech-design.md`](../../internal/exobrain/tech-design.md)。

## Markdown 与 LaTeX 的 V1 边界

不建议因 Python 环境而取消 LaTeX 公式支持：

- 浏览器公式渲染由 KaTeX 完成，不依赖 Python 或系统 TeX/LaTeX 安装。
- SymPy 的 LaTeX 解析只需要 Python 的 `antlr4-python3-runtime`，已由后端依赖锁定；也不需要系统 TeX。
- V1 应支持 Markdown、`$...$` 与 `$$...$$`，但不承诺 `.tex` 项目编译、PDF 生成、宏包解析或任意 LaTeX 导入。失败或未知语法应显示为原始源码并标记为 `inconclusive`，而不是静默伪造验证结果。
