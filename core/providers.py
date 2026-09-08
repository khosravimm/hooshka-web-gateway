from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional, Any
from enum import Enum
import time
import uuid


class ProviderType(Enum):
    CHATGPT_WEB = "chatgpt_web"
    OPENAI_API = "openai_api"
    ANTHROPIC = "anthropic"
    LOCAL_LLM = "local_llm"
    CUSTOM = "custom"


@dataclass
class ProviderCapabilities:
    chat_completion: bool = True
    streaming: bool = True
    tools: bool = False
    vision: bool = False
    embeddings: bool = False
    max_context_tokens: int = 4096
    supported_models: list[str] = field(default_factory=list)


@dataclass
class ProviderConfig:
    provider_id: str
    provider_type: ProviderType
    enabled: bool = True
    priority: int = 100
    config: dict = field(default_factory=dict)
    capabilities: Optional[ProviderCapabilities] = None


@dataclass
class ChatCompletionRequest:
    model: str
    messages: list[dict]
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    max_tokens: Optional[int] = None
    stream: bool = False
    tools: Optional[list[dict]] = None
    tool_choice: Optional[dict] = None
    user: Optional[str] = None
    conversation_id: Optional[str] = None
    provider_options: Optional[dict] = None


@dataclass
class ChatCompletionResponse:
    id: str
    created: int
    model: str
    choices: list["Choice"]
    usage: "Usage"
    object: str = "chat.completion"
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
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ChatCompletionChunk:
    id: str
    created: int
    model: str
    choices: list["ChunkChoice"]
    object: str = "chat.completion.chunk"
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
    owned_by: str
    provider: str
    object: str = "model"


@dataclass
class SessionContext:
    conversation_id: str
    provider_session_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    created_at: int = field(default_factory=lambda: int(time.time()))
    updated_at: int = field(default_factory=lambda: int(time.time()))


class ProviderError(Exception):
    def __init__(self, message: str, code: str = "provider_error", provider_id: str = "", details: dict = None):
        super().__init__(message)
        self.code = code
        self.provider_id = provider_id
        self.details = details or {}


class ProviderUnavailableError(ProviderError):
    def __init__(self, provider_id: str, message: str = "Provider unavailable"):
        super().__init__(message, "provider_unavailable", provider_id)


class ProviderTimeoutError(ProviderError):
    def __init__(self, provider_id: str, message: str = "Provider timeout"):
        super().__init__(message, "provider_timeout", provider_id)


class ProviderAuthError(ProviderError):
    def __init__(self, provider_id: str, message: str = "Authentication failed"):
        super().__init__(message, "authentication_failed", provider_id)


class Provider(ABC):
    def __init__(self, config: ProviderConfig):
        self._config = config
        self._capabilities = config.capabilities or ProviderCapabilities()
    
    @property
    def provider_id(self) -> str:
        return self._config.provider_id
    
    @property
    def provider_type(self) -> ProviderType:
        return self._config.provider_type
    
    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._capabilities
    
    @property
    def config(self) -> ProviderConfig:
        return self._config
    
    @abstractmethod
    async def health_check(self) -> bool:
        pass
    
    @abstractmethod
    async def chat_completion(
        self,
        request: ChatCompletionRequest,
        session: Optional[SessionContext] = None
    ) -> ChatCompletionResponse:
        pass
    
    @abstractmethod
    async def chat_completion_stream(
        self,
        request: ChatCompletionRequest,
        session: Optional[SessionContext] = None
    ) -> AsyncIterator[ChatCompletionChunk]:
        pass
    
    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        pass
    
    @abstractmethod
    async def close(self) -> None:
        pass
    
    def _generate_id(self, prefix: str = "chatcmpl") -> str:
        return f"{prefix}-{uuid.uuid4().hex[:8]}"
    
    def _current_timestamp(self) -> int:
        return int(time.time())