# EARLY (formerly Timeular) Integration for Home Assistant

A custom Home Assistant integration for [EARLY](https://early.app) (formerly known as Timeular), a time tracking application. This integration allows you to monitor your current time tracking activity in Home Assistant.

## Features

### Cloud API Integration
- **Current Activity Sensor**: Displays the currently tracked activity via cloud API, by name (not just whether tracking is on or off)
- **Activity Attributes**: Provides additional details like activity ID, name, start time, and notes
- **Automatic Updates**: Polls the EARLY API every 30 seconds for current tracking status
- **Per-Activity Switches**: Every activity configured in your EARLY account is exposed as its own `switch` entity, so you can start/stop tracking a specific activity from an automation, dashboard tile, or phone widget

### Bluetooth Tracker Support
- **Automatic Discovery**: Detects EARLY ZEI Bluetooth trackers automatically
- **Orientation Sensor**: Shows which side (0-8) of the physical tracker is facing up
- **Current Activity Sensor**: When paired with optional API credentials, maps the tracker's orientation to the matching EARLY activity name
- **Real-time Updates**: Instant notification when the tracker orientation changes
- **Signal Strength**: Monitor Bluetooth connection quality

### General
- **Config Flow**: Easy setup through the Home Assistant UI
- **Dual Mode**: Use API-based tracking, Bluetooth tracker, or both simultaneously

## Installation

### HACS (Recommended)

1. Add this repository as a custom repository in HACS
2. Search for "EARLY" in HACS
3. Click "Install"
4. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/early` directory to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Configuration

### Option 1: Bluetooth Tracker (Automatic)

If you have an EARLY ZEI physical tracker:

1. Make sure Bluetooth is enabled on your Home Assistant server
2. Turn on your EARLY tracker (press the power button)
3. Home Assistant will automatically discover the tracker
4. Go to **Settings** → **Devices & Services** → **Discovered**
5. Click **Configure** on the discovered EARLY Tracker
6. Click **Submit** to add it

The tracker will appear as a device with orientation and signal strength sensors.

### Option 2: Cloud API Setup

To track activities via the cloud API:

#### Prerequisites

Generate API credentials from your EARLY account:

1. Log in to [EARLY](https://early.app)
2. Go to your account settings
3. Navigate to "API & Integrations"
4. Generate a new API Key and API Secret pair
5. Save both values securely

#### Setup in Home Assistant

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **EARLY**
4. Enter your API Key and API Secret
5. Click **Submit**

### Using Both

You can set up both the Bluetooth tracker and the Cloud API simultaneously. They will work independently and provide different sensors.

## Sensors

### Cloud API Sensors

#### EARLY Current Activity

**Entity ID**: `sensor.early_current_activity`

**States**:
- `idle`: No activity is currently being tracked
- `<activity_name>`: The name of the currently tracked activity
- `unavailable`: Cannot connect to EARLY API

**Attributes**:
- `activity_id`: The unique ID of the current activity
- `activity_name`: The name of the current activity
- `started_at`: When the current tracking session started (ISO 8601 format)
- `note`: Any note associated with the current tracking session

### Bluetooth Tracker Sensors

#### Tracker Orientation

**Entity ID**: `sensor.<device_name>_orientation`

**States**: Integer from 0-8 representing which side of the tracker is facing up
- `0`: Base/sleeping (no side up)
- `1-8`: The numbered side that is currently facing up

**Attributes**:
- `orientation`: Current orientation value
- `device_address`: Bluetooth MAC address of the tracker

#### Signal Strength (RSSI)

**Entity ID**: `sensor.<device_name>_signal_strength`

**States**: Signal strength in dBm (disabled by default)

This sensor shows the Bluetooth signal strength between Home Assistant and the tracker.

#### Tracker Current Activity

**Entity ID**: `sensor.<device_name>_current_activity`

Only created when the Bluetooth tracker entry is also configured with API credentials (see [Option 1: Bluetooth Tracker](#option-1-bluetooth-tracker-automatic)).

**States**:
- `idle`: The current orientation isn't mapped to an activity
- `<activity_name>`: The activity assigned to the side currently facing up in your EARLY account

**Attributes**:
- `orientation`: Current orientation value
- `device_address`: Bluetooth MAC address of the tracker
- `activity_name`: The name of the current activity

## Switches

### EARLY Activity Switches

**Entity ID**: `switch.early_<activity_name>` (a slugified version of the activity name - check **Settings** → **Devices & Services** → **Entities** for the exact ID if your activity name has punctuation or non-ASCII characters)

Created for every activity in your EARLY account, for any config entry that has API credentials configured (a Cloud API entry, or a Bluetooth entry with optional API credentials added). Turning a switch **on** starts tracking that activity via the EARLY API; turning it **off** stops tracking (only if that activity is the one currently being tracked). Exactly one activity switch is `on` at a time, matching `sensor.early_current_activity`.

This is the building block for lock-screen widgets and Shortcuts automations: add an activity switch to a Home Assistant dashboard or expose it to the [Home Assistant Companion App widget](https://companion.home-assistant.io/) to start/stop a specific activity with one tap.

**Attributes**:
- `activity_id`: The unique ID of the activity
- `activity_name`: The name of the activity

## Example Automations

### Notify when starting work

```yaml
automation:
  - alias: "Notify when work tracking starts"
    trigger:
      - platform: state
        entity_id: sensor.early_current_activity
        to: "Work"
    action:
      - service: notify.mobile_app
        data:
          message: "Work tracking started!"
```

### Turn on focus mode when tracking (Cloud API)

```yaml
automation:
  - alias: "Enable focus mode when tracking"
    trigger:
      - platform: state
        entity_id: sensor.early_current_activity
        from: "idle"
    condition:
      - condition: template
        value_template: "{{ states('sensor.early_current_activity') != 'idle' }}"
    action:
      - service: input_boolean.turn_on
        target:
          entity_id: input_boolean.focus_mode
```

### React to Bluetooth tracker orientation changes

```yaml
automation:
  - alias: "Start activity when flipping tracker"
    trigger:
      - platform: state
        entity_id: sensor.timeular_zei_orientation
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.state != '0' }}"
    action:
      - service: notify.mobile_app
        data:
          message: "Tracker flipped to side {{ trigger.to_state.state }}"
