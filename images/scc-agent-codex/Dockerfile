# scc-agent-codex: OpenAI Codex CLI agent image built on scc-base.
# Installs Node.js 20 LTS and the Codex CLI globally.
FROM scc-base:latest

# Switch to root for system-level installs
USER root

# Install Node.js 20 LTS via NodeSource
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Codex CLI globally
RUN npm install -g @openai/codex

# Verify installation
RUN codex --version

# Switch back to the non-root agent user
USER agent
WORKDIR /home/agent

# The OCI adapter will exec codex explicitly; bash as default entrypoint
ENTRYPOINT ["/bin/bash"]
