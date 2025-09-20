from abc import ABC, abstractmethod
from typing import List, Dict, Any
from pydantic import BaseModel

class IPreviewableTask(ABC):
    @abstractmethod
    async def get_targets(self, params: BaseModel) -> List[Dict[str, Any]]:
        ...

class IExecutableTask(ABC):
    @abstractmethod
    async def execute(self, params: BaseModel) -> str:
        ...