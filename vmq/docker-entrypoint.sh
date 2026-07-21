#!/bin/sh
# V免签容器启动自愈：确保 ThinkPHP 运行目录可写，避免 500。
set -e

mkdir -p /var/www/html/runtime /var/www/html/public/qr-code
chown -R www-data:www-data /var/www/html/runtime /var/www/html/public/qr-code 2>/dev/null || true
chmod -R 777 /var/www/html/runtime /var/www/html/public/qr-code 2>/dev/null || true

exec apache2-foreground
