from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Agent(ABC):
    name: str

    @abstractmethod
    def run(self, request_text: str, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
