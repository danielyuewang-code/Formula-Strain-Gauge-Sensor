# Formula Strain Gauge Sensor
> PCB designs for measuring axial forces on suspension arms in Formula SAE racing applications

## Overview
This repository contains the Altium Designer PCB projects for strain gauge sensor systems designed to measure axial forces on suspension arms in formula racing vehicles. The project includes two design variants optimized for different size and performance requirements.

## Project Structure
### `/CIU` - Full-Featured MCU Board
The larger variant featuring a complete microcontroller solution for data acquisition and processing.
- **biggie.PrjPcb** - Main Altium project file
- **MCU.SchDoc** - Schematic design with MCU, signal conditioning, and power management

### `/smol` - Compact Sensor Board
The compact variant optimized for space-constrained installations.
- **smol.PrjPcb** - Main Altium project file
- **root.SchDoc** - Schematic design
- **smol.PcbDoc** - PCB layout

### `/docs`
Project documentation and design notes.

## Features
- Strain gauge signal conditioning and amplification
- Microcontroller-based data acquisition
- Axial force measurement capabilities
- Multiple size variants for different installation requirements
- Designed for harsh racing environments

## Hardware Requirements
- Altium Designer (for viewing/editing design files)
- Strain gauge sensors (specifications TBD)
- Power supply requirements (specifications TBD)

## Getting Started
1. Clone this repository
2. Open the desired project (.PrjPcb) in Altium Designer
3. Review the schematic and PCB layout files
4. Generate manufacturing outputs as needed

## Design Variants
- **Biggie** - Full-featured board with integrated MCU for standalone operation
- **Smol** - Amplifier board feeding signals
