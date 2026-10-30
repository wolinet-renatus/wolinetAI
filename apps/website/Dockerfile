FROM docker.io/library/nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html styles.css app.js favicon.ico favicon.png robots.txt /usr/share/nginx/html/
COPY assets/ /usr/share/nginx/html/assets/
COPY downloads/ /usr/share/nginx/html/downloads/
COPY .well-known/ /usr/share/nginx/html/.well-known/

EXPOSE 80 8080 3000
