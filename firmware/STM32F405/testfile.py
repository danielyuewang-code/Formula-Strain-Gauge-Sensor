"""
test_pipeline.py

Unit tests for strain gauge data processing pipeline.
Tests each class independently to validate correct behavior.

Run with:
    pytest test_pipeline.py -v
"""

import numpy as np
import pytest
import csv
import os
import tempfile

from pipeline import (
    CANParser,
    SensorCalibrator,
    DataFilter,
    DataProcessor,
    ADC_RESOLUTION,
    VREF,
    OFFSET_VOLTAGE,
    SENSITIVITY,
)


# ─────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────

def make_test_csv(rows):
    """
    Write a temporary CSV file with given rows.
    Returns the filepath.
    Used to test CANParser without needing a real AIM export.

    Format: timestamp, ch0_H, ch0_L, ch1_H, ch1_L, ch2_H, ch2_L, ch3_H, ch3_L
    """
    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.csv', delete=False, newline=''
    )
    writer = csv.writer(tmp)
    writer.writerow(["timestamp", "ch0_H", "ch0_L",
                     "ch1_H", "ch1_L", "ch2_H", "ch2_L",
                     "ch3_H", "ch3_L"])
    writer.writerows(rows)
    tmp.close()
    return tmp.name


def adc_to_bytes(adc_value):
    """
    Split a uint16 ADC value into high byte and low byte.
    Mirrors what the STM32 firmware does before CAN transmission.
    """
    high = (adc_value >> 8) & 0xFF
    low  = adc_value & 0xFF
    return high, low


# ─────────────────────────────────────────────────────────
# CAN PARSER TESTS
# ─────────────────────────────────────────────────────────

class TestCANParser:

    def test_parse_single_row(self):
        """
        Parser correctly reconstructs ADC values from high/low bytes.
        We know the ADC value we packed — verify we get it back.
        """
        adc_values = [2048, 1024, 3000, 500]
        row = [0.01]  # timestamp
        for val in adc_values:
            h, l = adc_to_bytes(val)
            row += [h, l]

        filepath = make_test_csv([row])
        try:
            parser = CANParser(filepath)
            parser.parse()

            assert parser.raw_adc.shape == (1, 4)
            for ch, expected in enumerate(adc_values):
                assert parser.raw_adc[0, ch] == expected, \
                    f"Channel {ch}: expected {expected}, got {parser.raw_adc[0, ch]}"
        finally:
            os.unlink(filepath)

    def test_parse_multiple_rows(self):
        """
        Parser reads all rows and produces correct number of samples.
        """
        num_rows = 5
        rows = []
        for i in range(num_rows):
            row = [i * 0.01]
            for ch in range(4):
                h, l = adc_to_bytes(1000 + i)
                row += [h, l]
            rows.append(row)

        filepath = make_test_csv(rows)
        try:
            parser = CANParser(filepath)
            parser.parse()

            assert len(parser.timestamps) == num_rows
            assert parser.raw_adc.shape == (num_rows, 4)
        finally:
            os.unlink(filepath)

    def test_timestamps_correct(self):
        """
        Timestamps are parsed correctly and in order.
        """
        timestamps = [0.0, 0.01, 0.02]
        rows = []
        for t in timestamps:
            row = [t] + [0x08, 0x00] * 4  # ADC = 2048 on all channels
            rows.append(row)

        filepath = make_test_csv(rows)
        try:
            parser = CANParser(filepath)
            parser.parse()
            np.testing.assert_array_almost_equal(parser.timestamps, timestamps)
        finally:
            os.unlink(filepath)

    def test_zero_adc_value(self):
        """
        Edge case: ADC reads zero (both bytes are 0x00).
        """
        row = [0.0] + [0x00, 0x00] * 4
        filepath = make_test_csv([row])
        try:
            parser = CANParser(filepath)
            parser.parse()
            assert np.all(parser.raw_adc == 0)
        finally:
            os.unlink(filepath)

    def test_max_adc_value(self):
        """
        Edge case: ADC reads max value 4095 (12-bit full scale).
        High byte = 0x0F, low byte = 0xFF
        """
        h, l = adc_to_bytes(4095)
        row = [0.0] + [h, l] * 4
        filepath = make_test_csv([row])
        try:
            parser = CANParser(filepath)
            parser.parse()
            assert np.all(parser.raw_adc == 4095)
        finally:
            os.unlink(filepath)


