from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

FUSO_BRASIL = ZoneInfo("America/Sao_Paulo")


def agora_brasil() -> datetime:
    """Horário oficial usado pelo app, independente do fuso do servidor."""
    return datetime.now(FUSO_BRASIL)


def agora_brasil_sem_fuso() -> datetime:
    """Horário local sem tzinfo, compatível com exportação para Excel."""
    return agora_brasil().replace(tzinfo=None)
