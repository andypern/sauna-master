#!/bin/bash

# Define the container name
CONTAINER_NAME="sauna-master"
REPO=andypern

# Check if the container is running
if [ "$(docker ps -q -f name=$CONTAINER_NAME)" ]; then
    echo "Container '$CONTAINER_NAME' is running. Stopping it..."
    # Stop the running container
    docker stop $CONTAINER_NAME
fi

# Check if the container exists (but is not running)
if [ "$(docker ps -a -q -f name=$CONTAINER_NAME)" ]; then
    echo "Container '$CONTAINER_NAME' exists. Removing it..."
    # Remove the container
    docker rm $CONTAINER_NAME
fi

# Start the container again
echo "Starting container '$CONTAINER_NAME'..."
docker run --privileged --restart always --name $CONTAINER_NAME --device /dev/gpiomem --device /sys/bus/w1/devices:/sys/bus/w1/devices -p 5000:5000 -d $REPO/$CONTAINER_NAME
