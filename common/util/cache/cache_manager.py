# common/cache/cache_manager.py
import redis
from common.config.settings import get_settings

class CacheManager:
    def __init__(self):
        self.settings = get_settings()

        # Si el cache está deshabilitado, todo será un no-op
        self.cache_enabled = str(self.settings.cache_enabled).lower() == "true"
        self.cache_type = (self.settings.cache_type or "memory").upper()

        self._memory_cache = {}  # fallback en memoria

        self._redis_client = None
        if self.cache_enabled and self.cache_type == "REDIS":
            try:
                self._redis_client = redis.StrictRedis.from_url(
                    self.settings.redis_url,
                    decode_responses=True
                )
                # Prueba rápida de conexión
                self._redis_client.ping()
                print("[CacheManager] Redis conectado en", self.settings.redis_url)
            except Exception as e:
                print("[CacheManager] Error conectando a Redis:", e)
                print("[CacheManager] Usando fallback en memoria")
                self.cache_type = "MEMORY"

    def set(self, key: str, value: str, expiry: int | None = None):
        if not self.cache_enabled:
            return
        if self.cache_type == "REDIS" and self._redis_client:
            self._redis_client.set(key, value, ex=expiry)
        else:
            self._memory_cache[key] = value

    def get(self, key: str) -> str | None:
        if not self.cache_enabled:
            return None
        if self.cache_type == "REDIS" and self._redis_client:
            return self._redis_client.get(key)
        return self._memory_cache.get(key)

    def delete(self, key: str):
        if not self.cache_enabled:
            return
        if self.cache_type == "REDIS" and self._redis_client:
            self._redis_client.delete(key)
        else:
            self._memory_cache.pop(key, None)

    def clear(self):
        if not self.cache_enabled:
            return
        if self.cache_type == "REDIS" and self._redis_client:
            self._redis_client.flushdb()
        else:
            self._memory_cache.clear()
