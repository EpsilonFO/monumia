FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the application
RUN npx vite build

# Production stage
FROM node:20-alpine

WORKDIR /app

# Install a simple HTTP server to serve the built files
RUN npm install -g http-server

# Copy built files from builder stage
COPY --from=builder /app/dist ./dist

# Expose port
EXPOSE 3000

# Serve the application
CMD ["http-server", "dist", "-p", "3000"]
