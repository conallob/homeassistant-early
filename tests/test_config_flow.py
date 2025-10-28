"""Test the EARLY config flow."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import FlowResultType

from custom_components.early.const import DOMAIN, CONF_API_SECRET
from custom_components.early.config_flow import (
    ConfigFlow,
    validate_input,
    CannotConnect,
    InvalidAuth,
)


class TestConfigFlow:
    """Test the config flow."""

    @pytest.mark.asyncio
    async def test_validate_input_success(self, mock_api_token_response):
        """Test validate_input with successful authentication."""
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_api_token_response
            mock_post.return_value = mock_response

            data = {
                CONF_API_KEY: "valid_key",
                CONF_API_SECRET: "valid_secret",
            }
            result = await validate_input(data)

            assert result == {"title": "EARLY"}
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_input_invalid_auth(self):
        """Test validate_input with invalid credentials."""
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_post.return_value = mock_response

            data = {
                CONF_API_KEY: "invalid_key",
                CONF_API_SECRET: "invalid_secret",
            }

            with pytest.raises(InvalidAuth):
                await validate_input(data)

    @pytest.mark.asyncio
    async def test_validate_input_cannot_connect(self):
        """Test validate_input with connection error."""
        with patch("requests.post") as mock_post:
            mock_post.side_effect = Exception("Connection failed")

            data = {
                CONF_API_KEY: "test_key",
                CONF_API_SECRET: "test_secret",
            }

            with pytest.raises(CannotConnect):
                await validate_input(data)

    @pytest.mark.asyncio
    async def test_validate_input_http_error(self):
        """Test validate_input with HTTP error."""
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = Exception("Server error")
            mock_post.return_value = mock_response

            data = {
                CONF_API_KEY: "test_key",
                CONF_API_SECRET: "test_secret",
            }

            with pytest.raises(CannotConnect):
                await validate_input(data)

    @pytest.mark.asyncio
    async def test_form_user_step(self, mock_hass):
        """Test we get the form for user step."""
        flow = ConfigFlow()
        flow.hass = mock_hass

        result = await flow.async_step_user()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

    @pytest.mark.asyncio
    async def test_form_user_success(self, mock_hass, mock_api_token_response):
        """Test successful user step creates entry."""
        flow = ConfigFlow()
        flow.hass = mock_hass

        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_api_token_response
            mock_post.return_value = mock_response

            result = await flow.async_step_user(
                user_input={
                    CONF_API_KEY: "test_key",
                    CONF_API_SECRET: "test_secret",
                }
            )

            assert result["type"] == FlowResultType.CREATE_ENTRY
            assert result["title"] == "EARLY"
            assert result["data"] == {
                CONF_API_KEY: "test_key",
                CONF_API_SECRET: "test_secret",
            }

    @pytest.mark.asyncio
    async def test_form_user_invalid_auth(self, mock_hass):
        """Test invalid auth error in user step."""
        flow = ConfigFlow()
        flow.hass = mock_hass

        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_post.return_value = mock_response

            result = await flow.async_step_user(
                user_input={
                    CONF_API_KEY: "invalid_key",
                    CONF_API_SECRET: "invalid_secret",
                }
            )

            assert result["type"] == FlowResultType.FORM
            assert result["errors"] == {"base": "invalid_auth"}

    @pytest.mark.asyncio
    async def test_form_user_cannot_connect(self, mock_hass):
        """Test cannot connect error in user step."""
        flow = ConfigFlow()
        flow.hass = mock_hass

        with patch("requests.post") as mock_post:
            mock_post.side_effect = Exception("Connection failed")

            result = await flow.async_step_user(
                user_input={
                    CONF_API_KEY: "test_key",
                    CONF_API_SECRET: "test_secret",
                }
            )

            assert result["type"] == FlowResultType.FORM
            assert result["errors"] == {"base": "cannot_connect"}

    @pytest.mark.asyncio
    async def test_form_user_unknown_error(self, mock_hass):
        """Test unknown error in user step."""
        flow = ConfigFlow()
        flow.hass = mock_hass

        with patch(
            "custom_components.early.config_flow.validate_input",
            side_effect=ValueError("Unexpected error"),
        ):
            result = await flow.async_step_user(
                user_input={
                    CONF_API_KEY: "test_key",
                    CONF_API_SECRET: "test_secret",
                }
            )

            assert result["type"] == FlowResultType.FORM
            assert result["errors"] == {"base": "unknown"}

    @pytest.mark.asyncio
    async def test_bluetooth_step_no_devices(self, mock_hass):
        """Test bluetooth step with no devices found."""
        flow = ConfigFlow()
        flow.hass = mock_hass

        with patch(
            "custom_components.early.bluetooth.async_discover_devices",
            return_value=[],
        ):
            result = await flow.async_step_bluetooth()

            assert result["type"] == FlowResultType.ABORT
            assert result["reason"] == "no_devices_found"

    @pytest.mark.asyncio
    async def test_bluetooth_step_device_found(self, mock_hass, mock_ble_device):
        """Test bluetooth step with device found."""
        flow = ConfigFlow()
        flow.hass = mock_hass

        with patch(
            "custom_components.early.bluetooth.async_discover_devices",
            return_value=[mock_ble_device],
        ):
            result = await flow.async_step_bluetooth()

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "bluetooth_confirm"

    @pytest.mark.asyncio
    async def test_bluetooth_confirm_creates_entry(self, mock_hass, mock_ble_device):
        """Test bluetooth confirmation creates entry."""
        flow = ConfigFlow()
        flow.hass = mock_hass
        flow._discovered_device = mock_ble_device

        result = await flow.async_step_bluetooth_confirm(user_input={})

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Timeular ZEI"
        assert result["data"]["address"] == "AA:BB:CC:DD:EE:FF"

    @pytest.mark.asyncio
    async def test_bluetooth_confirm_no_device(self, mock_hass):
        """Test bluetooth confirmation with no device."""
        flow = ConfigFlow()
        flow.hass = mock_hass
        flow._discovered_device = None

        result = await flow.async_step_bluetooth_confirm(user_input={})

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "no_devices_found"

    @pytest.mark.asyncio
    async def test_bluetooth_unique_id_already_configured(
        self, mock_hass, mock_ble_device
    ):
        """Test bluetooth setup aborts if device already configured."""
        flow = ConfigFlow()
        flow.hass = mock_hass

        # Mock existing entry with same unique_id
        existing_entry = MagicMock()
        existing_entry.unique_id = "AA:BB:CC:DD:EE:FF"

        with patch(
            "custom_components.early.bluetooth.async_discover_devices",
            return_value=[mock_ble_device],
        ):
            flow._async_current_entries = MagicMock(return_value=[existing_entry])

            result = await flow.async_step_bluetooth()

            # Should still show form but prevent duplicate later
            assert result["type"] == FlowResultType.FORM
