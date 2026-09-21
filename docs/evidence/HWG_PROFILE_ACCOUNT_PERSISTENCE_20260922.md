# HWG Provider Profile / Account Instance Persistence Evidence — 2026-09-22

- Evidence ID: `HWG-EVID-PROFILE-ACCOUNT-PERSIST-20260922`
- Product version: `1.0.0-dev.5`
- Work item: `HWG-WORK-004`
- Evidence level: `E1 + live_local_migration`

## Architecture

A new non-secret persistent NG store is implemented in `core/profile_store.py`. Provider Profiles and Account Instances are stored as separate artifacts under `.runtime-dev/ng-store/provider_profiles/` and `.runtime-dev/ng-store/account_instances/`.

Each migrated artifact includes an artifact version, timestamp, source config SHA-256, and change log. No cookie, token, credential, API key, or browser-storage value is copied into the store.

`/panel/api/ng/inventory` now resolves through the persistent store when initialized. Legacy `config.yaml` projection is fallback-only for the NG relationship model. Runtime execution still uses config until later governed migration work.

## Reversibility

Migration writes a `migration.json` manifest containing created artifact paths and hashes. Rollback deletes only artifacts whose hashes still match the migration manifest. If an artifact changes after migration, rollback fails closed rather than deleting operator changes.

## Live local migration result

Using the real development `config.yaml` in the isolated worktree:

- first migration: `persistent_ng_store`, 4 Provider Profiles, 4 Account Instances, 1 relationship conflict;
- rollback: `rolled_back=true`, 8 created artifacts removed;
- post-rollback inventory: `legacy_projection`, `persistence_complete=false`;
- second migration: `persistent_ng_store`, 4 Provider Profiles, 4 Account Instances, 1 relationship conflict.

The remaining conflict is `.runtime-dev\shared-profile`, currently referenced by `chatgpt-web:default-account`, `deepseek-web:default-account`, and `zai-web:default-account`. Persistence does not hide or resolve this conflict; isolation remains a separate governed work item.

## E1 safeguards

Tests verify separate profile/account persistence, persistent-store authority after migration, conflict preservation, reversible migration, fail-closed rollback after artifact modification, and non-persistence of a synthetic API-key secret value.

No claim is made that profile isolation, account lifecycle, or runtime cutover is complete.
