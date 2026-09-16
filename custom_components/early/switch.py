"""Platform for EARLY (Timeular) switch integration."""

from __future__ import annotations

import logging
from typing import Any, Callable

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ISSUE_REMOVED_ACTIVITIES
from .util import get_current_activity_id, is_bluetooth_entry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EARLY switches from a config entry."""
    # Switches require an API coordinator to start/stop tracking. This is
    # available for plain API config entries, and for Bluetooth entries that
    # were also configured with optional API credentials. The coordinator is
    # created by the sensor platform, which is forwarded before this one.
    if DOMAIN not in hass.data or config_entry.entry_id not in hass.data[DOMAIN]:
        _LOGGER.error("Coordinator not found for entry %s", config_entry.entry_id)
        return

    coordinator = hass.data[DOMAIN][config_entry.entry_id].get("coordinator")
    if not coordinator:
        # No coordinator was created for this entry - either no API
        # credentials were configured (e.g. a Bluetooth-only tracker), or
        # credentials were configured but the initial activity fetch failed
        # (see bluetooth_sensor.py). Either way, there is nothing to create
        # activity switches for.
        _LOGGER.debug(
            "No API coordinator for entry %s; skipping activity switches",
            config_entry.entry_id,
        )
        return

    # Fetch activities to create switches
    await coordinator.async_update()
    activities = coordinator.get_all_activities()

    if not activities:
        # No activities yet (fresh EARLY account, or a transient empty
        # response from the initial fetch) - still fall through to
        # register _async_sync_activity_switches below instead of
        # returning early. Bailing out here entirely would mean any
        # activity created afterward never gets a switch, since this
        # function is the only place that listener gets attached -
        # exactly the "no switch until a reload" gap this platform exists
        # to close.
        _LOGGER.warning(
            "No activities found for entry %s; switches will be added "
            "automatically once EARLY reports one",
            config_entry.entry_id,
        )

    # Bluetooth entries are a new source of activity switches (previously
    # they were skipped entirely). Scope their unique_id by config entry so
    # they can't collide with a Cloud API entry for the same account - the
    # README documents running both simultaneously. Plain API entries keep
    # their original unique_id format for backwards compatibility with
    # existing entity registries.
    entry_id_for_unique_id = (
        config_entry.entry_id if is_bluetooth_entry(config_entry) else None
    )

    # Tracks every activity a switch has been created for so far, by id ->
    # name. Kept separately from coordinator.get_all_activities() because
    # that dict is overwritten wholesale on every activities refresh (see
    # sensor.py's _fetch_activities) - once an activity is deleted in EARLY
    # it disappears from there, but this integration still needs its name
    # to show in the repair issue raised below.
    tracked_activities = dict(activities)

    def _build_switch(activity_id: str, activity_name: str) -> EarlyActivitySwitch:
        return EarlyActivitySwitch(
            coordinator, activity_id, activity_name, entry_id_for_unique_id
        )

    if tracked_activities:
        async_add_entities(
            [_build_switch(aid, name) for aid, name in tracked_activities.items()],
            True,
        )

    @callback
    def _async_sync_activity_switches() -> None:
        """Reconcile switches with the coordinator's current activities list.

        Switches are otherwise only ever created once, at platform setup -
        an activity added or deleted in EARLY afterward would go unnoticed
        until a full integration reload. Registered as a coordinator
        listener (the same pub/sub used for webhook push-updates - see
        sensor.py's EarlyAPICoordinator.add_listener), so this re-checks on
        every refresh, not just at startup.

        This function itself runs on every coordinator notify - every ~30s
        tracking poll (DEFAULT_SCAN_INTERVAL) or webhook-triggered refresh -
        but coordinator.get_all_activities() only actually changes at most
        once an hour (sensor.py's ACTIVITIES_REFRESH_INTERVAL), so most of
        those runs are a no-op diff. New activities get a switch added on
        the first run after they show up there, no reload needed - but "no
        reload needed" means "within about an hour", not "instantly".
        Removed activities are more disruptive to handle live (cleanly
        removing an entity means touching the entity registry, not just
        this platform), so those are surfaced as a fixable repair issue
        that reloads the entry instead - see repairs.py.

        Known gap: this only diffs by activity id, so an activity renamed
        in EARLY without changing id is neither re-added nor flagged - its
        switch's name stays stale until an unrelated reload. The same
        applies if the coordinator's spaces fetch (see sensor.py's
        _fetch_spaces) fails transiently on the very first fetch at
        startup: switches get created with their bare, unprefixed name,
        and stay that way even once a later refresh successfully
        resolves the "Space: Activity" prefix - only sensor.py's
        current-activity sensor re-resolves the name on every read and
        so isn't affected.
        """
        current_activities = coordinator.get_all_activities()
        current_ids = set(current_activities)
        known_ids = set(tracked_activities)

        new_ids = current_ids - known_ids
        if new_ids:
            new_switches = [
                _build_switch(activity_id, current_activities[activity_id])
                for activity_id in new_ids
            ]
            tracked_activities.update(
                (activity_id, current_activities[activity_id])
                for activity_id in new_ids
            )
            async_add_entities(new_switches, True)
            _LOGGER.debug(
                "Added %d new EARLY activity switch(es) for entry %s: %s",
                len(new_switches),
                config_entry.entry_id,
                sorted(new_ids),
            )

        # removed_ids stays derived from tracked_activities (never pruned
        # outside of a reload - see its docstring above), so as long as the
        # issue is unresolved this re-fires async_create_issue with the same
        # arguments on every subsequent refresh, not just once. That's
        # intentional and harmless (it's an upsert keyed by issue_id, and
        # async_delete_issue below is a no-op lookup miss when nothing was
        # ever created) - simpler than tracking "is this issue currently
        # open" separately just to skip a cheap, idempotent call.
        removed_ids = known_ids - current_ids
        issue_id = f"{config_entry.entry_id}_{ISSUE_REMOVED_ACTIVITIES}"
        if removed_ids:
            removed_names = sorted(tracked_activities[aid] for aid in removed_ids)
            # No translation_placeholders here: the issue's own
            # translation (title only, no top-level description - see
            # test_removed_activities_issue_has_no_top_level_description)
            # doesn't reference {activities}, so there'd be nothing to
            # consume it. The names only ever get shown via the fix flow's
            # own description_placeholders, built from data below.
            ir.async_create_issue(
                hass,
                DOMAIN,
                issue_id,
                is_fixable=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_REMOVED_ACTIVITIES,
                data={
                    "entry_id": config_entry.entry_id,
                    "removed_activity_names": ", ".join(removed_names),
                },
            )
        else:
            ir.async_delete_issue(hass, DOMAIN, issue_id)

    remove_listener = coordinator.add_listener(_async_sync_activity_switches)
    config_entry.async_on_unload(remove_listener)


class EarlyActivitySwitch(SwitchEntity):
    """Representation of an EARLY activity switch."""

    def __init__(
        self,
        coordinator: Any,
        activity_id: str,
        activity_name: str,
        config_entry_id: str | None = None,
    ) -> None:
        """Initialize the switch."""
        self._coordinator = coordinator
        self._activity_id = activity_id
        self._activity_name = activity_name
        self._attr_name = f"EARLY {activity_name}"
        self._attr_unique_id = (
            f"{DOMAIN}_{config_entry_id}_activity_{activity_id}"
            if config_entry_id
            else f"{DOMAIN}_activity_{activity_id}"
        )
        self._attr_icon = "mdi:timer"
        self._remove_listener: Callable[[], None] | None = None

    async def async_added_to_hass(self) -> None:
        """Register for immediate updates when the coordinator refreshes.

        This is what makes a webhook-triggered refresh (see webhook.py)
        show up right away instead of waiting for this entity's own next
        poll cycle.
        """
        self._remove_listener = self._coordinator.add_listener(
            self.async_write_ha_state
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister from the coordinator."""
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None

    @property
    def is_on(self) -> bool:
        """Return true if the activity is currently being tracked."""
        if not self._coordinator.tracking_data:
            return False

        current_tracking = self._coordinator.tracking_data.get("currentTracking")
        if not current_tracking:
            return False

        current_activity_id = get_current_activity_id(current_tracking)

        return current_activity_id == self._activity_id

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start tracking this activity."""
        try:
            await self._coordinator.start_tracking(self._activity_id)
            await self.async_update()
        except Exception as err:
            _LOGGER.error(
                "Error starting tracking for activity %s: %s",
                self._activity_name,
                err,
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop tracking this activity."""
        # Only stop if this activity is currently being tracked
        if self.is_on:
            try:
                await self._coordinator.stop_tracking()
                await self.async_update()
            except Exception as err:
                _LOGGER.error(
                    "Error stopping tracking for activity %s: %s",
                    self._activity_name,
                    err,
                )

    async def async_update(self) -> None:
        """Update the switch state."""
        await self._coordinator.async_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._coordinator.tracking_data is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            "activity_id": self._activity_id,
            "activity_name": self._activity_name,
        }
