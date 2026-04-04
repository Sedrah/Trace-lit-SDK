# Stage 1: build the React app
FROM node:22-alpine AS builder

WORKDIR /app
COPY dashboard/web/package.json dashboard/web/package-lock.json* ./
RUN npm ci --silent

COPY dashboard/web/ ./
RUN npm run build

# Stage 2: serve with nginx
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY infra/nginx/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
