from homeassistant import core
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.components.application_credentials import AuthImplementation, AuthorizationServer, ClientCredential


async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    """Set up the Timeular component."""
    # @TODO: Add setup code.
    return True


class OAuth2Impl(AuthImplementation):
    """Custom OAuth2 implementation for Timeular.com."""
    # ... Override AbstractOAuth2Implementation details

async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return auth implementation for timeular.com."""
    return OAuth2Impl(
        hass,
        auth_domain,
        credential,
        AuthorizationServer(
            authorize_url="https://api.timeular.com/api/v3/developer/sign-in",
            token_url="https://api.timeular.com/api/v3/developer/api-access"
        )
    )
