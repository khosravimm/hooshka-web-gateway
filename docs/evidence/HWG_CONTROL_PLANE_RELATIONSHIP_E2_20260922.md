# HWG Control Plane Relationship Redesign — E2 Evidence

- Date: 2026-09-22
- Scope: `HWG-WORK-006`, Management UI §11
- Application: `1.0.0-dev.6`
- Evidence: E1 + scoped E2

## Relationship model

The Control Plane now separates four operational workspaces: Browser Runtimes, Browser Profiles, Account Instances, and Discovery/Certification. Provider remains a separate logical-management workspace.

The visible operational chain is:

`Browser Profile → Browser Runtime → Account/Login → Provider Profile → Discovery & Functional Readiness`

Account cards render the concrete relationship:

`Provider Profile → Account Instance → Browser Profile/Origin → Runtime → Session → Readiness`

## Browser E2

A temporary isolated Chrome profile opened the live development Control Plane on port 5080 and navigated the redesigned workspaces without modifying provider/account state.

Observed:
- Browser Runtime cards: 2
- Browser Profile cards: 5 real Chrome profiles
- Account Instance cards: 4
- Profiles navigation: present
- Accounts navigation: present
- Active Accounts panel rendered successfully
- Browser console errors: 0
