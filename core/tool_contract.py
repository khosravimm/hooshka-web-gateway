from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class ToolRiskClass(str, Enum):
    READ_ONLY = "READ_ONLY"
    CONTROLLED_WRITE = "CONTROLLED_WRITE"
    EXECUTION = "EXECUTION"
    EXTERNAL_ACTION = "EXTERNAL_ACTION"
    PRIVILEGED = "PRIVILEGED"


class ToolAuthorizationMode(str, Enum):
    NONE = "none"
    POLICY = "policy"
    APPROVAL = "approval"


@dataclass(frozen=True)
class ToolAnnotations:
    read_only_hint: bool
    destructive_hint: bool
    idempotent_hint: bool
    open_world_hint: bool

@dataclass(frozen=True)
class ToolDescriptor:
    name: str
    description: str
    source: str
    risk_class: ToolRiskClass
    authorization_mode: ToolAuthorizationMode
    input_schema: dict[str, Any]
    annotations: ToolAnnotations
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["risk_class"] = self.risk_class.value
        data["authorization_mode"] = self.authorization_mode.value
        # Backward-compatible field retained for existing HWG clients/tests.
        data["risk"] = self.risk_class.value.lower()
        data["annotations"] = {
            "readOnlyHint": self.annotations.read_only_hint,
            "destructiveHint": self.annotations.destructive_hint,
            "idempotentHint": self.annotations.idempotent_hint,
            "openWorldHint": self.annotations.open_world_hint,
        }
        return data


def read_only_descriptor(name: str, description: str, input_schema: dict[str, Any], source: str = "hwg_native") -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        description=description,
        source=source,
        risk_class=ToolRiskClass.READ_ONLY,
        authorization_mode=ToolAuthorizationMode.NONE,
        input_schema=input_schema,
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )
