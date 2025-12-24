# Build stage
FROM node:18-alpine AS build
WORKDIR /app

# Copy frontend sources
COPY frontend/package*.json ./frontend/
COPY frontend/ ./frontend/
WORKDIR /app/frontend

# Install deps and build
RUN npm install --legacy-peer-deps
RUN npm run build

# Production stage: serve with nginx
FROM nginx:stable-alpine
COPY --from=build /app/frontend/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
