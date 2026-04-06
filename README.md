# Gree Climate Extended (`gree_ext`)

A Home Assistant custom integration that replaces the built-in `gree` integration with extended telemetry and fan control for Gree/Tosot floor-standing mini splits.

## Features

All existing Gree climate functionality is preserved, plus:

| Entity | Type | Description |
|--------|------|-------------|
| `binary_sensor.<name>_compressor_active` | Binary Sensor | `on` when compressor is running (CompFreq > 0) |
| `binary_sensor.<name>_idle` | Binary Sensor | `on` when unit is powered on but compressor has stopped |
| `sensor.<name>_indoor_coil_temp` | Sensor | Indoor coil (evaporator) temperature in °C |
| `sensor.<name>_outdoor_coil_temp` | Sensor | Outdoor coil (condenser) temperature in °C |
| `gree_ext.force_fan_off` | Service | Immediately powers off the unit to stop the fan |

## Installation

### HACS (recommended)
1. Add this repository as a custom repository in HACS
2. Install "Gree Climate Extended"
3. Restart Home Assistant
4. **Disable** the built-in `gree` integration (Settings → Integrations)
5. Add "Gree Climate Extended" integration

### Manual
1. Copy `custom_components/gree_ext/` to your HA `custom_components/` directory
2. Restart Home Assistant
3. Disable the built-in `gree` integration
4. Add "Gree Climate Extended" integration

## Important: Disable Built-in Gree First

This integration binds to the same UDP devices as the built-in `gree` integration. Running both simultaneously will cause conflicts. **Disable or remove** the built-in `gree` integration before enabling this one.

## Architecture

```
┌────────────────────────────────────────────┐
│            Home Assistant                  │
│                                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ Climate  │  │ Binary   │  │ Sensor   │ │
│  │ Entity   │  │ Sensors  │  │ Entities │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘ │
│       │              │              │       │
│       └──────┬───────┴──────────────┘       │
│              │                              │
│  ┌───────────▼───────────────┐              │
│  │  DeviceDataUpdateCoord.   │              │
│  │  ┌─────────────────────┐  │              │
│  │  │ Standard Props      │  │              │
│  │  │ (greeclimate lib)   │  │              │
│  │  ├─────────────────────┤  │              │
│  │  │ Extended Props      │  │              │
│  │  │ CompFreq, TemInlet  │  │              │
│  │  │ TemOutlet           │  │              │
│  │  └─────────────────────┘  │              │
│  └───────────┬───────────────┘              │
│              │ UDP :7000                    │
└──────────────┼──────────────────────────────┘
               │
        ┌──────▼──────┐
        │  Gree/Tosot │
        │  Mini Split  │
        └─────────────┘
```

## Protocol Extension

The Gree UDP protocol supports requesting arbitrary named properties via the `cols` array in status messages. This integration requests three additional properties beyond those in the `greeclimate` library:

| Property | Name | Description |
|----------|------|-------------|
| `CompFreq` | Compressor Frequency | 0 = off, >0 = running (Hz) |
| `TemInlet` | Indoor Coil Temp | Evaporator temperature (°C with +40 offset on FW <4.0) |
| `TemOutlet` | Outdoor Coil Temp | Condenser temperature (°C with +40 offset on FW <4.0) |

Not all firmware versions/models support these properties. Sensors gracefully show "Unknown" when the device doesn't respond with the requested data.

## Service: `gree_ext.force_fan_off`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `entity_id` | string/list | No | Target climate entity. If omitted, all devices are targeted. |

**Behavior**: Sends `Pow=0` to the device, immediately stopping both the compressor and fan. This is a safe, universal command that works across all Gree/Tosot models.

## Example Automations

### Auto-kill fan when compressor stops (idle detection)

```yaml
automation:
  - alias: "HVAC - Kill fan when compressor stops"
    description: >-
      When the mini split reaches target temperature and the compressor
      shuts off, turn off the unit entirely to stop the fan from running
      indefinitely in the background.
    triggers:
      - trigger: state
        entity_id: binary_sensor.living_room_ac_idle
        to: "on"
        for:
          seconds: 30  # debounce — wait 30s to confirm compressor truly stopped
    conditions:
      - condition: state
        entity_id: climate.living_room_ac
        state:
          - "cool"
          - "heat"
    actions:
      - action: gree_ext.force_fan_off
        data:
          entity_id: climate.living_room_ac
      - action: notify.persistent_notification
        data:
          title: "HVAC Fan Killed"
          message: "Compressor was idle for 30s — unit powered off."
```

### Alert on high indoor coil temperature

```yaml
automation:
  - alias: "HVAC - High coil temperature warning"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.living_room_ac_indoor_coil_temp
        above: 55
    actions:
      - action: notify.persistent_notification
        data:
          title: "⚠️ HVAC Coil Temperature High"
          message: >-
            Indoor coil temperature is {{ states('sensor.living_room_ac_indoor_coil_temp') }}°C.
            Check for restricted airflow or dirty filter.
```

### Re-enable HVAC after force-off (conditional restart)

```yaml
automation:
  - alias: "HVAC - Restart after force-off if still needed"
    description: >-
      After the fan-kill automation powers off the unit, check if the room
      temperature has drifted away from the setpoint and re-enable cooling.
    triggers:
      - trigger: state
        entity_id: climate.living_room_ac
        to: "off"
        for:
          minutes: 10
    conditions:
      - condition: numeric_state
        entity_id: sensor.living_room_temperature
        above: 25  # only restart if room is warm
    actions:
      - action: climate.turn_on
        target:
          entity_id: climate.living_room_ac
```

## Testing with a Real Unit

### Step 1: Verify UDP connectivity
```bash
# From the HA host, check that UDP port 7000 is reachable:
nmap -sU -p 7000 <device-ip>
```

### Step 2: Check protocol property support
Enable debug logging in `configuration.yaml`:
```yaml
logger:
  default: warning
  logs:
    custom_components.gree_ext: debug
    greeclimate: debug
```

After a poll cycle (~60s), look for log entries like:
```
Extended properties for gree_ext-Living Room: {'CompFreq': 42, 'TemInlet': 62, 'TemOutlet': 58}
```

If `CompFreq` / `TemInlet` / `TemOutlet` don't appear or are 0, your firmware may not support those properties. The sensors will show "Unknown".

### Step 3: Verify entities
In Developer Tools → States, filter for `gree_ext`. You should see:
- `climate.*` — standard HVAC controls
- `binary_sensor.*_compressor_active`
- `binary_sensor.*_idle`
- `sensor.*_indoor_coil_temp`
- `sensor.*_outdoor_coil_temp`
- Switches: light, quiet, fresh air, xfan, health

### Step 4: Test the service
In Developer Tools → Services:
```yaml
service: gree_ext.force_fan_off
data:
  entity_id: climate.living_room_ac
```

The unit should immediately power off.

## Compatibility

- **greeclimate library**: 2.1.1 (same as upstream HA integration)
- **Home Assistant**: 2024.12.0+
- **Protocol**: Gree WiFi protocol v1 (AES128/ECB) and v2 (AES128/GCM)
- **Tested models**: Tosot/Gree floor-standing mini splits with WiFi module
- **Communication**: Local UDP only, port 7000. No cloud dependencies.

## License

MIT
