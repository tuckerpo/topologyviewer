###############################################################
# SPDX-License-Identifier: BSD-2-Clause-Patent
# SPDX-FileCopyrightText: 2019-2020 the prplMesh contributors (see AUTHORS.md)
# This code is subject to the terms of the BSD+Patent license.
# See LICENSE file for more details.
###############################################################

####
## Python topologyviewer
####
FROM python:3.11.4-bullseye as python-req

RUN apt-get update \
    && apt-get -y install --no-install-recommends \
    graphviz nano vim jq \
    && apt-get clean

RUN useradd -ms /bin/bash pythonserver


####
## Topologyviewer runner
####
FROM python-req as topologyviewer_runner

#USER pythonserver
WORKDIR /home/pythonserver

# Checkout a fixed revision of the topologyviewer and install requirements
RUN printf '\033[1;35m%s Cloning Topologyviewer\n\033[0m' "$(date --iso-8601=seconds --universal)" \
    && git clone https://gitlab.com/prpl-foundation/prplmesh/topologyviewer.git topologyviewer \
    && printf '\033[1;35m%s Running server\n\033[0m' "$(date --iso-8601=seconds --universal)" \
    && cd topologyviewer \
    && git checkout 50d0a7114cebeba23a747360367d6d51ce751946

WORKDIR /home/pythonserver/topologyviewer

# Replaces python activate
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install -r requirements.txt

# Start topologyviewer app on container run on container run
CMD ["python", "main.py"]
