# Open-Source Potentiostat

**A fully open-source, low-cost potentiostat for cyclic voltammetry and general electrochemical characterization, built for under $200 as an alternative to commercial instruments costing $5,000+.**

> 🚧 **Status: Active development.** Not yet complete or ready for use. See [Build Progress](#build-progress) below for current status.

---

## Overview

Commercial potentiostats are expensive, putting them out of reach for many student labs, hobbyists, and independent researchers. This project is an attempt to build a fully open - hardware, firmware, and software - potentiostat capable of electrochemical characterization, at a fraction of the cost.

The instrument is built around a three-electrode electrochemical cell, using a potentiostatic control loop to maintain a precise potential at the working electrode and a switchable-gain transimpedance amplifier to measure the resulting current. A Teensy 4.1 handles low-level control and data acquisition, with a Python-based GUI for control and data analysis.

Once complete, the instrument will be validated against published cyclic voltammetry data.

## Planned Capabilities

- Cyclic voltammetry (CV)
- Linear sweep voltammetry (LSV)
- Chronoamperometry (CA)
- Open circuit potential (OCP) measurement

## Build Progress

- [x] Circuit design
- [x] SPICE simulation
- [x] Preliminary firmware
- [x] Breadboard prototype
- [ ] Breadboard testing & debugging *(in progress)*
- [ ] Electrode holder & electrode design
- [ ] Enclosure design
- [ ] Final PCB layout
- [ ] Full assembly & validation

## Repository Structure
```
open-source-potentiostat/
├── hardware/
│   ├── schematics/          # KiCad schematic files (in progress)
│   └── simulation/          # LTspice simulation files and notes
├── docs/
│   ├── bom/                 # Bill of materials (in progress)
│   ├── circuit_design_notes.md
│   └── simulation_notes.md
└── README.md
```
## License

- Hardware design files: [CERN-OHL-S v2](https://ohwr.org/cern_ohl_s_v2.txt)
- Software and firmware: MIT

## Author

**Samuel O'Blenes**
GitHub: [@samueloblenes](https://github.com/samueloblenes)

---

*This is a work in progress - design files, firmware, and documentation will be updated as the project develops. Feedback and suggestions are welcome via GitHub Issues.*
