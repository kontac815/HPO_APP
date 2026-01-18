FROM node:20-slim AS deps
WORKDIR /app
COPY package.json /app/package.json
RUN npm install

FROM node:20-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules /app/node_modules
COPY . /app
RUN npm run build

FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=builder /app /app
EXPOSE 3000
CMD ["npm", "run", "start"]

