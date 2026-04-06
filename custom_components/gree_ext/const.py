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

# Firmware version detection threshold.  greeclimate uses a heuristic:
# if TemSen (room temp sensor) reports a value < TEMP_OFFSET the firmware
# is "new style" (>= 4.0) and values are already in °C.  Otherwise the
# raw value has a +40 offset.  We apply the same heuristic to our coil
# temperature properties.  A coil temp below this threshold is certainly
# already in °C; above it, we subtract the offset.
#
# Note: greeclimate may also set device.version = "4.0" dynamically after
# the first TemSen read.  We honour that too as a secondary signal.
FW_V4_VERSION_PREFIX = "4"

# Complete list of extended property names to request.
EXTENDED_PROPERTIES: list[str] = []

# Some firmware variants use different property names for the same data.
# We request ALL known variants; the device will simply ignore names it
# doesn't recognise and omit them from the response.

# Compressor frequency — known aliases across firmware families.
PROP_COMP_FREQ_ALIASES: list[str] = ["CompFreq", "CompFre"]

# Indoor coil (evaporator) temperature — known aliases.
PROP_INDOOR_COIL_ALIASES: list[str] = ["TemInlet", "ICoilT", "TemPipe"]

# Outdoor coil (condenser) temperature — known aliases.
PROP_OUTDOOR_COIL_ALIASES: list[str] = ["TemOutlet", "OCoilT", "OutPipe"]

# Build the master request list from all alias groups.
EXTENDED_PROPERTIES = (
    PROP_COMP_FREQ_ALIASES
    + PROP_INDOOR_COIL_ALIASES
    + PROP_OUTDOOR_COIL_ALIASES
)

# Service name
SERVICE_FORCE_FAN_OFF = "force_fan_off"
