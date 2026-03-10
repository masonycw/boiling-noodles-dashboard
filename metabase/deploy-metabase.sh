#!/bin/bash
echo "Installing Docker (if necessary)..."
sudo apt-get update
sudo apt-get install -y docker.io docker-compose

echo "Starting Metabase Docker Container..."
cd /home/mason_ycw/boiling-noodles-dashboard/metabase
mkdir -p metabase-data
sudo docker-compose up -d

echo "Checking running containers..."
sudo docker ps

echo "🎉 Metabase should be available at http://34.81.51.45:3000 in a few moments."
