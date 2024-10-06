"""Collection of context variables."""

from __future__ import annotations

from contextvars import ContextVar

# context var for storing if call is running within a service
IN_SERVICE_VAR: ContextVar[bool] = ContextVar("in_service_var", default=False)
