from typing import Optional
from core.providers import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChunk,
    Choice,
    Message,
    Usage,
    ChunkChoice,
    Delta,
    ProviderError,
    Provider,
)
import logging
import time

logger = logging.getLogger(__name__)


class MCPTranslator:
    @staticmethod
    def translate_request(request: ChatCompletionRequest, provider: Provider) -> ChatCompletionRequest:
        translated = ChatCompletionRequest(
            model=request.model,
            messages=request.messages,
            temperature=request.temperature,
            top_p=request.top_p,
            max_tokens=request.max_tokens,
            stream=request.stream,
            tools=request.tools,
            tool_choice=request.tool_choice,
            user=request.user,
            conversation_id=request.conversation_id,
            provider_options=request.provider_options,
        )
        
        if provider.provider_type.value == "chatgpt_web":
            translated = MCPTranslator._adapt_for_chatgpt_web(translated, provider)
        
        logger.debug(f"Translated request for provider {provider.provider_id}: model={translated.model}, stream={translated.stream}")
        return translated
    
    @staticmethod
    def _adapt_for_chatgpt_web(request: ChatCompletionRequest, provider: Provider) -> ChatCompletionRequest:
        adapted = ChatCompletionRequest(
            model=request.model,
            messages=request.messages,
            temperature=request.temperature,
            top_p=request.top_p,
            max_tokens=request.max_tokens,
            stream=request.stream,
            tools=request.tools,
            tool_choice=request.tool_choice,
            user=request.user,
            conversation_id=request.conversation_id,
            provider_options=request.provider_options,
        )
        
        return adapted


class MCPNormalizer:
    @staticmethod
    def normalize_response(response: ChatCompletionResponse, provider: Provider) -> ChatCompletionResponse:
        normalized = ChatCompletionResponse(
            id=response.id or f"chatcmpl-{int(time.time() * 1000)}",
            object=response.object or "chat.completion",
            created=response.created or int(time.time()),
            model=response.model,
            choices=response.choices,
            usage=response.usage or Usage(),
            provider_meta={
                "provider_id": provider.provider_id,
                "provider_type": provider.provider_type.value,
                **(response.provider_meta or {}),
            },
        )
        
        if provider.provider_type.value == "chatgpt_web":
            normalized = MCPNormalizer._normalize_chatgpt_web(normalized, provider)
        
        return normalized
    
    @staticmethod
    def _normalize_chatgpt_web(response: ChatCompletionResponse, provider: Provider) -> ChatCompletionResponse:
        for choice in response.choices:
            if choice.message and choice.message.content:
                choice.message.content = choice.message.content.strip()
        
        if response.usage.total_tokens == 0:
            total_chars = sum(
                len(c.message.content or "") for c in response.choices
            )
            estimated_tokens = total_chars // 4
            response.usage = Usage(
                prompt_tokens=estimated_tokens // 3,
                completion_tokens=estimated_tokens * 2 // 3,
                total_tokens=estimated_tokens,
            )
        
        return response
    
    @staticmethod
    def normalize_chunk(chunk: ChatCompletionChunk, provider: Provider) -> ChatCompletionChunk:
        normalized = ChatCompletionChunk(
            id=chunk.id or f"chatcmpl-{int(time.time() * 1000)}",
            object=chunk.object or "chat.completion.chunk",
            created=chunk.created or int(time.time()),
            model=chunk.model,
            choices=chunk.choices,
            provider_meta={
                "provider_id": provider.provider_id,
                "provider_type": provider.provider_type.value,
                **(chunk.provider_meta or {}),
            },
        )
        
        return normalized
    
    @staticmethod
    def normalize_error(error: Exception, provider: Provider) -> dict:
        if isinstance(error, ProviderError):
            return {
                "error": {
                    "message": str(error),
                    "type": error.code,
                    "provider": error.provider_id,
                    "details": error.details,
                }
            }
        
        return {
            "error": {
                "message": str(error),
                "type": "internal_error",
                "provider": provider.provider_id,
            }
        }


class MCPSessionManager:
    def __init__(self):
        self._sessions: dict[str, dict] = {}
    
    def get_or_create_session(self, conversation_id: str, provider: Provider) -> dict:
        if conversation_id not in self._sessions:
            self._sessions[conversation_id] = {
                "conversation_id": conversation_id,
                "provider_id": provider.provider_id,
                "provider_session_id": None,
                "message_count": 0,
                "created_at": time.time(),
                "updated_at": time.time(),
            }
        else:
            self._sessions[conversation_id]["updated_at"] = time.time()
            self._sessions[conversation_id]["message_count"] += 1
        
        return self._sessions[conversation_id]
    
    def update_provider_session_id(self, conversation_id: str, provider_session_id: str):
        if conversation_id in self._sessions:
            self._sessions[conversation_id]["provider_session_id"] = provider_session_id
    
    def get_session(self, conversation_id: str) -> Optional[dict]:
        return self._sessions.get(conversation_id)
    
    def delete_session(self, conversation_id: str):
        self._sessions.pop(conversation_id, None)
    
    def list_sessions(self) -> list[dict]:
        return list(self._sessions.values())


mcp_translator = MCPTranslator()
mcp_normalizer = MCPNormalizer()
mcp_session_manager = MCPSessionManager()
