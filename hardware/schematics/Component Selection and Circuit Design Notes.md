# Component Selection and Circuit Design

## Overview
This document describes the circuit design of the open-source potentiostat, detailing the selection criteria and reasoning for each major component and subsystem. 
The design priorities are affordability, reproducibility, and sufficient performance for cyclic voltammetry and corrosion characterization of Cu and W in semiconductor-relevant electrolytes.

## Design requirements and constraints

### Functional requirements
CV - Cyclic Voltammetry:
- The working electrode potential is swept linearly from an initial value to a final value, then reversed back to the initial value. Current at the working electrode is measured continuously as a function of applied potential. Used for characterizing oxidation and reduction reactions, corrosion behaviour, and reaction reversibility.

LSV - Linear Sweep Voltammetry
- The working electrode potential is swept linearly from an initial value to a final value in one direction only, with no reverse scan. Current is measured continuously during the sweep. Used for Tafel analysis and corrosion potential determination.

CA - Chronoamperometry
- The working electrode potential is stepped to a value and held constant while current at the working electrode is measured as a function of time. Used for studying reaction kinetics.

OCP - Open Circuit Potential Measurement
- The working electrode potential is measured relative to the reference electrode with no applied current or voltage. Records the natural resting potential over time until equilibrium is reached. Performed before CV and LSV experiments to establish the equilibrium potential.

### Performance requirements
The instrument must operate within a voltage, current, and scan rate range sufficient to perform the electrochemical techniques described in Section 2.1 on Cu, W, and other semiconductor relevant materials.

Potential Range:
- Commercially available instruments like the Keithley 2450-EC and 2460-EC Electrochemistry Lab Systems use a potential window from -5 to +5 volts. However, the experiments planned for this instrument require more modest ranges: for the Ferri/ferrocyanide validation a typical scan range is from −0.2V to +0.6V. A typical scan range for copper in sulfuric acid is from −0.5V to +0.5V and for tungsten in sodium hydroxide is −1.0V to +0.8V. A potential control range of  ±2V was selected to cover all planned experiments with comfortable margin while keeping circuit complexity and cost minimal.

Current Measurement Range:
- The working electrode current during the planned experiments spans approximately from 10 nA in the passive region of both Cu and W to approximately 2 mA during active Cu dissolution on a 0.1 cm² sample. Four switchable transimpedance gain ranges (1 kΩ, 10 kΩ, 100 kΩ, 1 MΩ) were selected to cover this range with adequate resolution at each decade.

Scan Rate Range:
- A scan range of 1 mV/s to 500 mV/s was selected. This is sufficient for corrosion  characterization experiments are typically conducted at 10 mV/s to allow the electrode-electrolyte interface sufficient time to respond to each potential increment and allows for some flexibility. 

Resolution and Accuracy:
- In order to have sufficient accuracy, the following minimum resolution specifications were established:
  - current resolution less than 1nA
  - Voltage resolution at least 1mV.
  - ADC Resolution at least 16bit 
  - Potential accuracy of ± 5mV

### Cost and accessibility constraints
- Cost should be kept under $200
- Components must be available from major suppliers
- Assembly should be relatively simple and require hand soldering only


## Component selection and circuit design

