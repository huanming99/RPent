"""RoboTwin prompt bundle assembly."""

from __future__ import annotations

from robots.robotwin.prompts import system as system_parts
from robots.robotwin.prompts import user as user_parts


def system_prompt():
    return {
        "ROLE": system_parts.ROLE,
        "READ ORDER": system_parts.READ_ORDER,
        "CLEAN-TO-RANDOMIZED TRANSFER": system_parts.TRANSFER,
        "ACCURACY-FIRST LOOP": system_parts.ACCURACY_LOOP,
        "CONDITIONAL TASK-FAMILY PLAYBOOKS": system_parts.TASK_FAMILIES,
        "VLA AND PRIMITIVE CONTROL": system_parts.CONTROL,
        "PERCEPTION": system_parts.PERCEPTION,
        "RUNTIME": system_parts.RUNTIME,
        "BUDGET AND SUCCESS": system_parts.BUDGET_AND_SUCCESS,
        "MODE": system_parts.USER_MODE,
    }


def user_prompt():
    return {
        "CELL": user_parts.CELL,
        "BEGIN": user_parts.BEGIN,
    }


__all__ = ["system_prompt", "user_prompt"]
