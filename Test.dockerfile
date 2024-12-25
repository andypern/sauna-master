# Use Raspberry Pi compatible base image
#FROM arm32v6/python:3.9-alpine
FROM python:3.9-alpine

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apk add --no-cache \
apache-arrow \
build-base \
    linux-headers \
    musl-dev \
    python3-dev \
    gcc \
    fortify-headers \
    kmod \
    cargo \
    zlib-dev \
    cmake ninja \
    rust
