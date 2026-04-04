# scc-base: Foundation image for all SCC agent containers.
# Provides a non-root agent user, essential CLI tools, and a clean HOME.
FROM ubuntu:22.04

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
        jq \
    && rm -rf /var/lib/apt/lists/*

# Create agent user (uid 1000) with home directory
RUN useradd -m -u 1000 -s /bin/bash agent

# Pre-create the Claude config directory owned by agent
RUN mkdir -p /home/agent/.claude \
    && chown agent:agent /home/agent/.claude

USER agent
WORKDIR /home/agent
