"""
pipeline.py

Strain Gauge Data Processing Pipeline
Formula Racing SAE — UBC

Reads raw ADC counts from CSV (logged by AIM data logger),
processes through a modular pipeline:

1. CANParser      — reads CSV, extracts raw ADC counts per channel
2. SensorCalibrator — converts ADC counts → voltage → force (Newtons)
3. DataFilter      — applies moving average filter to smooth noise
4. DataVisualizer  — plots force vs time (in visualizer.py)

Each class has one responsibility. Easy to test, easy to modify.
"""

import numpy as np
import csv

# ─────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────

ADC_RESOLUTION   = 4096    # 12-bit ADC: 0 to 4095 counts
VREF             = 3.3     # STM32 reference voltage (volts)
OFFSET_VOLTAGE   = 1.65    # Amplifier output at zero load (midpoint of 3.3V)
SENSITIVITY      = 500.0   # Newtons per volt — determined during calibration
FILTER_WINDOW    = 10      # Moving average window size (samples)
NUM_CHANNELS     = 4       # FL, FR, RL, RR

CHANNEL_NAMES = ["Front Left", "Front Right", "Rear Left", "Rear Right"]


# ─────────────────────────────────────────────────────────
# CLASS 1 — CAN PARSER
# Reads CSV exported from AIM data logger
# Extracts timestamps and raw ADC counts for each channel
# ─────────────────────────────────────────────────────────

class CANParser:
    """
    Reads CSV file exported from AIM data logger.

    The AIM logger records CAN messages and exports them as CSV.
    Each row is one CAN message (one 100Hz sample).
    Columns: timestamp, ch0_high, ch0_low, ch1_high, ch1_low, ...

    Reassembles high/low byte pairs back into uint16 ADC counts.
    """

    def __init__(self, filepath):
        """
        Parameters
        ----------
        filepath : str
            Path to CSV file exported from AIM logger
        """
        self.filepath   = filepath
        self.timestamps = None   # numpy array of timestamps (seconds)
        self.raw_adc    = None   # numpy array shape (num_samples, NUM_CHANNELS)

    def parse(self):
        """
        Read CSV and reconstruct ADC values from high/low byte pairs.

        CSV format expected:
            timestamp, ch0_H, ch0_L, ch1_H, ch1_L, ch2_H, ch2_L, ch3_H, ch3_L

        Returns
        -------
        self : CANParser
            Returns self so calls can be chained
        """
        timestamps = []
        raw_adc    = []

        with open(self.filepath, 'r') as f:
            reader = csv.reader(f)
            next(reader)  # skip header row

            for row in reader:
                timestamp = float(row[0])

                # Reassemble each channel from high byte and low byte
                # CAN packed: high byte first, low byte second
                # Reverse: (high << 8) | low = original uint16 ADC count
                channels = []
                for ch in range(NUM_CHANNELS):
                    high_byte = int(row[1 + ch * 2])
                    low_byte  = int(row[2 + ch * 2])
                    adc_count = (high_byte << 8) | low_byte
                    channels.append(adc_count)

                timestamps.append(timestamp)
                raw_adc.append(channels)

        # Convert to numpy arrays for fast vectorized operations
        self.timestamps = np.array(timestamps)             # shape: (N,)
        self.raw_adc    = np.array(raw_adc, dtype=float)  # shape: (N, 4)

        print(f"Parsed {len(self.timestamps)} samples from {self.filepath}")
        return self


# ─────────────────────────────────────────────────────────
# CLASS 2 — SENSOR CALIBRATOR
# Converts raw ADC counts → voltage → force (Newtons)
#
# Step 1: ADC count → voltage
#         voltage = (adc_count / ADC_RESOLUTION) × VREF
#
# Step 2: Remove zero-load offset
#         delta_voltage = voltage - OFFSET_VOLTAGE
#         (amplifier outputs 1.65V midpoint at zero load)
#
# Step 3: Voltage → Force
#         force = delta_voltage × SENSITIVITY
#         (sensitivity determined by applying known weights during calibration)
# ─────────────────────────────────────────────────────────

class SensorCalibrator:
    """
    Converts raw ADC counts to force in Newtons.

    Uses a linear calibration model:
        force = (adc_voltage - offset) × sensitivity

    Calibration constants determined experimentally:
    known weights were applied to suspension and ADC output recorded.
    Linear regression on (weight, voltage) pairs gave sensitivity and offset.
    """

    def __init__(self, sensitivity=SENSITIVITY, offset_voltage=OFFSET_VOLTAGE,
                 adc_resolution=ADC_RESOLUTION, vref=VREF):
        """
        Parameters
        ----------
        sensitivity    : float — Newtons per volt
        offset_voltage : float — amplifier output at zero load (volts)
        adc_resolution : int   — ADC full scale count (4096 for 12-bit)
        vref           : float — reference voltage (volts)
        """
        self.sensitivity    = sensitivity
        self.offset_voltage = offset_voltage
        self.adc_resolution = adc_resolution
        self.vref           = vref

    def counts_to_voltage(self, adc_counts):
        """
        Convert ADC counts to voltage.

        Parameters
        ----------
        adc_counts : np.ndarray — raw ADC values (0 to 4095)

        Returns
        -------
        np.ndarray — voltage in volts
        """
        return (adc_counts / self.adc_resolution) * self.vref

    def voltage_to_force(self, voltage):
        """
        Convert voltage to force in Newtons.

        Removes zero-load offset then applies sensitivity scaling.

        Parameters
        ----------
        voltage : np.ndarray — voltage in volts

        Returns
        -------
        np.ndarray — force in Newtons
        """
        delta_voltage = voltage - self.offset_voltage
        return delta_voltage * self.sensitivity

    def calibrate(self, raw_adc):
        """
        Full calibration: ADC counts → voltage → force.

        Parameters
        ----------
        raw_adc : np.ndarray shape (N, 4) — raw ADC counts

        Returns
        -------
        np.ndarray shape (N, 4) — force in Newtons for each channel
        """
        voltage = self.counts_to_voltage(raw_adc)
        force   = self.voltage_to_force(voltage)
        return force


