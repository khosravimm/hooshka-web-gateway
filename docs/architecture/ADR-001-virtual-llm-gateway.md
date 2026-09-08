# ADR-001: Virtual LLM API Gateway Architecture

**Status:** Accepted
**Date:** 2026-09-07
**Deciders:** Architecture Team

## Context

AI Agents currently couple directly to specific LLM providers (OpenAI, Anthropic, Google, Ollama, vLLM, ChatGPT Web, etc.). Each provider has:
- Different API contracts
- Different session management
- Different request/response formats
- Different capabilities and limitations

This creates vendor lock-in and makes it impossible to swap backends without modifying agent code.

## Decision

We will implement a **Virtual LLM API Gateway** with a **Model Compatibility Proxy (MCP)** layer that provides:

1. **Standardized API** for agents (OpenAI-compatible chat completions, streaming, embeddings)
2. **Provider Abstraction** via a `Provider` interface
3. **MCP Layer** for request translation and response normalization
4. **Provider Registry** for dynamic backend selection
4. **Governance Layer** for auth, rate limiting, audit logging

## Architecture

```
Agent Runtime
      |
Virtual LLM API (OpenAI-compatible)
      |
      v
+---------------------+
|      MCP Layer      |  <-- Request Translation / Response Normalization
|  (Compatibility     |
|   Proxy)            |
+---------------------+
      |
      v
+---------------------+
|  Provider Registry  |  <-- Dynamic provider selection
+---------------------+
      |
      v
+------------+------------+------------+------------+
|            |            |            |            |
OpenAI     ChatGPT      Local LLM    Custom
Provider   Web          (Ollama/     Provider
           Adapter      vLLM)        Adapter
```

## Consequences

### Positive
- Agents depend only on standard API, not provider specifics
- Backend can be swapped without agent changes
- Providers without official APIs (ChatGPT Web) become accessible
- Centralized governance (auth, rate limits, audit)
- Multi-provider routing strategies possible

### Negative
- Additional latency from translation layer
- More complex deployment
- Must maintain compatibility with evolving provider APIs

## Implementation Phases

### Phase 1 (Current): Foundation + ChatGPT Web Provider
- Provider interface and base classes
- MCP translation/normalization layer
- Provider registry and configuration
- ChatGPT Web provider (DOM + Network adapters)
- Basic governance middleware

### Phase 2: Additional Providers
- OpenAI API provider
- Anthropic Claude provider
- Local LLM provider (Ollama/vLLM)

### Phase 3: Advanced Governance
- Authentication/Authorization
- Rate limiting with quotas
- Audit trail and compliance
- Policy enforcement engine

## References
- [MCP Definition](./mcp-definition.md)
- [Provider Adapter Contract](./provider-adapter-contract.md)
- [Governance Model](./governance-model.md)