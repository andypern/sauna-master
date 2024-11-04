# Base image with Python
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the application files into the container
COPY app.py /app
COPY templates /app/templates

# Install the required Python libraries
RUN pip install flask

# Copy the w1 kernel modules (optional, based on the host system setup)
RUN apt-get update && apt-get install -y kmod

# Expose the port the app runs on
EXPOSE 5000

# Command to run the Flask app
CMD ["python", "app.py"]
