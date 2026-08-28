"""Test the EARLY integration setup."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform

from custom_components.early import async_setup_entry, async_unload_entry
from custom_components.early.bluetooth import EarlyBluetoothDevice
from custom_components.early.const import DOMAIN


class TestIntegrationSetup:
    """Test the EARLY integration setup."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_api(self, mock_hass, mock_config_entry):
        """Test setting up API config entry."""
        mock_hass.config_entries.async_forward_entry_setups = AsyncMock(
            return_value=True
        )

        result = await async_setup_entry(mock_hass, mock_config_entry)

        assert result is True
        assert DOMAIN in mock_hass.data
        assert mock_config_entry.entry_id in mock_hass.data[DOMAIN]
        assert "config" in mock_hass.data[DOMAIN][mock_config_entry.entry_id]
        assert "bluetooth_devices" in mock_hass.data[DOMAIN][mock_config_entry.entry_id]

        assert mock_hass.config_entries.async_forward_entry_setups.call_args_list == [
            call(mock_config_entry, [Platform.SENSOR]),
            call(mock_config_entry, [Platform.SWITCH]),
        ]

    @pytest.mark.asyncio
    async def test_async_setup_entry_bluetooth(
        self, mock_hass, mock_bluetooth_config_entry
    ):
        """Test setting up Bluetooth config entry."""
        mock_hass.config_entries.async_forward_entry_setups = AsyncMock(
            return_value=True
        )

        with patch(
            "homeassistant.components.bluetooth.async_register_callback"
        ) as mock_register:
            mock_register.return_value = MagicMock()

            result = await async_setup_entry(mock_hass, mock_bluetooth_config_entry)

            assert result is True
            assert DOMAIN in mock_hass.data
            assert mock_bluetooth_config_entry.entry_id in mock_hass.data[DOMAIN]

            assert (
                mock_hass.config_entries.async_forward_entry_setups.call_args_list
                == [
                    call(mock_bluetooth_config_entry, [Platform.SENSOR]),
                    call(mock_bluetooth_config_entry, [Platform.SWITCH]),
                ]
            )
            mock_register.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_setup_entry_sets_up_webhook_when_coordinator_present(
        self, mock_hass, mock_config_entry
    ):
        """Test webhook setup is attempted when SENSOR created a coordinator."""

        async def _fake_forward(entry, platforms):
            if platforms == [Platform.SENSOR]:
                mock_hass.data[DOMAIN][entry.entry_id]["coordinator"] = MagicMock()
            return True

        mock_hass.config_entries.async_forward_entry_setups = AsyncMock(
            side_effect=_fake_forward
        )

        with patch(
            "custom_components.early.async_setup_webhook", new_callable=AsyncMock
        ) as mock_setup_webhook:
            result = await async_setup_entry(mock_hass, mock_config_entry)

            assert result is True
            mock_setup_webhook.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_setup_entry_skips_webhook_without_coordinator(
        self, mock_hass, mock_config_entry
    ):
        """Test webhook setup is skipped when no coordinator was created."""
        mock_hass.config_entries.async_forward_entry_setups = AsyncMock(
            return_value=True
        )

        with patch(
            "custom_components.early.async_setup_webhook", new_callable=AsyncMock
        ) as mock_setup_webhook:
            result = await async_setup_entry(mock_hass, mock_config_entry)

            assert result is True
            mock_setup_webhook.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_setup_entry_webhook_error_does_not_fail_setup(
        self, mock_hass, mock_config_entry
    ):
        """Test an unexpected webhook setup error doesn't fail entry setup."""

        async def _fake_forward(entry, platforms):
            if platforms == [Platform.SENSOR]:
                mock_hass.data[DOMAIN][entry.entry_id]["coordinator"] = MagicMock()
            return True

        mock_hass.config_entries.async_forward_entry_setups = AsyncMock(
            side_effect=_fake_forward
        )

        with patch(
            "custom_components.early.async_setup_webhook",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ):
            result = await async_setup_entry(mock_hass, mock_config_entry)

            assert result is True

    @pytest.mark.asyncio
    async def test_async_setup_entry_existing_domain(
        self, mock_hass, mock_config_entry
    ):
        """Test setting up entry when domain already exists in data."""
        mock_hass.data[DOMAIN] = {"existing_entry": {}}
        mock_hass.config_entries.async_forward_entry_setups = AsyncMock(
            return_value=True
        )

        result = await async_setup_entry(mock_hass, mock_config_entry)

        assert result is True
        assert "existing_entry" in mock_hass.data[DOMAIN]
        assert mock_config_entry.entry_id in mock_hass.data[DOMAIN]

    @pytest.mark.asyncio
    async def test_async_unload_entry_api(self, mock_hass, mock_config_entry):
        """Test unloading API config entry."""
        mock_hass.data[DOMAIN] = {
            mock_config_entry.entry_id: {
                "config": mock_config_entry.data,
                "bluetooth_devices": {},
            }
        }

        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        result = await async_unload_entry(mock_hass, mock_config_entry)

        assert result is True
        assert mock_config_entry.entry_id not in mock_hass.data[DOMAIN]

        mock_hass.config_entries.async_unload_platforms.assert_called_once_with(
            mock_config_entry, [Platform.SENSOR, Platform.SWITCH]
        )

    @pytest.mark.asyncio
    async def test_async_unload_entry_tears_down_webhook_when_coordinator_present(
        self, mock_hass, mock_config_entry
    ):
        """Test webhook teardown is attempted when a coordinator was stored."""
        mock_coordinator = MagicMock()
        mock_hass.data[DOMAIN] = {
            mock_config_entry.entry_id: {
                "config": mock_config_entry.data,
                "bluetooth_devices": {},
                "coordinator": mock_coordinator,
            }
        }

        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        with patch(
            "custom_components.early.async_unload_webhook", new_callable=AsyncMock
        ) as mock_unload_webhook:
            result = await async_unload_entry(mock_hass, mock_config_entry)

            assert result is True
            mock_unload_webhook.assert_called_once_with(
                mock_hass, mock_config_entry, mock_coordinator
            )

    @pytest.mark.asyncio
    async def test_async_unload_entry_webhook_error_does_not_fail_unload(
        self, mock_hass, mock_config_entry
    ):
        """Test an unexpected webhook teardown error doesn't fail entry unload."""
        mock_hass.data[DOMAIN] = {
            mock_config_entry.entry_id: {
                "config": mock_config_entry.data,
                "bluetooth_devices": {},
                "coordinator": MagicMock(),
            }
        }

        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        with patch(
            "custom_components.early.async_unload_webhook",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ):
            result = await async_unload_entry(mock_hass, mock_config_entry)

            assert result is True

    @pytest.mark.asyncio
    async def test_async_unload_entry_bluetooth(
        self, mock_hass, mock_bluetooth_config_entry
    ):
        """Test unloading Bluetooth config entry."""
        mock_device = MagicMock(spec=EarlyBluetoothDevice)
        mock_device.disconnect = AsyncMock()

        mock_hass.data[DOMAIN] = {
            mock_bluetooth_config_entry.entry_id: {
                "config": mock_bluetooth_config_entry.data,
                "bluetooth_devices": {"AA:BB:CC:DD:EE:FF": mock_device},
            }
        }

        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        result = await async_unload_entry(mock_hass, mock_bluetooth_config_entry)

        assert result is True
        assert mock_bluetooth_config_entry.entry_id not in mock_hass.data[DOMAIN]

        mock_device.disconnect.assert_called_once()
        mock_hass.config_entries.async_unload_platforms.assert_called_once_with(
            mock_bluetooth_config_entry, [Platform.SENSOR, Platform.SWITCH]
        )

    @pytest.mark.asyncio
    async def test_async_unload_entry_bluetooth_multiple_devices(
        self, mock_hass, mock_bluetooth_config_entry
    ):
        """Test unloading Bluetooth config entry with multiple devices."""
        mock_device1 = MagicMock(spec=EarlyBluetoothDevice)
        mock_device1.disconnect = AsyncMock()

        mock_device2 = MagicMock(spec=EarlyBluetoothDevice)
        mock_device2.disconnect = AsyncMock()

        mock_hass.data[DOMAIN] = {
            mock_bluetooth_config_entry.entry_id: {
                "config": mock_bluetooth_config_entry.data,
                "bluetooth_devices": {
                    "AA:BB:CC:DD:EE:FF": mock_device1,
                    "11:22:33:44:55:66": mock_device2,
                },
            }
        }

        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        result = await async_unload_entry(mock_hass, mock_bluetooth_config_entry)

        assert result is True
        assert mock_bluetooth_config_entry.entry_id not in mock_hass.data[DOMAIN]

        mock_device1.disconnect.assert_called_once()
        mock_device2.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_unload_entry_failed(self, mock_hass, mock_config_entry):
        """Test unload entry failure."""
        mock_hass.data[DOMAIN] = {
            mock_config_entry.entry_id: {
                "config": mock_config_entry.data,
                "bluetooth_devices": {},
            }
        }

        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)

        result = await async_unload_entry(mock_hass, mock_config_entry)

        assert result is False
        # Entry should remain in data when unload fails
        assert mock_config_entry.entry_id in mock_hass.data[DOMAIN]

    @pytest.mark.asyncio
    async def test_async_unload_entry_no_data(self, mock_hass, mock_config_entry):
        """Test unload entry with no data."""
        mock_hass.data[DOMAIN] = {}

        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        result = await async_unload_entry(mock_hass, mock_config_entry)

        assert result is True

    @pytest.mark.asyncio
    async def test_async_unload_entry_bluetooth_disconnect_error(
        self, mock_hass, mock_bluetooth_config_entry
    ):
        """Test unload with Bluetooth disconnect error."""
        mock_device = MagicMock(spec=EarlyBluetoothDevice)
        mock_device.disconnect = AsyncMock(side_effect=Exception("Disconnect error"))

        mock_hass.data[DOMAIN] = {
            mock_bluetooth_config_entry.entry_id: {
                "config": mock_bluetooth_config_entry.data,
                "bluetooth_devices": {"AA:BB:CC:DD:EE:FF": mock_device},
            }
        }

        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        # Should not raise exception
        with pytest.raises(Exception):
            result = await async_unload_entry(mock_hass, mock_bluetooth_config_entry)

    @pytest.mark.asyncio
    async def test_async_unload_entry_non_bluetooth_device(
        self, mock_hass, mock_bluetooth_config_entry
    ):
        """Test unload with non-Bluetooth device object."""
        mock_other_device = MagicMock()  # Not an EarlyBluetoothDevice

        mock_hass.data[DOMAIN] = {
            mock_bluetooth_config_entry.entry_id: {
                "config": mock_bluetooth_config_entry.data,
                "bluetooth_devices": {"AA:BB:CC:DD:EE:FF": mock_other_device},
            }
        }

        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        result = await async_unload_entry(mock_hass, mock_bluetooth_config_entry)

        assert result is True
        # Should not call disconnect on non-Bluetooth device
        assert (
            not hasattr(mock_other_device, "disconnect")
            or not mock_other_device.disconnect.called
        )
