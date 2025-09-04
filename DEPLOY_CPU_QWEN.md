# 部署指南（CPU 服务器 + Qwen2.5-3B-Instruct-GGUF Q5_K_M）

适用环境：4 vCPU / 16 GB RAM / 100 GB 硬盘 / 无 GPU 的外网独立服务器。

目标拓扑：
- 模型服务：llama.cpp OpenAI 兼容服务，监听 `:8080`（或经 Nginx 暴露到 443）。
- 后端：Flask + Socket.IO，经 gunicorn 启动，监听 `:5000`（或经 Nginx 暴露到 443）。
- 前端：浏览器直连后端；后端通过 OpenAI 兼容接口访问模型服务。

## 1. 服务器准备

- 操作系统：Ubuntu 20.04+/22.04+（示例基于 Ubuntu）。
- 安装基础工具：
  ```bash
  sudo apt update && sudo apt install -y python3-pip python3-venv nginx
  ```
- 打开端口（如未使用反代，临时开放 5000/8080；生产推荐只开放 80/443）：
  - 云厂商安全组：放行 TCP 80、443（可选：8080、5000）。

## 2. 安装与启动模型服务（llama.cpp server）

推荐模型：Qwen2.5-3B-Instruct GGUF 量化 Q5_K_M（质量优先）。若延迟偏高，可切换 Q4_K_M（更快更省内存）。

1) 安装 `llama-cpp-python` 的 OpenAI 兼容服务端：
```bash
pip install --upgrade "llama-cpp-python[server]"
```

2) 下载 GGUF 模型文件（示例路径 `/opt/models`）：
```bash
sudo mkdir -p /opt/models && sudo chown $USER:$USER /opt/models
cd /opt/models
# 方式A：Hugging Face CLI（推荐，需先登录或匿名，如仓库要求）
pip install -U huggingface_hub
# 列出仓库后挑选带有 q5_k_m 的文件（仓库名可能为官方或第三方量化，示例占位）
huggingface-cli ls <REPO_WITH_QWEN25_3B_INSTRUCT_GGUF>
# 下载你选择的 Q5_K_M 文件（示例文件名占位）
huggingface-cli download <REPO_WITH_QWEN25_3B_INSTRUCT_GGUF> qwen2.5-3b-instruct-q5_k_m.gguf -d /opt/models

# 方式B：wget 直链（如仓库支持直链下载）
wget -O /opt/models/qwen2.5-3b-instruct-q5_k_m.gguf "https://huggingface.co/<REPO_WITH_QWEN25_3B_INSTRUCT_GGUF>/resolve/main/qwen2.5-3b-instruct-q5_k_m.gguf?download=true"
```

3) 启动 OpenAI 兼容服务（监听 0.0.0.0:8080）：
```bash
python -m llama_cpp.server \
  --model /opt/models/qwen2.5-3b-instruct-q5_k_m.gguf \
  --host 0.0.0.0 --port 8080 \
  --n-gpu-layers 0 --threads 4 \
  --chat-template qwen2 \
  --model_alias qwen2.5-3b-instruct-q5_k_m
```

可选参数：
- 增大上下文：`--ctx-size 4096`（更长上下文会增大内存占用与延迟）。
- 限制并发：配合前端/后端做排队，或在 Nginx 层做限流。

4) 验证：
```bash
curl http://<你的域名或IP>:8080/v1/models
# 应返回包含你设置的 id，如：{"data":[{"id":"qwen2.5-3b-instruct-q5_k_m", ...}]}
```

5) （可选）注册为 systemd 服务（便于自启/守护）。示例见 `deploy/llama-cpp-server.service`。

## 3. 部署后端（Flask + Socket.IO）

1) 克隆或上传代码到服务器，例如 `/opt/chatbot_project`：
```bash
cd /opt
git clone <你的仓库地址> chatbot_project
cd chatbot_project
```

2) 安装依赖：
```bash
pip install -r requirements.txt
```

