FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html
COPY styles.css /usr/share/nginx/html/styles.css
COPY app.js /usr/share/nginx/html/app.js
COPY logo.png /usr/share/nginx/html/logo.png
COPY logo_dark.png /usr/share/nginx/html/logo_dark.png
COPY favicon.ico /usr/share/nginx/html/favicon.ico
COPY favicon.png /usr/share/nginx/html/favicon.png
EXPOSE 80 8080