# ─────────────────────────────────────────────────────────
# SENSOR CALIBRATOR TESTS
# ─────────────────────────────────────────────────────────

class TestSensorCalibrator:

    def setup_method(self):
        """Create a fresh calibrator before each test."""
        self.cal = SensorCalibrator()

    def test_midpoint_adc_gives_offset_voltage(self):
        """
        ADC midpoint (2048) should give exactly OFFSET_VOLTAGE (1.65V).
        At zero load the amplifier outputs the midpoint of the supply.
        """
        adc = np.array([[2048.0, 2048.0, 2048.0, 2048.0]])
        voltage = self.cal.counts_to_voltage(adc)
        expected = (2048 / ADC_RESOLUTION) * VREF
        np.testing.assert_array_almost_equal(voltage, expected, decimal=4)

    def test_zero_adc_gives_zero_voltage(self):
        """ADC count of 0 should give 0V."""
        adc = np.array([[0.0, 0.0, 0.0, 0.0]])
        voltage = self.cal.counts_to_voltage(adc)
        np.testing.assert_array_almost_equal(voltage, 0.0)

    def test_max_adc_gives_vref(self):
        """ADC count of 4095 should give approximately VREF (3.3V)."""
        adc = np.array([[4095.0, 4095.0, 4095.0, 4095.0]])
        voltage = self.cal.counts_to_voltage(adc)
        expected = (4095 / ADC_RESOLUTION) * VREF
        np.testing.assert_array_almost_equal(voltage, expected, decimal=3)

    def test_zero_load_gives_zero_force(self):
        """
        At zero load the amplifier outputs OFFSET_VOLTAGE (1.65V).
        Calibration should give 0 Newtons at this voltage.
        """
        voltage = np.array([[OFFSET_VOLTAGE] * 4])
        force = self.cal.voltage_to_force(voltage)
        np.testing.assert_array_almost_equal(force, 0.0, decimal=5)

    def test_known_force_value(self):
        """
        Verify calibration math with a known example.
        If voltage = 1.85V, delta = 1.85 - 1.65 = 0.2V
        Force = 0.2 × 500 = 100 N
        """
        voltage = np.array([[1.85, 1.85, 1.85, 1.85]])
        force = self.cal.voltage_to_force(voltage)
        expected = (1.85 - OFFSET_VOLTAGE) * SENSITIVITY
        np.testing.assert_array_almost_equal(force, expected, decimal=3)

    def test_negative_force(self):
        """
        Voltage below offset gives negative force (tension vs compression).
        """
        voltage = np.array([[1.45, 1.45, 1.45, 1.45]])
        force = self.cal.voltage_to_force(voltage)
        assert np.all(force < 0), "Force should be negative below offset voltage"

    def test_calibrate_full_pipeline(self):
        """
        End to end: raw ADC in, force in Newtons out.
        Use midpoint ADC (2048) — should give approximately 0 Newtons.
        """
        adc = np.array([[2048.0] * 4])
        force = self.cal.calibrate(adc)
        # 2048 counts → 1.6496V → delta ≈ -0.0004V → force ≈ -0.2N (tiny rounding)
        np.testing.assert_array_almost_equal(force, 0.0, decimal=0)

    def test_output_shape_preserved(self):
        """Output shape must match input shape."""
        adc = np.random.randint(0, 4096, size=(100, 4)).astype(float)
        force = self.cal.calibrate(adc)
        assert force.shape == adc.shape


# ─────────────────────────────────────────────────────────
# DATA FILTER TESTS
# ─────────────────────────────────────────────────────────

