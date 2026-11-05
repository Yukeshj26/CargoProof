from abc import ABC, abstractmethod
from datetime import datetime, timezone
class BaseProvider(ABC):
    name='base'; capabilities=[]; source_type='LIVE_OBSERVATION'
    def __init__(self, enabled=False):self.enabled=enabled
    @abstractmethod
    async def fetch(self, resource_id:str, **kwargs):...
    def unavailable(self, reason, status='UNAVAILABLE'):
        return {'provider':self.name,'status':status,'source_type':None,'observed_at':None,'retrieved_at':datetime.now(timezone.utc).isoformat(),'evidence':None,'error':reason}
