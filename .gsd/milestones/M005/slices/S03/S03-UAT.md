# S03: Typed config model adoption and strict typing cleanup — UAT

**Milestone:** M005
**Written:** 2026-04-04T18:25:17.741Z

## S03 UAT: Typed Config Model Adoption\n\n### Test 1: Governed-artifact types are importable and frozen\n```bash\nuv run python -c \"from scc_cli.core.governed_artifacts import GovernedArtifact, ArtifactBundle, ArtifactRenderPlan; print('OK')\"\n```\nExpected: OK\n\n### Test 2: NormalizedOrgConfig.from_dict works\n```bash\nuv run python -c \"from scc_cli.ports.config_models import NormalizedOrgConfig; c = NormalizedOrgConfig.from_dict({'organization': {'name': 'test'}}); print(c.organization.name)\"\n```\nExpected: test\n\n### Test 3: dict[str,Any] count under target\n```bash\ngrep -rn 'dict\\[str, Any\\]' src/scc_cli/ --include='*.py' | grep -v __pycache__ | wc -l\n```\nExpected: < 390\n\n### Test 4: All tests pass\n```bash\nuv run pytest --rootdir \"$PWD\" -q\n```\nExpected: 4117+ passed
