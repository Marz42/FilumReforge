"""Public domain-neutral template instantiation service.

The implementation remains in the legacy module during the compatibility
window so existing imports and API dependencies do not break.
"""

from app.services.workflow_video_instantiation_service import (
  GraphTemplateRunResult,
  WorkflowTemplateInstantiationService,
)

__all__ = ["GraphTemplateRunResult", "WorkflowTemplateInstantiationService"]

