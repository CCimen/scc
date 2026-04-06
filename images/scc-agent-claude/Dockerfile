# scc-agent-claude: Claude Code agent image built on scc-base.
# Installs the current Node.js LTS line and the Claude CLI globally.
FROM scc-base:latest

# Default to the current active Node.js LTS line.
ARG NODE_MAJOR=24

# Switch to root for system-level installs
USER root

# Install Node.js via NodeSource.
# Use a clean system PATH for this step so the bootstrap script does not pick
# up SCC's runtime safety wrappers from scc-base during image construction.
RUN export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    && /usr/bin/curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Verify installation
RUN claude --version

# Switch back to the non-root agent user
USER agent
WORKDIR /home/agent

# The OCI adapter will exec claude explicitly; bash as default entrypoint
ENTRYPOINT ["/bin/bash"]
