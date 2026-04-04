# S01: Provider selection config, CLI flag, and bootstrap dispatch — UAT

**Milestone:** M006-d622bc
**Written:** 2026-04-04T23:17:37.002Z

## UAT: Provider selection config, CLI flag, and bootstrap dispatch

### Preconditions
- SCC installed and runnable (`uv run scc --help` works)
- No prior provider config set (clean user config state)

### Test 1: Default provider is Claude
1. Run `scc provider show`
2. **Expected:** Output contains `claude`

### Test 2: Set provider to Codex
1. Run `scc provider set codex`
2. **Expected:** Confirmation message printed
3. Run `scc provider show`
4. **Expected:** Output contains `codex`

### Test 3: Set provider back to Claude
1. Run `scc provider set claude`
2. **Expected:** Confirmation message printed
3. Run `scc provider show`
4. **Expected:** Output contains `claude`

### Test 4: Invalid provider rejected
1. Run `scc provider set gemini`
2. **Expected:** Error message listing known providers (claude, codex)
3. Run `scc provider show`
4. **Expected:** Previous provider unchanged

### Test 5: --provider flag on scc start
1. Run `scc start --provider codex --dry-run` (or observe help)
2. **Expected:** The `--provider` option is accepted without error. Provider resolution uses the flag value.

### Test 6: CLI flag overrides config
1. Set config to claude: `scc provider set claude`
2. Start with `--provider codex`
3. **Expected:** Codex provider is resolved (flag beats config)

### Test 7: Policy violation
1. Configure a team org config with `allowed_providers: ["claude"]`
2. Run `scc start --provider codex`
3. **Expected:** `ProviderNotAllowedError` with message explaining codex is not allowed and listing permitted providers

### Test 8: Bare scc provider shows help
1. Run `scc provider`
2. **Expected:** Usage/help text displayed showing available subcommands (show, set)

### Edge Cases
- `scc provider set CLAUDE` (uppercase) → should be rejected (case-sensitive matching against KNOWN_PROVIDERS)
- Empty allowed_providers in team config → all providers permitted (no restriction)
- No team config at all → all providers permitted (graceful fallback)