class TestDataFilter:

    def setup_method(self):
        """Create a fresh filter before each test."""
        self.filt = DataFilter(window_size=5)

    def test_constant_signal_unchanged(self):
        """
        A perfectly constant signal should pass through the filter unchanged.
        Average of identical values = same value.
        """
        # 50 samples, all channels at 100.0 N
        data = np.ones((50, 4)) * 100.0
        filtered = self.filt.apply(data)

        # Middle section should be exactly 100.0 (edges affected by boundary)
        np.testing.assert_array_almost_equal(
            filtered[5:-5, :], 100.0, decimal=3
        )

    def test_output_shape_preserved(self):
        """Filter output must be same shape as input."""
        data = np.random.randn(200, 4)
        filtered = self.filt.apply(data)
        assert filtered.shape == data.shape

    def test_spike_gets_attenuated(self):
        """
        A single noise spike should be reduced by the filter.
        The spike's peak value in the filtered output should be
        smaller than in the raw data.
        """
        data = np.zeros((50, 4))
        data[25, 0] = 1000.0   # large spike on channel 0 at sample 25

        filtered = self.filt.apply(data)

        # Spike should be attenuated — filtered peak < raw peak
        assert filtered[25, 0] < 1000.0, "Spike should be attenuated"

        # With window=5, spike gets averaged with 4 zeros: 1000/5 = 200
        assert abs(filtered[25, 0] - 200.0) < 1.0

    def test_larger_window_more_smoothing(self):
        """
        Larger window = more aggressive noise reduction.
        A spike should be attenuated more with a larger window.
        """
        data = np.zeros((100, 4))
        data[50, 0] = 1000.0

        small_window = DataFilter(window_size=3).apply(data)
        large_window = DataFilter(window_size=11).apply(data)

        # Larger window should reduce spike more
        assert large_window[50, 0] < small_window[50, 0]

    def test_all_channels_filtered(self):
        """Filter is applied to all 4 channels, not just one."""
        data = np.zeros((50, 4))
        for ch in range(4):
            data[25, ch] = 500.0   # spike on every channel

        filtered = self.filt.apply(data)

        for ch in range(4):
            assert filtered[25, ch] < 500.0, \
                f"Channel {ch} spike should be attenuated"

    def test_window_size_one_is_passthrough(self):
        """
        Window size of 1 means average of 1 sample = no filtering.
        Output should equal input exactly.
        """
        filt = DataFilter(window_size=1)
        data = np.random.randn(50, 4)
        filtered = filt.apply(data)
        np.testing.assert_array_almost_equal(filtered, data)


# ─────────────────────────────────────────────────────────
# DATA PROCESSOR INTEGRATION TEST
# Tests the full pipeline end to end
# ─────────────────────────────────────────────────────────

class TestDataProcessor:

    def make_processor(self, num_samples=50):
        """
        Create a DataProcessor with a temporary CSV file.
        All channels set to ADC midpoint (2048) = zero force.
        """
        rows = []
        for i in range(num_samples):
            row = [i * 0.01]
            for ch in range(4):
                h, l = adc_to_bytes(2048)
                row += [h, l]
            rows.append(row)

        filepath = make_test_csv(rows)
        return DataProcessor(filepath), filepath

    def test_pipeline_runs_without_error(self):
        """Full pipeline runs from CSV to filtered force without crashing."""
        processor, filepath = self.make_processor()
        try:
            processor.run()
        finally:
            os.unlink(filepath)

    def test_output_shapes_correct(self):
        """All output arrays have correct shapes after run()."""
        num_samples = 50
        processor, filepath = self.make_processor(num_samples)
        try:
            processor.run()
            assert processor.timestamps.shape     == (num_samples,)
            assert processor.raw_adc.shape        == (num_samples, 4)
            assert processor.force_raw.shape      == (num_samples, 4)
            assert processor.force_filtered.shape == (num_samples, 4)
        finally:
            os.unlink(filepath)

    def test_midpoint_adc_gives_near_zero_force(self):
        """
        ADC midpoint (2048) at all channels should give approximately 0N force.
        Verifies calibration and pipeline are connected correctly.
        """
        processor, filepath = self.make_processor()
        try:
            processor.run()
            # Force should be very close to zero for midpoint ADC input
            np.testing.assert_array_almost_equal(
                processor.force_raw, 0.0, decimal=0
            )
        finally:
            os.unlink(filepath)
