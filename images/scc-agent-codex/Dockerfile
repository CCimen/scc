# scc-agent-codex: OpenAI Codex CLI agent image built on scc-base.
# Installs the current Node.js LTS line and the Codex CLI globally.
FROM scc-base:latest

# Default to the current active Node.js LTS line.
ARG NODE_MAJOR=24

# Pin the Codex CLI version for deterministic builds.
# Override at build time: docker build --build-arg CODEX_VERSION=0.1.2 ...
ARG CODEX_VERSION=latest

# Switch to root for system-level installs
USER root

# Install Node.js via NodeSource plus browser-auth/runtime helpers.
# Use a clean system PATH for this step so the bootstrap script does not pick
# up SCC's runtime safety wrappers from scc-base during image construction.
RUN export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    && /usr/bin/curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash - \
    && apt-get install -y --no-install-recommends nodejs bubblewrap socat \
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
