from typing import Optional
from core.providers import Provider, ProviderConfig, ProviderType, ProviderCapabilities
from core.mcp import mcp_session_manager
import logging

logger = logging.getLogger(__name__)


class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, Provider] = {}
        self._configs: dict[str, ProviderConfig] = {}
        self._default_provider_id: Optional[str] = None
    
    def register(self, provider: Provider) -> None:
        self._providers[provider.provider_id] = provider
        self._configs[provider.provider_id] = provider.config
        
        if self._default_provider_id is None and provider.config.enabled:
            self._default_provider_id = provider.provider_id
        
        logger.info(f"Registered provider: {provider.provider_id} ({provider.provider_type.value})")
    
    def unregister(self, provider_id: str) -> bool:
        if provider_id in self._providers:
            provider = self._providers.pop(provider_id)
            self._configs.pop(provider_id, None)
            
            if self._default_provider_id == provider_id:
                enabled = [p for p in self._providers.values() if p.config.enabled]
                self._default_provider_id = enabled[0].provider_id if enabled else None
            
            logger.info(f"Unregistered provider: {provider_id}")
            return True
        return False
    
    def get(self, provider_id: str) -> Optional[Provider]:
        return self._providers.get(provider_id)
    
    def get_default(self) -> Optional[Provider]:
        if self._default_provider_id:
            return self._providers.get(self._default_provider_id)
        return None
    
    def list_providers(self, enabled_only: bool = True) -> list[Provider]:
        providers = list(self._providers.values())
        if enabled_only:
            providers = [p for p in providers if p.config.enabled]
        return sorted(providers, key=lambda p: p.config.priority)
    
    def list_provider_ids(self, enabled_only: bool = True) -> list[str]:
        return [p.provider_id for p in self.list_providers(enabled_only)]
    
    def set_default(self, provider_id: str) -> bool:
        if provider_id in self._providers and self._providers[provider_id].config.enabled:
            self._default_provider_id = provider_id
            return True
        return False
    
    async def health_check_all(self) -> dict[str, bool]:
        results = {}
        for provider_id, provider in self._providers.items():
            if provider.config.enabled:
                try:
                    results[provider_id] = await provider.health_check()
                except Exception as e:
                    logger.error(f"Health check failed for {provider_id}: {e}")
                    results[provider_id] = False
            else:
                results[provider_id] = False
        return results
    
    async def close_all(self) -> None:
        for provider in self._providers.values():
            try:
                await provider.close()
            except Exception as e:
                logger.error(f"Error closing provider {provider.provider_id}: {e}")
        self._providers.clear()
        self._configs.clear()
        self._default_provider_id = None


class ProviderRouter:
    def __init__(self, registry: ProviderRegistry):
        self._registry = registry
    
    def select_provider(
        self,
        model: Optional[str] = None,
        provider_id: Optional[str] = None,
        provider_type: Optional[ProviderType] = None,
        require_streaming: bool = False,
        require_tools: bool = False,
    ) -> Optional[Provider]:
        if provider_id:
            provider = self._registry.get(provider_id)
            if provider and provider.config.enabled:
                return provider
            return None
        
        candidates = self._registry.list_providers(enabled_only=True)
        
        if provider_type:
            candidates = [p for p in candidates if p.provider_type == provider_type]
        
        if require_streaming:
            candidates = [p for p in candidates if p.capabilities.streaming]
        
        if require_tools:
            candidates = [p for p in candidates if p.capabilities.tools]
        
        if model:
            # Exact, fail-closed model resolution. An empty model list means the
            # provider has declared no routable model ids, not "match anything".
            candidates = [
                p for p in candidates
                if model in p.capabilities.supported_models
            ]
        
        if not candidates:
            return None
        
        return candidates[0]


provider_registry = ProviderRegistry()
provider_router = ProviderRouter(provider_registry)