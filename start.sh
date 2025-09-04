#!/bin/bash
# =============== 启动客服后端 (gevent-websocket) ===============

# 优先用环境变量 APP_NAME；默认指向 backend.app:app（从项目根目录运行）
APP_NAME="${APP_NAME:-backend.app:app}"
HOST="0.0.0.0"
PORT=5000
WORKERS=1
LOGFILE="gunicorn.log"

echo "🔄 正在启动客服后端服务..."
echo "📌 模式: gevent-websocket"
echo "📌 地址: http://${HOST}:${PORT}"

# 启动 gunicorn
exec gunicorn \
  -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
  -w $WORKERS \
  -b ${HOST}:${PORT} \
  $APP_NAME \
  --access-logfile $LOGFILE \
  --error-logfile $LOGFILE \
  --log-level info
