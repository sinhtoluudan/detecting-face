FROM node:22-alpine AS build
WORKDIR /app
COPY web/frontend/package*.json ./
RUN npm ci
COPY web/frontend ./
ARG API_PROXY_URL=http://api:8000
ENV API_PROXY_URL=$API_PROXY_URL NEXT_TELEMETRY_DISABLED=1
RUN npm run build
FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production HOSTNAME=0.0.0.0 PORT=3000 NEXT_TELEMETRY_DISABLED=1
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
USER node
EXPOSE 3000
CMD ["node","server.js"]
