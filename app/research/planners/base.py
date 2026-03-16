from abc import ABC, abstractmethod


class ResearchPlanner(ABC):
    @abstractmethod
    def build_queries(self, query: str) -> list[str]:
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError
