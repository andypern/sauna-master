FROM python:3.9-alpine

# Set working directory
WORKDIR /app

# Install only the necessary system dependencies for RPi.GPIO
RUN apk add --no-cache \
    python3-dev \
    gcc \
    musl-dev \
    linux-headers

# Install only required Python packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir bottle RPi.GPIO

# Copy only necessary application files
COPY bottle_app.py /app/
COPY views /app/views/

# Create required files for persistence
RUN touch /app/sauna_schedule.json && \
    touch /app/sauna_status.json && \
    chmod 666 /app/sauna_schedule.json && \
    chmod 666 /app/sauna_status.json

# Expose only the bottle app port
EXPOSE 8080

# Run the bottle application
CMD ["python", "bottle_app.py"]
