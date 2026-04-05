# scc-agent-codex: OpenAI Codex CLI agent image built on scc-base.
# Installs Node.js 20 LTS and the Codex CLI globally.
FROM scc-base:latest

# Pin the Codex CLI version for deterministic builds.
# Override at build time: docker build --build-arg CODEX_VERSION=0.1.2 ...
ARG CODEX_VERSION=latest

# Switch to root for system-level installs
USER root

# Install Node.js 20 LTS via NodeSource
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Codex CLI globally (version pinned via ARG)
RUN if [ "$CODEX_VERSION" = "latest" ]; then \
        npm install -g @openai/codex; \
    else \
        npm install -g @openai/codex@"$CODEX_VERSION"; \
    fi

# Verify installation
RUN codex --version

# Switch back to the non-root agent user
USER agent
WORKDIR /home/agent

# The OCI adapter will exec codex explicitly; bash as default entrypoint
ENTRYPOINT ["/bin/bash"]
