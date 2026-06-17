import logging
from typing import List, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GOOGLE_API_KEY
        self.model = model or settings.EMBEDDING_MODEL
        self.enabled = bool(self.api_key)
        
        if self.enabled:
            self.client = httpx.AsyncClient(
                base_url="https://generativelanguage.googleapis.com",
                timeout=30.0,
            )
        else:
            self.client = None

    async def close(self) -> None:
        if self.client:
            await self.client.aclose()

    async def get_embedding(self, text: str) -> List[float]:
        if not text:
            return [0.0] * 768
            
        if not self.enabled:
            logger.debug("Google API key missing. Using deterministic mock embedding.")
            return self.generate_mock_embedding(text)

        try:
            url = f"/v1beta/models/{self.model}:embedContent?key={self.api_key}"
            body = {
                "content": {
                    "parts": [{"text": text}]
                }
            }
            response = await self.client.post(url, json=body)
            if response.status_code != 200:
                logger.error(f"Gemini embedding API failed with status {response.status_code}: {response.text}")
                logger.info("Falling back to deterministic mock embedding due to API error.")
                return self.generate_mock_embedding(text)
                
            data = response.json()
            return data["embedding"]["values"]
        except Exception as e:
            logger.exception("Exception during Gemini embedding request, falling back to mock.")
            return self.generate_mock_embedding(text)

    def _get_word_embedding(self, word: str, dim: int = 768) -> List[float]:
        import hashlib
        import random
        hasher = hashlib.sha256(word.lower().encode("utf-8"))
        seed = int(hasher.hexdigest(), 16) % (2**32)
        rng = random.Random(seed)
        return [rng.uniform(-1.0, 1.0) for _ in range(dim)]

    def generate_mock_embedding(self, text: str, dim: int = 768) -> List[float]:
        import re
        words = re.findall(r'\w+', text.lower())
        if not words:
            words = ["empty"]
            
        vector = [0.0] * dim
        for w in words:
            w_vec = self._get_word_embedding(w, dim)
            for i in range(dim):
                vector[i] += w_vec[i]
                
        norm = sum(x*x for x in vector) ** 0.5
        if norm > 0:
            vector = [x / norm for x in vector]
        return vector

embedding_service = EmbeddingService()
