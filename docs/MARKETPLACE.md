# SCC Marketplace Plugins

SCC supports marketplace plugins that extend Claude Code functionality. Plugins are distributed via Git repositories and managed centrally by organizations.

## Official Marketplace

The official SCC plugin marketplace is hosted at:

```
https://github.com/CCimen/sandboxed-code-plugins
```

### Enabling the Official Marketplace

Add this to your org config:

```json
{
    "marketplaces": {
        "sandboxed-code-official": {
            "source": "github",
            "owner": "CCimen",
            "repo": "sandboxed-code-plugins"
        }
    }
}
```

## Available Plugins

### scc-safety-net

Protects remote git history and uncommitted work from accidental destructive commands.

**What it blocks:**

| Command | Risk | Safe Alternative |
|---------|------|------------------|
| `git push --force` | Overwrites remote history | `git push --force-with-lease` |
| `git push +main` | Force push via refspec | `git push --force-with-lease` |
| `git reset --hard` | Destroys uncommitted changes | `git stash` |
| `git branch -D` | Deletes without merge check | `git branch -d` |
| `git stash drop/clear` | Permanently loses stashed work | Review first |
| `git clean -f` | Deletes untracked files | `git clean -n` (dry-run) |
| `git checkout -- <file>` | Discards file changes | `git stash` |
| `git restore <file>` | Discards worktree changes | `git restore --staged` |

Bypass attempts through `sudo`, `bash -c`, and command chaining are also caught.

**Enable in your org config:**

```json
{
    "defaults": {
        "enabled_plugins": ["scc-safety-net@sandboxed-code-official"]
    }
}
```

Or per-team:

```json
{
    "profiles": {
        "engineering": {
            "additional_plugins": ["scc-safety-net@sandboxed-code-official"]
        }
    }
}
```

**Configuration:**

The plugin reads policy from `security.safety_net` in your org config:

```json
{
    "security": {
        "safety_net": {
            "action": "block",
            "block_force_push": true,
            "block_reset_hard": true,
            "block_branch_force_delete": true,
            "block_checkout_restore": true,
            "block_clean": true,
            "block_stash_destructive": true
        }
    }
}
```

| Option | Default | Description |
|--------|---------|-------------|
| `action` | `block` | `block`, `warn`, or `allow` |
| `block_force_push` | `true` | Block `git push --force` and `+refspec` |
| `block_reset_hard` | `true` | Block `git reset --hard` |
| `block_branch_force_delete` | `true` | Block `git branch -D` |
| `block_checkout_restore` | `true` | Block `git checkout -- <file>` and `git restore <file>` |
| `block_clean` | `true` | Block `git clean -f` |
| `block_stash_destructive` | `true` | Block `git stash drop/clear` |

**Checking status:**

Inside Claude Code, run `/scc-safety-net:status` to see the effective policy.

## Creating Custom Marketplaces

Organizations can host their own plugin marketplaces. See [GOVERNANCE.md](./GOVERNANCE.md) for trust configuration.

```json
{
    "marketplaces": {
        "internal-plugins": {
            "source": "github",
            "owner": "my-org",
            "repo": "scc-plugins"
        }
    },
    "defaults": {
        "enabled_plugins": ["my-plugin@internal-plugins"]
    }
}
```

## Plugin Format

Plugins are directories containing:

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json       # Plugin metadata
├── hooks/
│   └── hooks.json        # Hook registrations
├── commands/
│   └── *.md              # Slash commands
└── scripts/
    └── *.py              # Hook implementations
```

See the [scc-safety-net source](https://github.com/CCimen/sandboxed-code-plugins/tree/main/scc-safety-net) for a complete example.
