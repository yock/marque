## Agent skills

### Issue tracker

Issues live in Gitea (gitea.yock.dev, yock/marque) via the `tea` CLI as the developer's account, `--login gitea.yock.dev`; the orchestrator acts as `--login yockbot` (see **Orchestrator identity** in `docs/agents/issue-tracker.md`).

### Triage labels

Default vocabulary: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `GLOSSARY.md` + `docs/adr/`. See `docs/agents/domain.md`.
