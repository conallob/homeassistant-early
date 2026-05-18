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
    async def test_validate_input_success(self, mock_hass, mock_api_token_response):
        """Test validate_input with successful authentication."""
        with patch("custom_components.early.config_flow.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_api_token_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            # Make async_add_executor_job execute the lambda immediately
            async def mock_executor(func):
                return func()
            mock_hass.async_add_executor_job = mock_executor

            data = {
                CONF_API_KEY: "valid_key",
                CONF_API_SECRET: "valid_secret",
            }
            result = await validate_input(mock_hass, data)

            assert result == {"title": "EARLY Time Tracking"}
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_input_invalid_auth(self, mock_hass):
        """Test validate_input with invalid credentials."""
        with patch("custom_components.early.config_flow.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.raise_for_status.side_effect = Exception("Unauthorized")
            mock_post.return_value = mock_response

            # Make async_add_executor_job execute the lambda immediately
            async def mock_executor(func):
                return func()
            mock_hass.async_add_executor_job = mock_executor

            data = {
                CONF_API_KEY: "invalid_key",
                CONF_API_SECRET: "invalid_secret",
            }

            with pytest.raises(InvalidAuth):
                await validate_input(mock_hass, data)

    @pytest.mark.asyncio
    async def test_validate_input_cannot_connect(self, mock_hass):
        """Test validate_input with connection error."""
        import requests as req_module

        with patch("custom_components.early.config_flow.requests.post") as mock_post:
            mock_post.side_effect = req_module.exceptions.ConnectionError("Connection failed")

            # Make async_add_executor_job execute the lambda immediately
            async def mock_executor(func):
                return func()
            mock_hass.async_add_executor_job = mock_executor

            data = {
                CONF_API_KEY: "test_key",
                CONF_API_SECRET: "test_secret",
            }

            with pytest.raises(CannotConnect):
                await validate_input(mock_hass, data)

    @pytest.mark.asyncio
    async def test_validate_input_http_error(self, mock_hass):
        """Test validate_input with HTTP error."""
        import requests as req_module

        with patch("custom_components.early.config_flow.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = req_module.exceptions.HTTPError("Server error")
            mock_post.return_value = mock_response

            # Make async_add_executor_job execute the lambda immediately
            async def mock_executor(func):
                return func()
            mock_hass.async_add_executor_job = mock_executor

            data = {
                CONF_API_KEY: "test_key",
                CONF_API_SECRET: "test_secret",
            }

            with pytest.raises(CannotConnect):
                await validate_input(mock_hass, data)

    @pytest.mark.asyncio
    async def test_form_user_step(self, mock_hass):
        """Test we get the form for user step."""
        flow = ConfigFlow()
        flow.hass = mock_hass
        mock_hass.config_entries = MagicMock()

        result = await flow.async_step_user()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

    @pytest.mark.asyncio
    async def test_form_user_success(self, mock_hass, mock_api_token_response):
        """Test successful user step creates entry."""
        flow = ConfigFlow()
        flow.hass = mock_hass
        mock_hass.config_entries = MagicMock()

        async def mock_executor(func):
            return func()
        mock_hass.async_add_executor_job = mock_executor

        with patch("custom_components.early.config_flow.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_api_token_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = await flow.async_step_user(
                user_input={
                    CONF_API_KEY: "test_key",
                    CONF_API_SECRET: "test_secret",
                }
            )

            assert result["type"] == FlowResultType.CREATE_ENTRY
            assert result["title"] == "EARLY Time Tracking"
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
        import requests as req_module

        flow = ConfigFlow()
        flow.hass = mock_hass
        mock_hass.config_entries = MagicMock()

        async def mock_executor(func):
            return func()
        mock_hass.async_add_executor_job = mock_executor

        with patch("custom_components.early.config_flow.requests.post") as mock_post:
            mock_post.side_effect = req_module.exceptions.ConnectionError("Connection failed")

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
    async def test_bluetooth_step_device_found(self, mock_hass, mock_ble_device):
        """Test bluetooth step with device found."""
        flow = ConfigFlow()
        flow.hass = mock_hass
        mock_hass.config_entries = MagicMock()

        # Create a mock discovery info
        discovery_info = MagicMock()
        discovery_info.name = "Timeular ZEI"
        discovery_info.address = "AA:BB:CC:DD:EE:FF"

        # Mock the unique_id check and confirm_only (context is read-only in bare flow)
        with patch.object(flow, '_abort_if_unique_id_configured'):
            with patch.object(flow, 'async_set_unique_id'):
                with patch.object(flow, '_set_confirm_only'):
                    result = await flow.async_step_bluetooth(discovery_info)

                    assert result["type"] == FlowResultType.FORM
                    assert result["step_id"] == "bluetooth_confirm"

    @pytest.mark.asyncio
    async def test_bluetooth_confirm_proceeds_to_api_step(self, mock_hass):
        """Test bluetooth confirmation proceeds to API credentials step."""
        flow = ConfigFlow()
        flow.hass = mock_hass
        mock_hass.config_entries = MagicMock()

        # Set up discovery info
        discovery_info = MagicMock()
        discovery_info.name = "Timeular ZEI"
        discovery_info.address = "AA:BB:CC:DD:EE:FF"
        flow._discovery_info = discovery_info

        result = await flow.async_step_bluetooth_confirm(user_input={})

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "bluetooth_api"

    @pytest.mark.asyncio
    async def test_bluetooth_confirm_shows_form(self, mock_hass):
        """Test bluetooth confirmation shows form when no user input."""
        flow = ConfigFlow()
        flow.hass = mock_hass
        mock_hass.config_entries = MagicMock()

        # Set up discovery info
        discovery_info = MagicMock()
        discovery_info.name = "Timeular ZEI"
        discovery_info.address = "AA:BB:CC:DD:EE:FF"
        flow._discovery_info = discovery_info

        with patch.object(flow, '_set_confirm_only'):
            result = await flow.async_step_bluetooth_confirm(user_input=None)

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "bluetooth_confirm"

    @pytest.mark.asyncio
    async def test_bluetooth_unique_id_already_configured(
        self, mock_hass, mock_ble_device
    ):
        """Test bluetooth setup aborts if device already configured."""
        flow = ConfigFlow()
        flow.hass = mock_hass
        mock_hass.config_entries = MagicMock()

        # Create a mock discovery info
        discovery_info = MagicMock()
        discovery_info.name = "Timeular ZEI"
        discovery_info.address = "AA:BB:CC:DD:EE:FF"

        # Mock to test that uniqueness check is performed
        with patch.object(flow, 'async_set_unique_id') as mock_set_unique:
            with patch.object(flow, '_abort_if_unique_id_configured') as mock_abort:
                with patch.object(flow, '_set_confirm_only'):
                    result = await flow.async_step_bluetooth(discovery_info)

                    # Should call the uniqueness checks
                    mock_set_unique.assert_called_once_with(discovery_info.address)
                    mock_abort.assert_called_once()

    @pytest.mark.asyncio
    async def test_bluetooth_api_step_shows_form(self, mock_hass, mock_ble_device):
        """Test bluetooth API step shows form."""
        flow = ConfigFlow()
        flow.hass = mock_hass
        flow._discovery_info = mock_ble_device

        result = await flow.async_step_bluetooth_api()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "bluetooth_api"
        assert result["errors"] == {}

    @pytest.mark.asyncio
    async def test_bluetooth_api_with_credentials(
        self, mock_hass, mock_api_token_response
    ):
        """Test bluetooth API step with valid credentials."""
        flow = ConfigFlow()
        flow.hass = mock_hass

        # Create discovery info with proper attributes
        discovery_info = MagicMock()
        discovery_info.name = "Timeular ZEI"
        discovery_info.address = "AA:BB:CC:DD:EE:FF"
        flow._discovery_info = discovery_info

        with patch("custom_components.early.config_flow.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_api_token_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            async def mock_executor(func):
                return func()
            mock_hass.async_add_executor_job = mock_executor

            result = await flow.async_step_bluetooth_api(
                user_input={
                    CONF_API_KEY: "test_key",
                    CONF_API_SECRET: "test_secret",
                }
            )

            assert result["type"] == FlowResultType.CREATE_ENTRY
            assert result["title"] == "Timeular ZEI"
            assert result["data"]["address"] == "AA:BB:CC:DD:EE:FF"
            # Credentials must be in options, not data, to allow HA encryption
            assert CONF_API_KEY not in result["data"]
            assert result["options"][CONF_API_KEY] == "test_key"
            assert result["options"][CONF_API_SECRET] == "test_secret"

    @pytest.mark.asyncio
    async def test_bluetooth_api_without_credentials(self, mock_hass):
        """Test bluetooth API step without credentials (skipped)."""
        flow = ConfigFlow()
        flow.hass = mock_hass

        # Create discovery info with proper attributes
        discovery_info = MagicMock()
        discovery_info.name = "Timeular ZEI"
        discovery_info.address = "AA:BB:CC:DD:EE:FF"
        flow._discovery_info = discovery_info

        result = await flow.async_step_bluetooth_api(user_input={})

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Timeular ZEI"
        assert result["data"]["address"] == "AA:BB:CC:DD:EE:FF"
        assert CONF_API_KEY not in result["data"]
        assert CONF_API_SECRET not in result["data"]

    @pytest.mark.asyncio
    async def test_bluetooth_api_invalid_credentials(
        self, mock_hass, mock_ble_device
    ):
        """Test bluetooth API step with invalid credentials (no token in response)."""
        flow = ConfigFlow()
        flow.hass = mock_hass
        flow._discovery_info = mock_ble_device

        async def mock_executor(func):
            return func()
        mock_hass.async_add_executor_job = mock_executor

        with patch("custom_components.early.config_flow.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()  # doesn't raise
            mock_response.status_code = 200
            mock_response.json.return_value = {}  # no token key → InvalidAuth
            mock_post.return_value = mock_response

            result = await flow.async_step_bluetooth_api(
                user_input={
                    CONF_API_KEY: "invalid_key",
                    CONF_API_SECRET: "invalid_secret",
                }
            )

            assert result["type"] == FlowResultType.FORM
            assert result["errors"] == {"base": "invalid_auth"}

    @pytest.mark.asyncio
    async def test_bluetooth_api_partial_credentials(self, mock_hass, mock_ble_device):
        """Test bluetooth API step rejects partial credentials (only key, no secret)."""
        flow = ConfigFlow()
        flow.hass = mock_hass
        flow._discovery_info = mock_ble_device

        result = await flow.async_step_bluetooth_api(
            user_input={
                CONF_API_KEY: "some_key",
                CONF_API_SECRET: "",  # missing secret
            }
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "missing_credentials"}

    @pytest.mark.asyncio
    async def test_bluetooth_api_cannot_connect(self, mock_hass):
        """Test bluetooth API step with connection error."""
        import requests as req_module

        flow = ConfigFlow()
        flow.hass = mock_hass
        mock_hass.config_entries = MagicMock()

        # Create discovery info with proper attributes
        discovery_info = MagicMock()
        discovery_info.name = "Timeular ZEI"
        discovery_info.address = "AA:BB:CC:DD:EE:FF"
        flow._discovery_info = discovery_info

        with patch("custom_components.early.config_flow.requests.post") as mock_post:
            mock_post.side_effect = req_module.exceptions.ConnectionError("Connection failed")

            async def mock_executor(func):
                return func()
            mock_hass.async_add_executor_job = mock_executor

            result = await flow.async_step_bluetooth_api(
                user_input={
                    CONF_API_KEY: "test_key",
                    CONF_API_SECRET: "test_secret",
                }
            )

            assert result["type"] == FlowResultType.FORM
            assert result["errors"] == {"base": "cannot_connect"}
