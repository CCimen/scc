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

## Base Image Blocked

**Symptom**: Container fails to start with "base image blocked by policy"

**Diagnosis**:
```bash
scc config explain --field security
```

Look for `blocked_base_images` patterns.

**Common cause**: Your org blocks `:latest` tags with a pattern like `*:latest`. SCC normalizes images without explicit tags by adding `:latest`, so `python` becomes `python:latest` which matches the block.

**Solution**: Use explicit version tags:
```yaml
# In .scc.yaml
base_image: python:3.12-slim
```

Not: `python` or `python:latest`

## Stdio MCP Server Blocked

**Symptom**: MCP server with `type: stdio` fails with "security policy prevents stdio MCP servers"

**Diagnosis**:
```bash
scc config explain --field security
```

Check if `allow_stdio_mcp` is `false` (the default).

**Cause**: Stdio MCP servers have elevated privileges (they run with mounted workspace, network access, and tokens). They're disabled by default for security.

**Solutions**:

1. **Use a different transport** - SSE or HTTP servers don't require the stdio gate:
   ```json
   {
     "name": "my-server",
     "type": "sse",
     "url": "https://mcp.example.com/my-server"
   }
   ```

2. **Request org admin enable stdio** - They must set `allow_stdio_mcp: true` in the org config security section

## Stdio Command Path Blocked

**Symptom**: Stdio MCP server fails with "command path not in allowed prefixes"

**Diagnosis**:
```bash
scc config explain --field security
```

Check the `allowed_stdio_prefixes` list.

**Cause**: When stdio is enabled, commands must reside in allowed paths. SCC resolves symlinks and validates the real path is under an allowed prefix.

**Examples**:
- Allowed prefixes: `["/usr/local/bin", "/opt/tools"]`
- `/usr/local/bin/mcp-tool` → allowed
- `/home/user/bin/mcp-tool` → blocked
- `/usr/local/bin/link` → symlink to `/home/user/actual` → blocked (real path checked)

**Solution**: Move the binary to an allowed prefix or ask org admin to add your path to `allowed_stdio_prefixes`.

## Pattern Matching is Case-Insensitive

**Symptom**: A plugin or image is blocked even though the pattern case doesn't match exactly.

**Example**:
- Pattern: `*-DEV`
- Blocked: `my-tool-dev`, `MyTool-Dev`, `MYTOOL-DEV`

**Cause**: All security patterns use case-insensitive matching via Unicode casefolding. This prevents bypass attempts using case variations.

**Solution**: This is expected security behavior. There is no workaround; the match is intentional.

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

**Quick unblock**: If you need the resource now, create a temporary local override:
```bash
scc unblock jira-api --ttl 8h --reason "Sprint planning integration"
```

This works for delegation denials only. Security blocks require a policy exception (see below).

## Exception Troubleshooting

### Local Override Not Working

**Symptom**: You ran `scc unblock` but the resource is still blocked.

**Diagnosis**:
```bash
scc config explain
```

Check if the item appears in `blocked_items` (security block) vs `denied_additions` (delegation denial).

**Cause**: Local overrides only work for delegation denials. Security blocks require policy exceptions.

**Solution for security blocks**:
```bash
scc exceptions create --policy --id INC-2025-001 \
  --allow-plugin vendor-tools --ttl 8h \
  --reason "Emergency vendor integration"
```

This generates YAML for a PR. Policy exceptions require review.

### Exception Already Expired

**Symptom**: `scc config explain` shows no active exceptions, but you created one.

**Diagnosis**:
```bash
scc exceptions list --all
```

Check if your exception appears as expired.

**Cause**: Exceptions have a max TTL of 24 hours. Default is 8 hours.

**Solution**: Create a new exception:
```bash
scc unblock target-name --ttl 8h --reason "Continuing work"
```

To clean up expired entries:
```bash
scc exceptions cleanup
```

### Corrupt Exception File

**Symptom**: Warning about corrupted exceptions file on startup.

SCC automatically backs up corrupt files to `~/.config/scc/exceptions.json.bak-YYYYMMDD`.

**Diagnosis**:
```bash
scc doctor
```

**Solution**: If the backup contains valid exceptions, restore it:
```bash
cp ~/.config/scc/exceptions.json.bak-20251221 ~/.config/scc/exceptions.json
```

To start fresh:
```bash
scc exceptions reset --user --yes
```

### Shared Exception Not Visible to Team

**Symptom**: You used `--shared` but teammates don't see the exception.

**Diagnosis**: Check if `.scc/exceptions.json` is in `.gitignore`:
```bash
git check-ignore .scc/exceptions.json
```

**Cause**: If the file is gitignored, it won't be committed and shared.

**Solutions**:
1. Remove from `.gitignore` and commit
2. Or use user-scoped exceptions instead (without `--shared`)

## Plugin Audit Failures

### Malformed Manifest

**Symptom**: `scc audit plugins` exits with code 1 and shows "malformed" status.

**Example output**:
```
Plugin: broken-tool
  .mcp.json: malformed (line 15, col 8: Expected ',' but found '}')
```

**Cause**: The plugin's `.mcp.json` or `hooks/hooks.json` contains invalid JSON.

**Solution**: Fix the JSON syntax in the plugin directory:
```bash
# Find the plugin location
scc audit plugins --json | grep -A5 '"name": "broken-tool"'

# Edit the manifest and fix the syntax error at the reported line/column
```

Common JSON errors:
- Missing comma between properties
- Trailing comma after last property
- Unquoted keys
- Single quotes instead of double quotes

### Unreadable Manifest

**Symptom**: `scc audit plugins` shows "unreadable" status.

**Cause**: Permission error reading the manifest file.

**Solution**:
```bash
# Check permissions on the plugin directory
ls -la ~/.claude/plugins/

# Fix permissions if needed
chmod -R u+r ~/.claude/plugins/broken-tool/
```

### CI Pipeline Fails on Audit

**Symptom**: CI job fails with exit code 1 from `scc audit plugins`.

**Cause**: One or more installed plugins have manifest problems. Exit code 1 means at least one manifest couldn't be parsed.

**Solution**: Run the audit locally with JSON output to identify the problem:
```bash
scc audit plugins --json
```

Look for plugins with `"status": "malformed"` or `"status": "unreadable"` in the output. Fix or remove those plugins.

### No Plugins Found

**Symptom**: `scc audit plugins` shows "No plugins installed."

**Cause**: The Claude Code plugin registry is empty or missing.

**Diagnosis**: Check if the registry exists:
```bash
cat ~/.claude/plugins/installed_plugins.json
```

This is informational only. If you haven't installed any Claude Code plugins, this is expected. The audit command exits with code 0 in this case.

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
