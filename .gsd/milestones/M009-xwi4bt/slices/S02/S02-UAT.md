# S02: Setup three-tier consistency and final verification — UAT

**Milestone:** M009-xwi4bt
**Written:** 2026-04-06T17:08:40.988Z

## UAT: Setup Three-Tier Consistency

### Preconditions
- SCC installed and configured with at least one provider (Claude or Codex)
- Docker/OCI runtime available for image-present checks

### Test 1: Onboarding status panel shows four-state readiness
1. Run `scc setup` (or trigger the onboarding status panel)
2. Observe the provider status table
3. **Expected:** Each provider shows one of: ✅ launch-ready, 🔑 auth cache present, 📦 image available, ❌ sign-in needed
4. **Expected:** No provider shows the old two-tier wording ("Docker available" / "not configured")

### Test 2: Setup completion summary matches onboarding panel vocabulary
1. Complete setup successfully
2. Observe the completion summary's provider readiness section
3. **Expected:** Uses the same four-state vocabulary as the onboarding status panel (launch-ready / auth cache present / image available / sign-in needed)
4. **Expected:** Both surfaces produce identical status text for the same provider state

### Test 3: Provider preference hints in next-steps
1. Complete setup successfully
2. Observe the "Get started" next-steps section
3. **Expected:** Shows `scc provider show` with description "Show current provider preference"
4. **Expected:** Shows `scc provider set` with description "Set preference (ask|claude|codex)"

### Test 4: Provider with auth but no image
1. Configure a provider with auth credentials cached but container image not pulled
2. Run setup and observe status
3. **Expected:** Shows "auth cache present" (not "launch-ready" and not "sign-in needed")

### Test 5: Provider with image but no auth
1. Pull provider image but remove auth credentials
2. Run setup and observe status
3. **Expected:** Shows "image available" (not "launch-ready" and not "sign-in needed")

### Edge Cases
- **No providers configured:** Both panels show ❌ sign-in needed for all providers
- **Both providers launch-ready:** Both panels show ✅ launch-ready for both
