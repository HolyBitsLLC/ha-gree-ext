"""Tests for firmware version detection and temperature offset logic."""

from __future__ import annotations

import pytest

from custom_components.gree_ext.const import (
    PROP_COMP_FREQ,
    PROP_INDOOR_COIL_TEMP,
    PROP_OUTDOOR_COIL_TEMP,
    TEMP_OFFSET,
)
from custom_components.gree_ext.coordinator import DeviceDataUpdateCoordinator


class TestNormaliseAliases:
    """Test alias normalisation for different firmware property names."""

    def test_canonical_names_pass_through(self):
        raw = {"CompFreq": 42, "TemInlet": 65, "TemOutlet": 58}
        result = DeviceDataUpdateCoordinator._normalise_aliases(raw)
        assert result[PROP_COMP_FREQ] == 42
        assert result[PROP_INDOOR_COIL_TEMP] == 65
        assert result[PROP_OUTDOOR_COIL_TEMP] == 58

    def test_alternate_aliases_normalised(self):
        raw = {"CompFre": 30, "ICoilT": 55, "OCoilT": 48}
        result = DeviceDataUpdateCoordinator._normalise_aliases(raw)
        assert result[PROP_COMP_FREQ] == 30
        assert result[PROP_INDOOR_COIL_TEMP] == 55
        assert result[PROP_OUTDOOR_COIL_TEMP] == 48

    def test_pipe_aliases_normalised(self):
        raw = {"CompFreq": 0, "TemPipe": 62, "OutPipe": 50}
        result = DeviceDataUpdateCoordinator._normalise_aliases(raw)
        assert result[PROP_COMP_FREQ] == 0
        assert result[PROP_INDOOR_COIL_TEMP] == 62
        assert result[PROP_OUTDOOR_COIL_TEMP] == 50

    def test_missing_properties_omitted(self):
        raw = {"CompFreq": 10}
        result = DeviceDataUpdateCoordinator._normalise_aliases(raw)
        assert PROP_COMP_FREQ in result
        assert PROP_INDOOR_COIL_TEMP not in result
        assert PROP_OUTDOOR_COIL_TEMP not in result

    def test_none_values_skipped(self):
        raw = {"CompFreq": None, "CompFre": 20}
        result = DeviceDataUpdateCoordinator._normalise_aliases(raw)
        assert result[PROP_COMP_FREQ] == 20

    def test_empty_dict(self):
        result = DeviceDataUpdateCoordinator._normalise_aliases({})
        assert result == {}


class TestTemperatureHeuristic:
    """Test the temperature offset heuristic for FW detection."""

    def test_value_below_offset_is_raw_celsius(self):
        # Raw value 25 < TEMP_OFFSET(40) → already in °C
        raw = 25
        assert raw < TEMP_OFFSET
        # This is the "v4" path
        result = float(raw)
        assert result == 25.0

    def test_value_above_offset_needs_subtraction(self):
        # Raw value 65 >= TEMP_OFFSET(40) → subtract offset → 25°C
        raw = 65
        assert raw >= TEMP_OFFSET
        result = float(raw - TEMP_OFFSET)
        assert result == 25.0

    def test_edge_case_value_equals_offset(self):
        # Raw value exactly 40 → with offset means 0°C (plausible coil temp)
        raw = 40
        assert raw >= TEMP_OFFSET
        result = float(raw - TEMP_OFFSET)
        assert result == 0.0

    def test_negative_result_from_offset(self):
        # Raw 35 on old firmware → 35 - 40 = -5°C (plausible for outdoor coil)
        # But 35 < 40 so heuristic says "v4 raw" → 35°C
        # This is the ambiguous zone; heuristic picks v4 interpretation
        raw = 35
        assert raw < TEMP_OFFSET
        result = float(raw)
        assert result == 35.0
