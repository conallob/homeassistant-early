"""Test the EARLY repairs module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.early.repairs import (
    RemovedActivitiesRepairFlow,
    async_create_fix_flow,
)


class TestAsyncCreateFixFlow:
    """Test async_create_fix_flow."""

    @pytest.mark.asyncio
    async def test_returns_removed_activities_flow_for_a_known_entry(self):
        """Test the real fix flow is returned when the entry still exists."""
        hass = MagicMock()
        hass.config_entries.async_get_entry.return_value = MagicMock()

        flow = await async_create_fix_flow(
            hass,
            "test_entry_id_removed_activities",
            {"entry_id": "test_entry_id", "removed_activity_names": "Meeting"},
        )

        assert isinstance(flow, RemovedActivitiesRepairFlow)
        assert flow._entry_id == "test_entry_id"
        assert flow._removed_activity_names == "Meeting"

    @pytest.mark.asyncio
    async def test_falls_back_to_confirm_flow_when_entry_no_longer_exists(self):
        """Test a stale issue (entry removed) doesn't crash the fix flow."""
        from homeassistant.components.repairs import ConfirmRepairFlow

        hass = MagicMock()
        hass.config_entries.async_get_entry.return_value = None

        flow = await async_create_fix_flow(
            hass,
            "test_entry_id_removed_activities",
            {"entry_id": "test_entry_id", "removed_activity_names": "Meeting"},
        )

        assert isinstance(flow, ConfirmRepairFlow)

    @pytest.mark.asyncio
    async def test_falls_back_to_confirm_flow_when_no_data(self):
        """Test a missing data dict doesn't crash the fix flow."""
        from homeassistant.components.repairs import ConfirmRepairFlow

        hass = MagicMock()

        flow = await async_create_fix_flow(hass, "some_other_issue", None)

        assert isinstance(flow, ConfirmRepairFlow)


class TestRemovedActivitiesRepairFlow:
    """Test RemovedActivitiesRepairFlow."""

    @pytest.mark.asyncio
    async def test_confirm_step_shows_form_with_removed_activity_names(self):
        """Test the initial confirm step shows the removed activities."""
        flow = RemovedActivitiesRepairFlow("test_entry_id", "Meeting, Focus")
        flow.hass = MagicMock()

        result = await flow.async_step_confirm()

        assert result["type"] == "form"
        assert result["step_id"] == "confirm"
        assert result["description_placeholders"] == {"activities": "Meeting, Focus"}

    @pytest.mark.asyncio
    async def test_confirm_step_reloads_the_entry_on_submit(self):
        """Test submitting the form reloads the config entry."""
        flow = RemovedActivitiesRepairFlow("test_entry_id", "Meeting")
        flow.hass = MagicMock()
        flow.hass.config_entries.async_reload = AsyncMock()

        result = await flow.async_step_confirm(user_input={})

        flow.hass.config_entries.async_reload.assert_called_once_with("test_entry_id")
        assert result["type"] == "create_entry"

    @pytest.mark.asyncio
    async def test_init_step_delegates_to_confirm(self):
        """Test the flow's first step goes straight to confirm."""
        flow = RemovedActivitiesRepairFlow("test_entry_id", "Meeting")
        flow.hass = MagicMock()

        result = await flow.async_step_init()

        assert result["step_id"] == "confirm"
