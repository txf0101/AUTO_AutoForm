"""这个文件定义多 Agent 系统中各方都要遵守的数据结构。可以把它看成协议表：任务是什么、上下文是什么、证据怎么写、一次计划应该返回哪些字段。

This file defines the shared data structures used by the multi-agent system. Treat it as the protocol sheet that describes tasks, context, evidence, and the fields a plan must return.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentRoleSpec:
    """Describe one planned AutoForm agent role and its evidence boundary.

    `source_files` records the local files that justify the role today.  This
    keeps the role registry grounded in repository evidence instead of an
    unconstrained roadmap note.
    """

    role_id: str
    display_name: str
    responsibility: str
    source_files: tuple[str, ...]
    default_tools: tuple[str, ...] = ()
    handoff_targets: tuple[str, ...] = ()
    enabled: bool = True

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON ready role description for CLI, HTTP, MCP, and tests."""

        return {
            "role_id": self.role_id,
            "display_name": self.display_name,
            "responsibility": self.responsibility,
            "source_files": list(self.source_files),
            "default_tools": list(self.default_tools),
            "handoff_targets": list(self.handoff_targets),
            "enabled": self.enabled,
        }


@dataclass(frozen=True)
class AgentSystemRequest:
    """Input contract for a future multi agent turn.

    The request keeps the raw prompt, optional requested roles, and caller
    context separate.  That separation allows a future HTTP route, CLI command,
    MCP tool, or scheduled job to pass the same shape into the orchestrator.
    """

    prompt: str
    requested_roles: tuple[str, ...] = ()
    context: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Return request data without assuming a specific runtime backend."""

        return {
            "prompt": self.prompt,
            "requested_roles": list(self.requested_roles),
            "context": self.context,
        }


@dataclass(frozen=True)
class AgentSystemPlan:
    """Serializable routing plan returned by the reserved orchestrator."""

    request: AgentSystemRequest
    selected_roles: tuple[AgentRoleSpec, ...]
    missing_roles: tuple[str, ...]
    execution_mode: str
    notes: tuple[str, ...]
    integration_points: dict[str, str]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON ready plan that can be inspected in tests and docs."""

        return {
            "request": self.request.as_dict(),
            "selected_roles": [role.as_dict() for role in self.selected_roles],
            "missing_roles": list(self.missing_roles),
            "execution_mode": self.execution_mode,
            "notes": list(self.notes),
            "integration_points": self.integration_points,
        }
