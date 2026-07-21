# V免签(Vmqphp) 运行镜像：ThinkPHP5.1 + PHP7.4 + Apache
FROM php:7.4-apache

# ThinkPHP 依赖 + 二维码识别(gd) + curl(健康检查/DB 等待)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpng-dev libjpeg-dev libfreetype6-dev curl default-mysql-client \
    && docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install -j"$(nproc)" pdo_mysql gd bcmath \
    && rm -rf /var/lib/apt/lists/*

# 运行目录指向 public（ThinkPHP 入口），开启伪静态 rewrite
RUN a2enmod rewrite \
    && sed -ri 's!DocumentRoot /var/www/html!DocumentRoot /var/www/html/public!g' /etc/apache2/sites-available/000-default.conf \
    && printf '<Directory /var/www/html/public>\n    AllowOverride All\n    Require all granted\n</Directory>\n' > /etc/apache2/conf-available/vmq.conf \
    && a2enconf vmq

COPY . /var/www/html/
RUN chown -R www-data:www-data /var/www/html \
    && chmod -R 777 /var/www/html/runtime /var/www/html/public/qr-code 2>/dev/null || true \
    && sed -i 's/\r$//' /var/www/html/docker-entrypoint.sh \
    && chmod +x /var/www/html/docker-entrypoint.sh

EXPOSE 80
ENTRYPOINT ["/var/www/html/docker-entrypoint.sh"]
