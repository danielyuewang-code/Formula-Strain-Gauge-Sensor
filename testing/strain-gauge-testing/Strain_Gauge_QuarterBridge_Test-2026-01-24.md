# Strain Gauge Quarter-Bridge Test

Daniel Wang  
2026-01-24  

---

## 1. Objective
Verify quarter-bridge strain gauge readings, op-amp amplification, and ESP32 ADC response to applied strain.

---

## 2. Test Setup

### 2.1 Hardware
- Strain Gauge: 350 Ω
- Bridge Configuration: Quarter-bridge
- Bridge Resistors: 3 × 100 Ω, 1 × 51 Ω (didn't have 350 Ω resistors on hand)
- Excitation Voltage: 3.3 V
- Op-Amp: MCP6002 (single op-amp, non-inverting configuration)
- Gain: ~100 (100 kΩ / 1 kΩ)
- MCU: ESP32-WROOM-32D
- ADC Pin: GPIO32

**See Breakboard Setup:**
![Breadboard setup](images/breadboard-setup.jpg)

### 2.2 Signal Chain
```text
Strain Gauge (350 Ω)
→ Wheatstone Quarter Bridge (~351 Ω)
→ Op-Amp (Gain ≈ 100)
→ ESP32 ADC (GPIO32)
→ Serial Monitor
```

---

## 3. Testing

### 3.1 Testing Each Layer

#### Wheatstone Quarter Bridge
- Measured bridge output with multimeter
    - Output (no strain): fluctuating ~0.1 mV
    - When manually bending strain gauge with hands: ~1 mV

#### Op-Amp
- Output (no strain): ~2.4
- Amplified output when manually bending with hands: ~100 mV (expected 100x gain)

Note: A mid-supply bias (1.65 V) was not implemented in this test; the op-amp reference was tied to ground. As a result, the DC operating point was undefined, and an output offset of ~2.4 V was observed. Input impedance mismatch between the bridge and op-amp inputs likely contributed to this offset. Future designs should include buffer op-amps prior to the gain stage.

### 3.2 ESP32 Reading
- Op-amp connected to ADC pin GPIO32
- Serial moniter on Arduino IDE

#### MCU Sanity Check
- LED blink test and ADC read test
**Note for our ESP, there was no auto-reboot, BOOT button must be held down during upload.

#### ADC Test Code
Serial moniter baud rate: 115200
```cpp
void setup() {
  Serial.begin(115200);
}

void loop() {
  int raw = analogRead(36);
  Serial.println(raw);
  delay(500);
}
```

#### Voltage Conversion Code
```cpp
void setup() {
  Serial.begin(115200);
}

void loop() {
  int raw = analogRead(36);
  float voltage = (raw / 4095.0) * 3.3;
  Serial.print("ADC: ");
  Serial.print(raw);
  Serial.print(" Voltage: ");
  Serial.println(voltage, 3);
  delay(500);
}
```
From bending the strain gauge, max volatage readings from 3.3 V down to 0.4 V.

--- 

## 4. Next Steps
- waterjetted steel test piece (200x20x1.5 mm) to hang weights from and get proper calibration curve on serial moniter
- add the two op amps to balance current
