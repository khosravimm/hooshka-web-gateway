# MCP Definition: Model Compatibility Proxy

**Critical Distinction:** This project's **MCP (Model Compatibility Proxy)** is **NOT** the same as **Model Context Protocol** (Anthropic's open standard for LLM-tool integration).

| Aspect | This Project's MCP | Model Context Protocol |
|--------|-------------------|------------------------|
| **Full Name** | Model Compatibility Proxy | Model Context Protocol |
| **Purpose** | Provider abstraction & API compatibility | Standardized LLM ↔ Tool communication |
| **Scope** | Gateway-internal translation layer | Cross-system protocol |
| **Audience** | Gateway developers | Agent/Tool developers |
| **Standard** | Internal project convention | Open industry standard (Anthropic) |

## What MCP Does in This Architecture

The MCP sits between the **Virtual LLM API** (what agents see) and **Provider Adapters** (what backends speak).

```
┌─────────────────────────────────────────────────────────────┐
│                    Virtual LLM API                          │
│  (OpenAI-compatible: chat.completions, streaming, models)  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     MCP LAYER                               │
│  ┌──────────────────┐  ┌────────────────────────────────┐  │
│  │ Request          │  │ Response                       │  │
│  │ Translator       │  │ Normalizer                     │  │
│  │                  │  │                                │  │
│  │ • Standard →     │  │ • Provider → Standard          │  │
│  │   Provider fmt   │  │ • Unified error handling       │  │
│  │ • Param mapping  │  │ • Streaming normalization      │  │
│  │ • Auth injection │  │ • Token counting               │  │
│  └──────────────────┘  └────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Provider Adapter                          │
│  (Implements Provider interface, speaks backend protocol)   │
└─────────────────────────────────────────────────────────────┘
```

## MCP Responsibilities

### 1. Request Translation
- Convert standard `ChatCompletionRequest` → Provider-specific request format
- Map parameters: `temperature`, `top_p`, `max_tokens`, `tools`, `tool_choice`
- Inject provider-specific authentication/headers
- Handle provider-specific quirks (e.g., ChatGPT Web requires conversation context)

### 2. Response Normalization
- Convert provider response → standard `ChatCompletionResponse`
- Normalize streaming chunks to SSE format
- Unify error formats (map provider errors → standard error codes)
- Extract usage/token counts consistently

### 3. Session/Context Bridge
- Map standard `conversation_id` → provider session mechanism
- Handle context window differences
- Manage conversation history translation

### 4. Capability Negotiation
- Advertise what the virtual API supports
- Map to provider capabilities
- Graceful degradation for unsupported features

## What MCP Does NOT Do
- **Not** a protocol for tool/function calling (that's Model Context Protocol)
- **Not** a message format for agent-tool communication
- **Not** a transport protocol (uses HTTP/SSE internally)
- **Not** a replacement for provider SDKs (wraps them)

## Naming Convention
In code: `mcp/` package, `MCPTranslator`, `MCPNormalizer`, `MCPError`
In docs: Always qualify as "Model Compatibility Proxy" on first use