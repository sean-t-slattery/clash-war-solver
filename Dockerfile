FROM node:24-slim AS web
WORKDIR /build
RUN corepack enable
COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml ./
RUN corepack pnpm install --frozen-lockfile
COPY apps/web/ ./
RUN corepack pnpm build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY backend ./backend
COPY data ./data
COPY --from=web /build/dist ./apps/web/dist
# Container must listen on its virtual interface; Compose publishes to host loopback only.
CMD ["uvicorn","backend.app:create_app","--factory","--host","0.0.0.0","--port","8000"]
