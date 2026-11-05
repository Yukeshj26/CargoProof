from .adapters import (
    StraleProvider,
    AisfleetProvider,
    ContainerIntelligenceProvider,
    GlobalPortTelemetryProvider,
    SynthoraProvider,
    SandboxX402Provider
)
from ..config import settings

PROVIDERS = {
    p.name: p for p in (
        ContainerIntelligenceProvider(),
        AisfleetProvider(),
        StraleProvider(),
        GlobalPortTelemetryProvider(),
        SynthoraProvider(),
        SandboxX402Provider()
    )
}

def provider_status():
    rows = []
    for name, provider in PROVIDERS.items():
        configured = provider.enabled
        active = configured and not settings.demo_mode
        mode = (
            'DEMO_MODE_BLOCKED' if configured and settings.demo_mode
            else ('SANDBOX_X402' if name == 'cargoproof_test_provider' and active
            else ('LIVE_CONFIGURED' if active
            else 'NOT_CONFIGURED'))
        )
        rows.append({
            'name': name,
            'capabilities': provider.capabilities,
            'enabled': active,
            'configured': configured,
            'mode': mode,
            'source_type': provider.source_type
        })
    return rows
