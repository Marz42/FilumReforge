FROM node:20-bookworm-slim

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY scripts/docker-dev-entrypoint.sh /usr/local/bin/filum-frontend-dev
RUN sed -i 's/\r$//' /usr/local/bin/filum-frontend-dev \
    && chmod +x /usr/local/bin/filum-frontend-dev \
    && sha256sum package-lock.json | cut -d ' ' -f 1 > node_modules/.filum-package-lock.sha256

COPY . .

EXPOSE 5173

ENTRYPOINT ["filum-frontend-dev"]
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
