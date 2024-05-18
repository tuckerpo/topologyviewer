#!/bin/sh

# Run the topologyviewer
docker run -it --rm -p 8050:8050 --hostname "topology_server" --name "topology_runner" topologyviewer_img
