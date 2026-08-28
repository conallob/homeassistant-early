"""Near-real-time EARLY tracking updates via webhooks.

EARLY's v3 API is polled for the current tracking status every
DEFAULT_SCAN_INTERVAL seconds (see sensor.py) - that polling loop is a
built-in latency the integration otherwise has no way around. EARLY's API
also supports webhooks: POSTing to
"{API_BASE_URL}/webhooks/subscription" with an event name and a target URL
registers a subscription that EARLY calls back on "trackingStarted" and
"trackingStopped".

This module registers a Home Assistant webhook endpoint and subscribes it
to both events for a given config entry's coordinator, so switches/sensor
update immediately instead of waiting for the next poll. It is strictly an
optimization layered on top of polling, never a replacement:

- Subscribing requires Home Assistant to have a publicly reachable URL
  EARLY's servers can reach (see homeassistant.helpers.network.get_url).
  Most local-only installs don't have one; this is expected and not an
  error, so it's logged at info level and setup simply continues without a
  webhook - polling keeps working exactly as before.
- Any failure subscribing/unsubscribing with the EARLY API, or handling an
  incoming webhook call, is caught and logged rather than raised, so it
  can never break entry setup/unload or crash the poll-based coordinator
  this integration has always relied on.

The webhook_id/subscription ids are also mirrored into config_entry.data
(under WEBHOOK_STATE_KEY) so a non-graceful restart (crash, container
restart, systemctl restart - anything that skips async_unload_entry) can
still be recognized and cleaned up on the next setup, instead of silently
leaking an orphaned subscription (and local webhook_id) in EARLY's account
every time that happens.
"""

from __future__ import annotations

import logging

from aiohttp import web
from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import (
    DOMAIN,
    WEBHOOK_EVENT_TRACKING_STARTED,
    WEBHOOK_EVENT_TRACKING_STOPPED,
)
from .sensor import EarlyAPICoordinator

_LOGGER = logging.getLogger(__name__)

WEBHOOK_EVENTS = (WEBHOOK_EVENT_TRACKING_STARTED, WEBHOOK_EVENT_TRACKING_STOPPED)

# Config-entry data key this module uses to remember a webhook it created,
# purely so a subsequent setup (e.g. after a non-graceful restart) can find
# and clean up a subscription async_unload_webhook never got the chance to.
WEBHOOK_STATE_KEY = "_early_webhook_state"


async def _async_forget_previous_subscription(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: EarlyAPICoordinator
) -> None:
    """Unsubscribe and clear any webhook state left over from a prior run."""
    previous_state = entry.data.get(WEBHOOK_STATE_KEY)
    if not previous_state:
        return

    for subscription_id in previous_state.get("subscription_ids", {}).values():
        await coordinator.async_unsubscribe_webhook(subscription_id)

    hass.config_entries.async_update_entry(
        entry,
        data={k: v for k, v in entry.data.items() if k != WEBHOOK_STATE_KEY},
    )


async def async_setup_webhook(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: EarlyAPICoordinator
) -> None:
    """Register a webhook endpoint and subscribe it to EARLY tracking events."""
    try:
        # Only used to confirm Home Assistant has a public URL at all; the
        # actual callback URL below is built from the webhook_id via
        # webhook.async_generate_url, which already resolves the same
        # external base URL.
        get_url(hass, allow_internal=False, allow_ip=False)
    except NoURLAvailableError:
        _LOGGER.info(
            "No externally reachable URL configured for Home Assistant; "
            "EARLY activity updates will rely on polling only (webhooks "
            "require a public URL EARLY's servers can reach)"
        )
        return

    # Clean up a subscription from a previous run before creating a new
    # one, so a non-graceful restart (or a setup retry) doesn't accumulate
    # orphaned subscriptions in the user's EARLY account.
    await _async_forget_previous_subscription(hass, entry, coordinator)

    webhook_id = webhook.async_generate_id()
    webhook_url = webhook.async_generate_url(hass, webhook_id)

    async def _handle_webhook(
        hass: HomeAssistant, received_webhook_id: str, request: web.Request
    ) -> web.Response:
        """Handle an incoming EARLY tracking webhook call.

        The payload isn't parsed for tracking state - EARLY's tracking
        endpoint (already polled by the coordinator) is the single source
        of truth the rest of this integration trusts, so a webhook call of
        either event just triggers an immediate, unthrottled refresh from
        that endpoint instead of duplicating state-parsing logic here. Both
        the body parse and the refresh are guarded so nothing here can ever
        raise out of the aiohttp view.
        """
        try:
            await request.json()
        except ValueError:
            _LOGGER.debug("Received EARLY webhook call with a non-JSON body")

        _LOGGER.debug("Received EARLY webhook call; refreshing tracking status")
        try:
            await coordinator.async_update(no_throttle=True)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Error refreshing EARLY tracking data from webhook")

        return web.Response(status=200)

    webhook.async_register(
        hass,
        DOMAIN,
        "EARLY tracking",
        webhook_id,
        _handle_webhook,
        allowed_methods=["POST"],
    )

    entry_data = hass.data[DOMAIN][entry.entry_id]
    entry_data["webhook_id"] = webhook_id

    subscription_ids = {}
    for event in WEBHOOK_EVENTS:
        subscription_id = await coordinator.async_subscribe_webhook(event, webhook_url)
        if subscription_id:
            subscription_ids[event] = subscription_id

    if not subscription_ids:
        # EARLY never accepted a subscription (no webhook support on this
        # plan, unreachable target URL, auth failure, etc.) - keep the
        # entry on polling only and don't leave a dead local endpoint
        # registered.
        webhook.async_unregister(hass, webhook_id)
        entry_data.pop("webhook_id", None)
        return

    entry_data["webhook_subscription_ids"] = subscription_ids
    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            WEBHOOK_STATE_KEY: {
                "webhook_id": webhook_id,
                "subscription_ids": subscription_ids,
            },
        },
    )
    _LOGGER.debug(
        "EARLY webhook registered for entry %s (%d/%d events subscribed)",
        entry.entry_id,
        len(subscription_ids),
        len(WEBHOOK_EVENTS),
    )


async def async_unload_webhook(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: EarlyAPICoordinator
) -> None:
    """Unregister the local webhook endpoint and unsubscribe from EARLY."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    webhook_id = entry_data.pop("webhook_id", None)
    subscription_ids = entry_data.pop("webhook_subscription_ids", {})

    for subscription_id in subscription_ids.values():
        await coordinator.async_unsubscribe_webhook(subscription_id)

    if webhook_id:
        webhook.async_unregister(hass, webhook_id)

    if WEBHOOK_STATE_KEY in entry.data:
        hass.config_entries.async_update_entry(
            entry,
            data={k: v for k, v in entry.data.items() if k != WEBHOOK_STATE_KEY},
        )