```

### Map tracker sides to activities

```yaml
automation:
  - alias: "Tracker side 1 - Start work"
    trigger:
      - platform: state
        entity_id: sensor.timeular_zei_orientation
        to: "1"
    action:
      - service: light.turn_on
        target:
          entity_id: light.desk_lamp
        data:
          brightness: 255
      - service: notify.mobile_app
        data:
          message: "Work mode activated!"

  - alias: "Tracker side 2 - Start break"
    trigger:
      - platform: state
        entity_id: sensor.timeular_zei_orientation
        to: "2"
    action:
      - service: light.turn_on
        target:
          entity_id: light.living_room
        data:
          brightness: 128
      - service: notify.mobile_app
        data:
          message: "Break time!"
```

### Toggle an activity from a lock screen widget

Add `switch.early_work` to a dashboard, or expose it as a widget via the Home Assistant Companion App, to start/stop tracking "Work" with one tap:

```yaml
automation:
  - alias: "Stop tracking Work after hours"
    trigger:
      - platform: time
        at: "18:00:00"
    condition:
      - condition: state
        entity_id: switch.early_work
        state: "on"
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.early_work
```

A phone Shortcuts automation ("if I open my work phone after 6pm") can call the same switch via the Home Assistant API or the companion app's `switch.turn_off` action.

## Technical Information

### Cloud API

This integration uses the EARLY Public API v3:
- **Base URL**: `https://api.timeular.com/api/v3`
- **Documentation**: [https://developers.early.app](https://developers.early.app)

### Bluetooth Tracker

The integration communicates with EARLY ZEI trackers using Bluetooth Low Energy (BLE):
- **Service UUID**: `c7e70010-c847-11e6-8175-8c89a55d403c`
- **Orientation Characteristic UUID**: `c7e70012-c847-11e6-8175-8c89a55d403c`
- **Device Name**: Starts with "Timeular ZEI"
- **Protocol**: Unencrypted BLE notifications for orientation changes

## Troubleshooting

### Cloud API Issues

#### Cannot Connect Error
- Verify your internet connection
- Check if api.timeular.com is accessible from your network
- Ensure Home Assistant can make outbound HTTPS connections

#### Invalid Authentication Error
- Double-check your API Key and API Secret
- Regenerate credentials in the EARLY web interface if needed
- Remove the integration and add it again with fresh credentials

#### Sensor Shows Unavailable
- Check Home Assistant logs for error messages
- Verify the EARLY API service status
- Try reloading the integration

### Bluetooth Tracker Issues

#### Tracker Not Discovered
- Ensure Bluetooth is enabled on your Home Assistant server
- Press the power button on the tracker to wake it up
- Make sure the tracker isn't already paired with another device exclusively
- Check that your Home Assistant server is within Bluetooth range (typically 10m/33ft)

#### Tracker Disconnects Frequently
- Move the Home Assistant server closer to where you use the tracker
- Check for Bluetooth interference from other devices
- Ensure the tracker battery isn't low (LED will show red when low)

#### Orientation Not Updating
- Check that the tracker is connected (check the sensor availability)
- Try restarting the integration
- Power cycle the tracker (press and hold the button until LED turns green, then release)

## Support

- **Issues**: [GitHub Issues](https://github.com/conallob/homeassistant-early/issues)
- **EARLY Support**: [early.app/support](https://early.app/support)
- **Home Assistant Community**: [community.home-assistant.io](https://community.home-assistant.io)

## License

This project is licensed under the MIT License.

## Credits

Developed by [@conallob](https://github.com/conallob)

EARLY (formerly Timeular) is a trademark of Timeular GmbH.
