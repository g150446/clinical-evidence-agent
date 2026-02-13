FROM nginx:alpine
COPY index.html /usr/share/nginx/html/index.html
COPY config.js /usr/share/nginx/html/config.js
RUN echo 'server { listen 8080; server_name localhost; location / { root /usr/share/nginx/html; index index.html; } }' > /etc/nginx/conf.d/default.conf
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD wget --quiet --tries=1 --spider http://localhost:8080 || exit 1
