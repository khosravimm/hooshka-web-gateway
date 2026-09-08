# Provider Adapter Contract

This document defines the interface that all provider adapters must implement to work with the Virtual LLM API Gateway.

## Provider Interface (Python Protocol)

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional
from dataclasses import dataclass
from enum import Enum

class ProviderType(Enum):
    CHATGPT_WEB = "chatgpt_web"
    OPENAI_API = "openai_api"
    ANTHROPIC = "anthropic"
    LOCAL_LLM = "local_llm"
    CUSTOM = "custom"

@dataclass
class ProviderCapabilities:
    """What this provider supports"""
    chat_completion: bool = True
    streaming: bool = True
    tools: bool = False
    vision: bool = False
    embeddings: bool = False
    max_context_tokens: int = 4096
    supported_models: list[str] = None

@dataclass
class ProviderConfig:
    """Provider-specific configuration"""
    provider_id: str
    provider_type: ProviderType
    enabled: bool = True
    priority: int = 100  # Lower = higher priority
    config: dict = None  # Provider-specific settings
    capabilities: ProviderCapabilities = None

class Provider(ABC):
    """Base interface for all LLM providers"""
    
    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier for this provider instance"""
        pass
    
    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """Type category of this provider"""
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """What this provider can do"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is available"""
        pass
    
    @abstractmethod
    async def chat_completion(
        self,
        request: "ChatCompletionRequest",
        session: Optional["SessionContext"] = None
    ) -> "ChatCompletionResponse":
        """Non-streaming chat completion"""
        pass
    
    @abstractmethod
    async def chat_completion_stream(
        self,
        request: "ChatCompletionRequest",
        session: Optional["SessionContext"] = None
    ) -> AsyncIterator["ChatCompletionChunk"]:
        """Streaming chat completion"""
        pass
    
    @abstractmethod
    async def list_models(self) -> list["ModelInfo"]:
        """List available models"""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Cleanup resources"""
        pass


# Standard Request/Response Models (MCP Internal)

@dataclass
class ChatCompletionRequest:
    model: str
    messages: list[dict]  # Standard OpenAI format
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    max_tokens: Optional[int] = None
    stream: bool = False
    tools: Optional[list[dict]] = None
    tool_choice: Optional[dict] = None
    user: Optional[str] = None
    # Extension fields
    conversation_id: Optional[str] = None
    provider_options: Optional[dict] = None

@dataclass
class ChatCompletionResponse:
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list["Choice"]
    usage: "Usage"
    provider_meta: Optional[dict] = None

@dataclass
class Choice:
    index: int
    message: "Message"
    finish_reason: str

@dataclass
class Message:
    role: str
    content: Optional[str] = None
    tool_calls: Optional[list] = None

@dataclass
class Usage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

@dataclass
class ChatCompletionChunk:
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: list["ChunkChoice"]
    provider_meta: Optional[dict] = None

@dataclass
class ChunkChoice:
    index: int
    delta: "Delta"
    finish_reason: Optional[str] = None

@dataclass
class Delta:
    role: Optional[str] = None
    content: Optional[str] = None
    tool_calls: Optional[list] = None

@dataclass
class ModelInfo:
    id: str
    object: str = "model"
    owned_by: str
    provider: str

@dataclass
class SessionContext:
    conversation_id: str
    provider_session_id: Optional[str] = None
    metadata: dict = None
    created_at: int = 0
    updated_at: int = 0
```

## Provider Adapter Implementation Requirements

### 1. Configuration
Each adapter must accept a `ProviderConfig` at initialization.

### 2. Lifecycle
- `health_check()` - Must be fast (< 5s), used for routing decisions
- `close()` - Must release all resources (browser, connections, etc.)

### 3. Request Handling
- Must accept standard `ChatCompletionRequest`
- Must return standard `ChatCompletionResponse` or `AsyncIterator[ChatCompletionChunk]`
- Must handle `conversation_id` for session continuity
- Must respect `stream` parameter

### 4. Error Handling
- Raise `ProviderError` (defined in MCP) for provider-specific failures
- Map provider errors to standard error codes where possible

### 5. Concurrency
- Must be thread-safe / async-safe
- Multiple concurrent requests supported

### 6. Observability
- Log structured events: request_start, request_complete, error
- Include `provider_id`, `conversation_id`, latency, token counts

## ChatGPT Web Provider Specifics

### Adapter Variants
| Variant | Implementation | Use Case |
|---------|---------------|----------|
| `dom` | Playwright DOM automation | Reliable, non-streaming |
| `network` | CDP/WebSocket interception | Streaming, faster |

### Configuration
```python
@dataclass
class ChatGPTWebConfig(ProviderConfig):
    cdp_url: str = "http://127.0.0.1:9222"
    chatgpt_url: str = "https://chatgpt.com"
    adapter: str = "dom"  # or "network"
    headless: bool = False
    timeout: int = 120
    long_text_chunk_size: int = 15000
```

### Session Management
- Uses ChatGPT conversation URL as `provider_session_id`
- Supports `conversation_id` passthrough for continuity
- New conversations created automatically when needed

## Adding New Providers

1. Create new adapter in `adapters/<provider_name>.py`
2. Implement `Provider` interface
3. Register in `core/provider_registry.py`
4. Add configuration schema in `core/config.py`
5. Write tests in `tests/providers/test_<provider_name>.py`
6. Update `docs/architecture/provider-adapter-contract.md`

## Testing Contract

All providers must pass:
- `test_health_check()`
- `test_chat_completion_basic()`
- `test_chat_completion_streaming()`
- `test_conversation_continuity()`
- `test_error_handling()`
- `test_concurrent_requests()`
- `test_model_listing()`