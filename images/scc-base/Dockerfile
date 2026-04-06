# scc-base: Foundation image for all SCC agent containers.
# Provides a non-root agent user, essential CLI tools, safety wrappers,
# and a clean HOME.
FROM ubuntu:22.04

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        curl \
        wget \
        openssh-client \
        rsync \
        python3 \
        ca-certificates \
        jq \
    && rm -rf /var/lib/apt/lists/*

# Install the standalone safety evaluator and wrapper scripts
COPY wrappers/scc_safety_eval/ /usr/local/lib/scc/scc_safety_eval/
COPY wrappers/bin/ /usr/local/lib/scc/bin/
RUN chmod +x /usr/local/lib/scc/bin/*

# Make the evaluator importable and wrappers first in PATH
ENV PYTHONPATH=/usr/local/lib/scc
ENV PATH="/usr/local/lib/scc/bin:$PATH"

# Create agent user (uid 1000) with home directory
RUN useradd -m -u 1000 -s /bin/bash agent

# Pre-create provider config directories owned by agent with strict permissions
RUN mkdir -p /home/agent/.claude /home/agent/.codex \
    && chmod 0700 /home/agent/.claude /home/agent/.codex \
    && chown agent:agent /home/agent/.claude /home/agent/.codex

USER agent
WORKDIR /home/agent