3) 配置环境变量（复制并修改 `.env.example` 为 `.env`，或导出为系统环境变量）：
```
FRONTEND_ORIGIN=https://chat.example.com          # 你的前端实际域名（或 http://localhost:3000）
API_BASE_URL=https://api.example.com              # 后端对外地址（Nginx 反代的域名）
LLM_BASE_URL=http://llm.example.com:8080/v1       # 模型服务对外地址（或内网地址）
LLM_API_KEY=sk-noauth                             # llama.cpp 默认不校验，保持即可
LLM_MODEL=qwen2.5-3b-instruct-q5_k_m              # 与 --model_alias 保持一致
TRANSLATION_ENABLED=true                          # 公网翻译不稳时可设为 false

BOT_INACTIVITY_SEC=30
BOT_SUPPRESS_SEC=5
LIBRE_ENDPOINTS=https://libretranslate.de/translate,https://translate.astian.org/translate,https://libretranslate.com/translate
```

4) 启动后端（两种方式择一）：
- A. 直接用 gunicorn 命令（从项目根目录运行）：
  ```bash
  gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
    -w 1 -b 0.0.0.0:5000 backend.app:app \
    --access-logfile gunicorn.log --error-logfile gunicorn.log --log-level info
  ```
- B. 使用仓库自带 `start.sh`：
  - 从 `backend/` 目录运行：
    ```bash
    cd backend && bash ../start.sh
    ```
  - 或在项目根目录运行并覆盖 APP_NAME：
    ```bash
    APP_NAME="backend.app:app" bash start.sh
    ```

5) 验证：
```bash
curl http://127.0.0.1:5000/api/v1/config
```

6) （可选）注册为 systemd 服务。示例见 `deploy/chatbot-backend.service`。

## 4. Nginx 反向代理（推荐 HTTPS）

为后端与模型分别配置域名（例如 `api.example.com` 与 `llm.example.com`），示例配置见：
- `deploy/nginx-api.conf`（反代到 127.0.0.1:5000，包含 WebSocket 升级头）。
- `deploy/nginx-llm.conf`（反代到 127.0.0.1:8080）。

部署步骤：
```bash
sudo cp deploy/nginx-api.conf /etc/nginx/sites-available/api.conf
sudo cp deploy/nginx-llm.conf /etc/nginx/sites-available/llm.conf
sudo ln -s /etc/nginx/sites-available/api.conf /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/llm.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

签发证书（以 certbot 为例）：
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d api.example.com -d llm.example.com
```

## 5. 前端与 CORS

- 设置 `FRONTEND_ORIGIN` 为前端的实际源，例如 `https://chat.example.com`（或本地开发 `http://localhost:3000`）。
- 前端 `frontend/js/config.js` 在加载时会调用后端 `/api/v1/config` 同步配置，避免硬编码多个地址。

## 6. 验证流程

1) 模型可用：
```bash
curl https://llm.example.com/v1/models -H "Authorization: Bearer sk-noauth"
```

2) 后端可用：
```bash
curl https://api.example.com/api/v1/config
```

3) Socket.IO 与对话：
- 前端页面打开浏览器控制台，确认能建立 WebSocket 连接。
- 发送消息后，后端会用中文回复，前端会按客户端语言翻译显示（可通过 `.env` 关闭翻译）。

## 7. 性能与调优建议

- 量化：优先 `Q5_K_M`；若延迟较高，切换 `Q4_K_M`。
- 线程：`--threads 4`（与 vCPU 数一致或略低）。
- 上下文：一般 4K 足够客服 FAQ；更大上下文增加内存与延迟。
- 负载：并发高时可在后端加请求排队、限流或提示稍后重试。

## 8. 常见问题

- 400/415/422 翻译失败：公网 LibreTranslate 不稳定，设置 `TRANSLATION_ENABLED=false` 或自建翻译服务。
- 模型 `id` 不匹配：将 `LLM_MODEL` 设为 `--model_alias` 指定的别名，或看 `/v1/models` 返回的 `id`。
- 启动路径问题：用 `backend.app:app` 从项目根目录启动；若用 `start.sh`，建议在 `backend/` 目录执行或覆盖 `APP_NAME`。
- CORS 失败：确认 `FRONTEND_ORIGIN` 与前端一致（协议、域名、端口需完全匹配）。

---

是否需要改代码？一般不需要：
- 本仓库已通过环境变量控制 `LLM_BASE_URL`、`LLM_MODEL`、`LLM_API_KEY`、`FRONTEND_ORIGIN`、`API_BASE_URL` 等，无需改动源码。
- 仅需在服务器正确设置环境变量，并确保模型服务对外可访问且 `/v1` 接口兼容。

若你需要，我可以按你的域名/IP 直接填好 `.env`、Nginx 与 systemd 模板。

