"""Fiyat kaynakları ve kaynaklar arası yedekleme (fallback) zinciri."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from ceyrek_tracker.cards.finance.models import Snapshot
from ceyrek_tracker.cards.finance.providers.altinkaynak import AltinkaynakProvider
from ceyrek_tracker.cards.finance.providers.base import PriceProvider
from ceyrek_tracker.cards.finance.providers.truncgil import TruncgilProvider
from ceyrek_tracker.infra.http import ProviderError

logger = logging.getLogger(__name__)

# Menüde görünen sıra; ilk eleman varsayılan kaynaktır.
PROVIDER_CHOICES: tuple[tuple[str, str], ...] = (
    (TruncgilProvider.id, TruncgilProvider.name),
    (AltinkaynakProvider.id, AltinkaynakProvider.name),
)
DEFAULT_PROVIDER = PROVIDER_CHOICES[0][0]


class AllProvidersFailed(ProviderError):
    def __init__(self, errors: Sequence[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = tuple(errors)


class FallbackFetcher:
    """Kaynakları sırayla dener; ilk başarılı sonucu döndürür."""

    def __init__(self, providers: Sequence[PriceProvider]) -> None:
        if not providers:
            raise ValueError("en az bir kaynak gerekli")
        self.providers = tuple(providers)

    def fetch(self) -> Snapshot:
        errors: list[str] = []
        for provider in self.providers:
            try:
                return provider.fetch()
            except ProviderError as exc:
                logger.warning("%s başarısız: %s", provider.name, exc)
                errors.append(f"{provider.name}: {exc}")
            except Exception as exc:  # Bir kaynaktaki beklenmedik hata zinciri kırmasın
                logger.exception("%s beklenmedik hata", provider.name)
                errors.append(f"{provider.name}: {exc.__class__.__name__}")
        raise AllProvidersFailed(errors)


def create_providers() -> dict[str, PriceProvider]:
    return {TruncgilProvider.id: TruncgilProvider(), AltinkaynakProvider.id: AltinkaynakProvider()}


def build_fetcher(providers: dict[str, PriceProvider], primary_id: str) -> FallbackFetcher:
    """Seçili kaynağı başa alıp diğerlerini yedek olarak sıralar."""
    primary = providers.get(primary_id) or providers[DEFAULT_PROVIDER]
    rest = [p for p in providers.values() if p is not primary]
    return FallbackFetcher([primary, *rest])


__all__ = [
    "DEFAULT_PROVIDER",
    "PROVIDER_CHOICES",
    "AllProvidersFailed",
    "FallbackFetcher",
    "PriceProvider",
    "ProviderError",
    "build_fetcher",
    "create_providers",
]
