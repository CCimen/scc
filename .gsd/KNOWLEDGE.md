# KNOWLEDGE.md

## Stable rules and lessons
- Provider-core destinations must be validated before launch. Do not make users discover missing provider access at runtime.
- GitHub/npm/PyPI are not provider-core. They are optional named destination sets.
- Network-tool wrappers are defense-in-depth in enforced modes. Topology plus proxy policy remain the hard egress control.
- Runtime wrappers are the cross-provider baseline. Claude hooks and Codex-native features are UX layers.
- Do not introduce provider-specific fields into core contracts just because one adapter needs them today.
- Typed contracts are part of maintainability, not polish.
- Do not rename controls in a way that sounds stronger than the actual enforcement.
- Keep Beads and `.gsd/` state rooted in the synced repo only.
