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
    kmod \
    cargo \
    zlib-dev jpeg-dev \
    cmake ninja git \
    curl-dev boost-dev \
    rust

ENV CFLAGS="-D_GNU_SOURCE"
#ENV PYARROW_BUNDLE_ARROW_CPP=1

RUN git clone https://github.com/apache/arrow.git && \
    cd arrow/cpp/ && \
    mkdir build && cd build && \ 
    cmake -GNinja \
       -DCMAKE_BUILD_TYPE=Release \
       -DARROW_JSON=ON \
       -DARROW_CSV=ON \
       -DARROW_PARQUET=ON \
       -DARROW_FILESYSTEM=ON \
       .. && \
       ninja install

  
#finally, actually install the python packages

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir wheel setuptools && \
    pip install --no-cache-dir pyarrow &&\
    pip install --no-cache-dir streamlit


# Install Python packages one by one to better handle dependencies
RUN pip install --no-cache-dir flask RPi.GPIO tzlocal bottle

# Copy application files
COPY app.py /app/
COPY streamlit_app.py /app/
COPY bottle_app.py /app/
COPY templates /app/templates/
COPY views /app/views/

# Expose ports
EXPOSE 5000 8501 8080

# Create a startup script
COPY <<EOF /app/start.sh
#!/bin/sh
python bottle_app.py
EOF

RUN chmod +x /app/start.sh

# Run both applications
CMD ["/app/start.sh"]
