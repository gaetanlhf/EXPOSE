FROM openresty/openresty:1.27.1.2-3-alpine-apk

RUN apk update && \
    apk add --no-cache python3 python3-dev py3-pip supervisor nodejs npm

WORKDIR /expose.sh

COPY sshserver/ /expose.sh/sshserver

COPY tools/ /expose.sh/tools

COPY banners/ /expose.sh/banners

RUN npm install /expose.sh/tools

RUN pip3 install --no-cache-dir --break-system-packages -r /expose.sh/sshserver/requirements.txt

COPY webserver/nginx.conf /usr/local/openresty/nginx/conf/nginx.conf

COPY supervisor/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]