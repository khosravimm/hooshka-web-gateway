# HWG Discovery Workspace UX Hierarchy — E1/E2 Checkpoint

Date: 2026-09-26  
Build: `2.1.1-dev.discovery-workspace-ux.20260926-1055`  
Environment: Safe-Laptop Dev `5080` only

## Implemented

- Existing Qualification/resume is visually prioritized before advanced Discovery machinery.
- The technical Discovery process map is collapsed by default under `جزئیات فرایند Discovery`.
- The workspace is visibly segmented into: existing Qualifications, technical process details, advanced/research Run creation, and recorded Runs.
- New Web Chat and Resume remain primary user actions.

## Visual verification

- Unified Exploration/Preparation workspace rendered on Dev 5080.
- Existing Candidate card appears before technical Discovery details.
- Technical Discovery map is closed by default.
- New Web Chat, Resume, advanced Run creation and Run history are all present.
- Artifact: `.runtime-dev/connection-profile-e2/discovery-workspace-ux-1055.png`

## Evidence classification

- E1: information hierarchy and deterministic UI tests.
- E2 bounded: live rendering on Dev 5080 with the existing real Candidate state.
- Not claimed: final human acceptance or provider certification changes.

Production 5000 / release 2.1.0 was not changed.
