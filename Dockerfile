FROM node:20-bookworm-slim AS jsdeps
WORKDIR /tools
COPY backend/tools/package.json ./package.json
RUN npm install --omit=dev

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY --from=jsdeps /usr/local/bin/node /usr/local/bin/node
COPY --from=jsdeps /tools/node_modules backend/tools/node_modules
COPY . .
RUN useradd -m app && mkdir -p /data && chown app /data
USER app
ENV LMA_DB=/data/migrations.db
WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
