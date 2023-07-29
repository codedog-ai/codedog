from abc import ABC, abstractmethod

from codedog.actors.base import Actor


class Reporter(Actor, ABC):
    @abstractmethod
    def report(self) -> str:
        """Generate report content text."""
