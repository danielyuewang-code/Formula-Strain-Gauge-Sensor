# Project Index - Formula Strain Gauge Sensor

## Project Overview
**Project Name:** Formula Strain Gauge Sensor  

---

## Repository Structure

```
Formula-Strain-Gauge-Sensor/
├── README.md                      # Project overview and getting started guide
├── PROJECT_INDEX.md               # This file - detailed project index
├── .gitignore                     # Git ignore rules
│
├── biggie/                        # Full-featured MCU variant
│   ├── biggie.PrjPcb             # Main Altium project file
│   ├── MCU.SchDoc                # Schematic - MCU, signal conditioning, power
│   └── __Previews/               # Altium preview files
│       └── MCU.SchDocPreview
│
├── smol/                          # Compact sensor variant
│   ├── smol.PrjPcb               # Main Altium project file
│   ├── root.SchDoc               # Schematic design
│   ├── smol.PcbDoc               # PCB layout
│   ├── __Previews/               # Altium preview files
│   │   └── root.SchDocPreview
│   └── History/                  # Altium version history
│
└── docs/                          # Documentation
    └── Design_Folder.md          # Design documentation
```

---

## Design Variants

### 1. Biggie (Full-Featured Board)
**Location:** `/biggie`  
**Description:** Complete microcontroller-based data acquisition system

**Key Files:**
- `biggie.PrjPcb` - Altium project container
- `MCU.SchDoc` - Main schematic with MCU and signal conditioning

---

### 2. Smol (Compact Board)
**Location:** `/smol`  
**Description:** Space-optimized sensor board for constrained installations

**Key Files:**
- `smol.PrjPcb` - Altium project container
- `root.SchDoc` - Schematic design
- `smol.PcbDoc` - PCB layout

---

## Quick Reference

### Opening Projects
1. Navigate to desired variant folder (`biggie/` or `smol/`)
2. Open the `.PrjPcb` file in Altium Designer
3. Access schematics and PCB files from the project panel

### Documentation
- Design decisions and specifications: `/docs/Design_Folder.md`
- General project info: `README.md`
- Project navigation: This file (`PROJECT_INDEX.md`)
