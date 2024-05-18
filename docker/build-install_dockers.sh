#!/bin/sh
scriptdir="$(cd "${0%/*}" || exit 1; pwd)"

# Build OBUSPA USP test controller in docker
# docker build -t obuspa_img OBUSPA/.

# Checkout topologyviewer repository
docker build -t topologyviewer_img ${scriptdir}
