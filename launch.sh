#!/bin/bash

# Define the container name
CONTAINER_NAME="andypern/sauna-master"

# Check if the container is running
if [ "$(docker ps -q -f name=$CONTAINER_NAME)" ]; then
    echo "Container '$CONTAINER_NAME' is running. Stopping it..."
    # Stop the running container
    docker stop $CONTAINER_NAME
    
    # Optionally, remove the container (if you want to ensure a fresh start)
    docker rm $CONTAINER_NAME
fi

# Start the container again
echo "Starting container '$CONTAINER_NAME'..."
docker run --privileged --name $CONTAINER_NAME --device /dev/gpiomem --device /sys/bus/w1/devices:/sys/bus/w1/devices -p 5000:5000 -d $CONTAINER_NAME