# ─────────────────────────────────────────────────────────
# CLASS 3 — DATA FILTER
# Moving average filter — smooths high frequency noise
#
# For each sample, replaces the value with the average
# of the surrounding window of samples.
#
# This is a digital low pass filter — slow suspension changes
# pass through, fast electrical noise gets averaged out.
# ─────────────────────────────────────────────────────────

class DataFilter:
    """
    Applies moving average filter to force data.

    Moving average is a simple digital low pass filter.
    Replaces each sample with the mean of the surrounding window.

    Uses numpy.convolve with a uniform kernel — efficient vectorized
    operation instead of a Python loop.
    """

    def __init__(self, window_size=FILTER_WINDOW):
        """
        Parameters
        ----------
        window_size : int — number of samples to average over
                           larger = more smoothing, more lag
        """
        self.window_size = window_size

    def apply(self, force_data):
        """
        Apply moving average filter to all channels.

        Parameters
        ----------
        force_data : np.ndarray shape (N, 4) — force in Newtons

        Returns
        -------
        np.ndarray shape (N, 4) — filtered force data
        """
        num_samples, num_channels = force_data.shape
        filtered = np.zeros_like(force_data)

        # Uniform kernel — every sample in window gets equal weight
        # Example window_size=5: kernel = [0.2, 0.2, 0.2, 0.2, 0.2]
        kernel = np.ones(self.window_size) / self.window_size

        for ch in range(num_channels):
            # np.convolve slides the kernel across the signal
            # 'same' mode: output is same length as input
            filtered[:, ch] = np.convolve(force_data[:, ch], kernel, mode='same')

        return filtered


# ─────────────────────────────────────────────────────────
# CLASS 4 — DATA PROCESSOR
# Orchestrates the full pipeline:
# parse → calibrate → filter → return processed data
# ─────────────────────────────────────────────────────────

class DataProcessor:
    """
    Orchestrates the full processing pipeline.

    Combines CANParser, SensorCalibrator, and DataFilter
    into a single run() call.

    Stores results as attributes for downstream use
    (visualization, export, analysis).
    """

    def __init__(self, filepath, window_size=FILTER_WINDOW):
        """
        Parameters
        ----------
        filepath    : str — path to AIM CSV file
        window_size : int — moving average window size
        """
        self.parser     = CANParser(filepath)
        self.calibrator = SensorCalibrator()
        self.filter     = DataFilter(window_size)

        # Results stored after run()
        self.timestamps     = None   # (N,) timestamps in seconds
        self.raw_adc        = None   # (N, 4) raw ADC counts
        self.force_raw      = None   # (N, 4) calibrated but unfiltered force
        self.force_filtered = None   # (N, 4) calibrated and filtered force

    def run(self):
        """
        Execute full pipeline: parse → calibrate → filter.

        Returns
        -------
        self : DataProcessor
            Returns self for method chaining
        """
        # Step 1: Parse CSV
        self.parser.parse()
        self.timestamps = self.parser.timestamps
        self.raw_adc    = self.parser.raw_adc

        # Step 2: Calibrate — ADC counts to force
        self.force_raw = self.calibrator.calibrate(self.raw_adc)

        # Step 3: Filter — smooth noise
        self.force_filtered = self.filter.apply(self.force_raw)

        print(f"Pipeline complete — {len(self.timestamps)} samples processed")
        return self

    def summary(self):
        """
        Print summary statistics for each channel.
        """
        if self.force_filtered is None:
            print("Run pipeline first with .run()")
            return

        print("\n── Suspension Load Summary ──")
        for ch, name in enumerate(CHANNEL_NAMES):
            data = self.force_filtered[:, ch]
            print(f"{name:12s} | "
                  f"Mean: {np.mean(data):8.1f} N | "
                  f"Max:  {np.max(data):8.1f} N | "
                  f"Min:  {np.min(data):8.1f} N | "
                  f"Std:  {np.std(data):6.1f} N")


# ─────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run full pipeline on a data file
    processor = DataProcessor("data/run_001.csv", window_size=10)
    processor.run()
    processor.summary()
