# Open-Source Potentiostat

**A fully open-source, low-cost potentiostat for cyclic voltammetry and general electrochemical characterization, built for under $200 as an alternative to commercial instruments.**

> **Status: Active development.** Not yet complete or ready for use. See [Build Progress](#build-progress) below for current status.

---

## Overview

This project is an attempt to build a fully open - hardware, firmware, and software - potentiostat capable of electrochemical characterization, at a fraction of the cost of a comercial instrument.

The instrument is built around a three-electrode electrochemical cell, using a potentiostatic control loop to maintain a precise potential and a switchable-gain transimpedance amplifier to measure the resulting current. A Teensy 4.1 handles low-level control and data acquisition, with a Python-based GUI for control and data analysis.

Once complete, the instrument will be validated against published cyclic voltammetry data.

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
├── firmware/                
│   └── firmware.ino         
├── hardware/                
│   ├── schematic/           
│   └── simulation/          
├── software/                
│   ├── app.py
│   ├── main.py
│   └── requirements.txt
├── docs/                    
│   ├── BOM.csv
│   ├── circuit_design_notes.md
│   └── simulation_notes.md
├── LICENSE_hardware
├── LICENSE_software
└── README.md
```
## Acknowledgments

This project draws inspiration from **CheapStat**, an open-source, "do-it-yourself" potentiostat originally designed by Aaron Rowe, Andrew Bonham, Michael Zimmer, Kevin Plaxco and colleagues at UC Santa Barbara, which demonstrated that a fully open, low-cost potentiostat could support real analytical and educational applications.

- Rowe, A.A., Bonham, A.J., White, R.J., et al. (2011). ["CheapStat: An Open-Source, 'Do-It-Yourself' Potentiostat for Analytical and Educational Applications."](https://doi.org/10.1371/journal.pone.0023783) *PLOS ONE*.

## License

- Hardware design files: [CERN-OHL-S v2](https://ohwr.org/cern_ohl_s_v2.txt)
- Software and firmware: MIT

## Author

**Samuel O'Blenes**
GitHub: [@samueloblenes](https://github.com/samueloblenes)

---

*This is a work in progress - design files, firmware, and documentation will be updated as the project develops. Feedback and suggestions are welcome via GitHub Issues.*
