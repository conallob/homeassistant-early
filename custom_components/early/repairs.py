"""Repair flows for the EARLY (Timeular) integration.

Currently handles one issue: an activity that was deleted in EARLY after
its switch was created (see switch.py's _async_sync_activity_switches).
Reloading the config entry is the fix - it rebuilds the switch platform
from the current activities list, dropping the stale switch.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import ISSUE_REMOVED_ACTIVITIES


class RemovedActivitiesRepairFlow(RepairsFlow):
    """Reload the config entry to remove switches for deleted EARLY activities."""

    def __init__(self, entry_id: str, removed_activity_names: str) -> None:
        """Initialize the flow."""
        super().__init__()
        self._entry_id = entry_id
        self._removed_activity_names = removed_activity_names

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the first step of the fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Reload the entry once the user confirms."""
        if user_input is not None:
            await self.hass.config_entries.async_reload(self._entry_id)
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"activities": self._removed_activity_names},
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    """Create the fix flow for a given issue."""
    if data and issue_id.endswith(f"_{ISSUE_REMOVED_ACTIVITIES}"):
        entry_id = data.get("entry_id")
        if entry_id and hass.config_entries.async_get_entry(entry_id):
            return RemovedActivitiesRepairFlow(
                entry_id, str(data.get("removed_activity_names", ""))
            )

    return ConfirmRepairFlow()
