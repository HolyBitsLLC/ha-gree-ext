"""Constants for the Gree Climate Extended integration."""

from __future__ import annotations

DOMAIN = "gree_ext"

DISCOVERY_SCAN_INTERVAL = 300
DISCOVERY_TIMEOUT = 8
DISPATCH_DEVICE_DISCOVERED = "gree_ext_device_discovered"

FAN_MEDIUM_LOW = "medium low"
FAN_MEDIUM_HIGH = "medium high"

MAX_ERRORS = 2

TARGET_TEMPERATURE_STEP = 1

UPDATE_INTERVAL = 60
MAX_EXPECTED_RESPONSE_TIME_INTERVAL = UPDATE_INTERVAL * 2

# ── Extended Protocol Properties ─────────────────────────────────────────────
# These property names are requested from the device in addition to the
# standard greeclimate Props enum.  Not all devices/firmware versions support
# all of them; the coordinator treats missing/None values gracefully.

# Compressor frequency (Hz); 0 = compressor off, >0 = running.
PROP_COMP_FREQ = "CompFreq"

# Indoor coil (evaporator) temperature.  Uses the same +40 offset convention
# as TemSen on firmware < 4.0.
PROP_INDOOR_COIL_TEMP = "TemInlet"

# Outdoor coil (condenser) temperature.  Same offset rules.
PROP_OUTDOOR_COIL_TEMP = "TemOutlet"

# Temperature offset used by firmware versions < 4.0.
TEMP_OFFSET = 40

# Complete list of extended property names to request.
EXTENDED_PROPERTIES: list[str] = [
    PROP_COMP_FREQ,
    PROP_INDOOR_COIL_TEMP,
    PROP_OUTDOOR_COIL_TEMP,
]

# Service name
SERVICE_FORCE_FAN_OFF = "force_fan_off"
