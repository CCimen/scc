# Troubleshooting

Common problems and how to fix them.

## Quick Diagnosis

Run `scc doctor` first. It checks Docker, config, and common issues.

```bash
scc doctor
```

## Plugin or Server Blocked

**Symptom**: You add a plugin or MCP server but it doesn't appear in your session.

**Diagnosis**:
```bash
scc config explain --field plugins
```

Look for `blocked_items` in the output.

**Cause**: The resource matches a pattern in `security.blocked_plugins` or `security.blocked_mcp_servers` in your organization config. These patterns use glob matching (e.g., `malicious-*` blocks `malicious-tool`, `malicious-helper`, etc.).

**Solution**: Security blocks are absolute. Contact your organization admin to request an exception or use a different resource.

## Addition Denied

**Symptom**: Your `.scc.yaml` additions are ignored.

**Diagnosis**:
```bash
scc config explain
```

Look for `denied_additions` in the output.

**Possible causes**:

1. **Team not delegated for plugins**
   - Your team isn't in the org's `delegation.teams.allow_additional_plugins` list
   - Solution: Ask org admin to add your team

2. **Team not delegated for MCP servers**
   - Your team isn't in `delegation.teams.allow_additional_mcp_servers`
   - Solution: Ask org admin to delegate MCP server additions to your team

3. **Project overrides disabled**
   - Your team profile has `delegation.allow_project_overrides: false`
   - Solution: Ask team lead to enable project overrides, or add the resource to the team profile instead

## Organization Config Fetch Failed

**Symptom**: `scc start` fails with "Failed to fetch organization config"

**Diagnosis**:
```bash
scc doctor
```

**Possible causes**:

1. **Network unreachable**
   - Check your internet connection
   - Check if the config URL is accessible from your network

2. **Auth token expired**
   - If using `env:TOKEN`, verify the environment variable is set and valid
   - If using `command:...`, verify the command returns a valid token

3. **URL changed**
   - Run `scc setup` to reconfigure the organization URL

**Workaround**: Use offline mode with cached config:
```bash
scc start ~/repo --offline
```

This only works if you've successfully fetched the config before.

## Docker Not Running

**Symptom**: "Cannot connect to Docker daemon"

**Solutions**:

**macOS/Windows**: Start Docker Desktop

**Linux**:
```bash
sudo systemctl start docker
```

If you're not in the docker group:
```bash
sudo usermod -aG docker $USER
# Log out and back in
```

## Slow File Operations (WSL2)

**Symptom**: Everything is slow. File reads take seconds.

**Cause**: Your project is on the Windows filesystem (`/mnt/c/...`). The WSL2/Windows bridge is slow.

**Solution**: Move your project to the Linux filesystem:
```bash
mkdir -p ~/projects
cp -r /mnt/c/Users/you/project ~/projects/
cd ~/projects/project
scc start .
```

The speed difference is dramatic. Plan for 10-100x faster file operations.

## Team Profile Not Found

**Symptom**: `scc start --team myteam` fails with "Team not found"

**Diagnosis**:
```bash
scc teams
```

**Possible causes**:

1. **Typo in team name** - Names are case-sensitive
2. **Team not in org config** - Ask org admin to add the team profile
3. **Stale cache** - Refresh with `scc teams --sync`

## Session Won't Resume

**Symptom**: `scc start --continue` doesn't find your session

**Diagnosis**:
```bash
scc sessions
```

**Possible causes**:

1. **Container removed** - Run `docker container prune` carefully; it removes stopped containers
2. **Different workspace** - `--continue` matches by workspace path
3. **No previous sessions** - Check `~/.cache/scc/` for session data

**Solution**: Start fresh:
```bash
scc start ~/repo --fresh
```

## Stats Show "Incomplete"

**Symptom**: `scc stats` shows sessions marked incomplete

**Cause**: On Unix systems, SCC can't record session end time because `os.execvp` replaces the process. This is expected behavior.

Sessions without clean exit use the expected duration from config as an estimate. The session count is accurate; only actual duration is estimated.

## Config Changes Not Taking Effect

**Symptom**: You updated org config but `scc` still uses old values

**Possible causes**:

1. **Cache TTL not expired** - Org config caches for 1 hour
   ```bash
   scc teams --sync  # Force refresh
   ```

2. **User config override** - Check `~/.config/scc/config.json`

3. **CLI flag override** - Flags like `--team` override config

**Full reset**:
```bash
rm -rf ~/.cache/scc/
scc teams --sync
```

## Container Accumulation

**Symptom**: Docker uses lots of disk space

**Cause**: SCC creates containers that aren't auto-cleaned

**Solution**:
```bash
# List scc containers
docker ps -a --filter "name=scc-"

# Remove stopped containers
docker container prune

# Remove old scc containers specifically
docker rm $(docker ps -a -q --filter "name=scc-" --filter "status=exited")
```

## MCP Server Connection Failed

**Symptom**: MCP server defined in config but Claude can't connect

**Diagnosis**: Check the server definition in `scc config explain`.

**For SSE servers**:
- Verify the URL is reachable from inside the container
- Check if the server requires authentication

**For stdio servers**:
- Verify the command exists inside the container
- Check if args are correct

**Network issues**: The container has full network access. If the MCP server is on localhost, use `host.docker.internal` instead of `localhost`.

## Getting Help

If none of these solutions work:

1. Run `scc doctor --verbose` and note any warnings
2. Run `scc config explain` to see effective configuration
3. Check the [Architecture docs](ARCHITECTURE.md) to understand the config flow
4. Open an issue with the diagnostic output
