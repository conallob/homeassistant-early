# EARLY Integration Tests

This directory contains comprehensive unit tests for the EARLY Home Assistant integration.

## Test Coverage

The test suite covers:

- **Config Flow** (`test_config_flow.py`)
  - API credential validation
  - Bluetooth device discovery
  - Error handling
  - Duplicate entry prevention

- **API Coordinator & Sensor** (`test_sensor.py`)
  - Token management and caching
  - Token refresh on expiration
  - Activity fetching
  - Tracking data updates
  - Start/stop tracking
  - Current activity sensor states and attributes

- **Activity Switches** (`test_switch.py`)
  - Switch state management
  - Start/stop tracking via switches
  - Error handling
  - Availability

- **Bluetooth Device** (`test_bluetooth.py`)
  - Device connection/disconnection
  - Orientation reading
  - Callback registration
  - Device matching and discovery

- **Bluetooth Sensors** (`test_bluetooth_sensor.py`)
  - Orientation sensor
  - RSSI sensor
  - Device info
  - Availability

- **Integration Setup** (`test_init.py`)
  - Entry setup for API and Bluetooth
  - Platform forwarding
  - Entry unloading
  - Bluetooth device cleanup

## Running Tests

### Prerequisites

Install the required dependencies:

```bash
pip install -r requirements-test.txt
```

Or install Home Assistant core to get all dependencies:

```bash
pip install homeassistant
```

### Run All Tests

```bash
pytest tests/
```

### Run Specific Test File

```bash
pytest tests/test_sensor.py
```

### Run with Coverage

```bash
pytest tests/ --cov=custom_components.early --cov-report=html
```

## Test Structure

Tests use pytest fixtures defined in `conftest.py`:
- `mock_hass` - Mock Home Assistant instance
- `mock_config_entry` - Mock API config entry
- `mock_bluetooth_config_entry` - Mock Bluetooth config entry
- `mock_api_token_response` - Mock API token response
- `mock_activities_response` - Mock activities list
- `mock_tracking_response_active` - Mock active tracking data
- `mock_tracking_response_idle` - Mock idle state
- `mock_ble_device` - Mock Bluetooth device
- `mock_bleak_client` - Mock Bleak BLE client

## Note

These tests are designed to run independently without requiring a full Home Assistant installation, using mocks for all external dependencies including:
- Home Assistant core
- API requests
- Bluetooth Low Energy (Bleak)
- Home Assistant entities and platforms
