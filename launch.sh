#!/bin/bash

# Define the container name
CONTAINER_NAME="sauna-master"
REPO=andypern

# Default tag
TAG="latest"

# Parse command line arguments
while getopts "t:" opt; do
    case $opt in
        t)
            TAG="$OPTARG"
            ;;
        \?)
            echo "Invalid option: -$OPTARG" >&2
            exit 1
            ;;
    esac
done

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
echo "Starting container '$CONTAINER_NAME' with tag '$TAG'..."
docker run --privileged --restart always --name $CONTAINER_NAME --device /dev/gpiomem --device /sys/bus/w1/devices:/sys/bus/w1/devices -p 8501:8501 -p 8080:8080 -d $REPO/$CONTAINER_NAME:$TAG
