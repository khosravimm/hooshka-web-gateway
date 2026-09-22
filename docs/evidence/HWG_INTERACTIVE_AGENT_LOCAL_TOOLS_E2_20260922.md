# HWG Interactive Agent Local Tools — E2 Evidence

Date: 2026-09-22
Scope: Control Panel Interactive Chat / `deepseek-web`
User case: `لیست فایل های درایو D را نمایش بده`

## Defect
The Interactive Chat previously sent a plain chat request without any tool definitions or execution loop. The provider therefore truthfully answered that it had no filesystem access. This violated the intended HWG agent role.

## Correction
The interactive chat now enables governed Agent mode. HWG exposes read-only `list_files`, `read_file`, and `search_files` tools to the provider, receives structured tool calls, executes them inside configured local read roots, returns tool results to the provider, and asks the provider to synthesize the final human-readable answer.

Tool execution is server-side; the Web provider itself never receives direct filesystem authority. Unknown/write/command tools fail closed. The current Windows default read root is `D:\`.

## Live E2
A real request to `/v1/chat/conversation` with `agent_mode=true` returned HTTP 200 and `provider_meta.agent_mode=true`. DeepSeek requested `list_files`, HWG executed it locally, and the final response contained the actual D:\ root directories and files.

A browser-level Control Panel test then opened Interactive Chat, selected `deepseek-web`, submitted the same request, and rendered the actual D:\ listing. The response metadata showed `Agent: فعال`; browser console errors: 0.

Result: **E2 PASS for the scoped read-only filesystem agent path.** This does not certify arbitrary command execution or write tools.
