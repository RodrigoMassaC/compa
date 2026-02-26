"""
Spider base abstracto para todos los scrapers de Compa.
Regla de arquitectura #12: Todos los spiders heredan de BaseSpider
y retornan List[ScrapedProduct].
"""
import asyncio
import logging
import random
from abc import ABC, abstractmethod
from typing import List

from app.schemas.scraper_schema import ScrapedProduct

logger = logging.getLogger(__name__)

# Pool de 5 User-Agents reales y modernos para rotación
USER_AGENTS: List[str] = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) "
        "Gecko/20100101 Firefox/123.0"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.3.1 Safari/605.1.15"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
]


class BaseSpider(ABC):
    """
    Spider base para todos los scrapers de Compa.
    Define la interfaz y los helpers comunes (delay, user-agent, logger).
    """

    # Rango de delay en segundos entre requests (regla de arquitectura #13)
    DELAY_MIN: float = 2.0
    DELAY_MAX: float = 4.0

    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self._current_ua_index: int = 0

    @abstractmethod
    async def run(self) -> List[ScrapedProduct]:
        """
        Método principal que ejecuta el spider.
        Debe retornar todos los productos extraídos.
        """
        ...

    async def _random_delay(self) -> None:
        """
        Pausa aleatoria entre DELAY_MIN y DELAY_MAX segundos.
        Obligatoria entre requests para no sobrecargar el servidor.
        """
        delay = random.uniform(self.DELAY_MIN, self.DELAY_MAX)
        self.logger.debug(f"Esperando {delay:.2f}s...")
        await asyncio.sleep(delay)

    def _get_headers(self) -> dict:
        """
        Retorna headers HTTP con User-Agent rotativo.
        Rota en round-robin entre los 5 UAs del pool.
        """
        ua = USER_AGENTS[self._current_ua_index % len(USER_AGENTS)]
        self._current_ua_index += 1
        return {
            "User-Agent": ua,
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "es-VE,es;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

    def _get_random_ua(self) -> str:
        """Retorna un User-Agent aleatorio del pool."""
        return random.choice(USER_AGENTS)
