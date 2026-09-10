"""Browser/runtime observability primitives for Web-chat providers.

The module stores only non-secret model/runtime provenance. It must never carry
cookies, bearer tokens, signatures, CAPTCHA proof, prompt content, or raw
provider storage.
"""
from dataclasses import dataclass, field
import re
from typing import Iterable, Optional


def normalize_model_marker(value: Optional[str]) -> str:
    """Normalize display/id variants for conservative equality checks."""
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


class BrowserEvidenceMismatch(RuntimeError):
    def __init__(self, message: str, details: dict):
        super().__init__(message)
        self.details = details


@dataclass
class BrowserModelEvidence:
    provider: str
    requested_model: Optional[str]
    expected_upstream_model: Optional[str]
    frontend_version: Optional[str] = None
    ui_selected_model: Optional[str] = None
    frontend_state_models: list[str] = field(default_factory=list)
    backend_request_model: Optional[str] = None
    response_model: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            "provider": self.provider,
            "requested_model": self.requested_model,
            "expected_upstream_model": self.expected_upstream_model,
            "frontend_version": self.frontend_version,
            "ui_selected_model": self.ui_selected_model,
            "frontend_state_models": list(self.frontend_state_models),
            "backend_request_model": self.backend_request_model,
            "response_model": self.response_model,
        }

    def validate(self, *, require_selection: bool = True, require_backend: bool = True) -> dict:
        """Fail closed when model-selection provenance contradicts expectation."""
        expected = normalize_model_marker(self.expected_upstream_model)
        if not expected:
            raise BrowserEvidenceMismatch(
                "Expected upstream model is missing",
                self.as_dict(),
            )

        selected = []
        if self.ui_selected_model:
            selected.append(self.ui_selected_model)
        selected.extend(x for x in self.frontend_state_models if x)

        if require_selection:
            if not selected:
                raise BrowserEvidenceMismatch(
                    "No UI/frontend model-selection evidence was observed",
                    self.as_dict(),
                )
            if not any(normalize_model_marker(x) == expected for x in selected):
                raise BrowserEvidenceMismatch(
                    "UI/frontend selected model does not match expected upstream model",
                    self.as_dict(),
                )

        backend = normalize_model_marker(self.backend_request_model)
        if require_backend:
            if not backend:
                raise BrowserEvidenceMismatch(
                    "No backend request model was observed",
                    self.as_dict(),
                )
            if backend != expected:
                raise BrowserEvidenceMismatch(
                    "Backend request model does not match expected upstream model",
                    self.as_dict(),
                )

        response = normalize_model_marker(self.response_model)
        if response and response != expected:
            raise BrowserEvidenceMismatch(
                "Response model does not match expected upstream model",
                self.as_dict(),
            )

        return {
            **self.as_dict(),
            "verified": True,
            "selection_verified": bool(selected),
            "backend_verified": bool(backend),
            "response_verified": bool(response),
        }
