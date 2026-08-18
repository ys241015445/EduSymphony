#!/usr/bin/env bash
# =============================================================================
# 一键全栈部署（公网 Linux / VPS）
#   用法：  bash deploy.sh
#   默认用 docker-compose.coolify.yml（单容器 app = Nginx + backend）。
#   Coolify 用户无需本脚本：推代码后在 Coolify 面板 redeploy 即可。
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.coolify.yml}"

if ! docker info >/dev/null 2>&1; then
  echo "[deploy] Docker 未运行，请先启动 docker 服务：sudo systemctl start docker" >&2
  exit 1
fi

echo "[deploy] 构建并启动（$COMPOSE_FILE）..."
docker compose -f "$COMPOSE_FILE" up -d --build

echo "[deploy] 等待服务健康 ..."
sleep 8
docker compose -f "$COMPOSE_FILE" ps

cat <<'EOF'

================ 部署完成 ================
 EduSymphony 应用 :  给 app 服务配置的域名（Coolify/反代）
 付费闸门         :  扫码 +「我已支付」→ 邮件通知管理员确认额度
 提醒：配置 ALIPAY_QR / WECHAT_QR / SMTP_* / ADMIN_PAYMENT_EMAIL
 珠科材料助手     :  需 DEEPSEEK_API_KEY + 执行 supabase_zhuke_materials_migration.sql
=========================================
EOF
