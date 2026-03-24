# Component Selection and Circuit Design

## Overview
This document describes the circuit design of the open-source potentiostat, detailing the selection criteria and reasoning for each major component and subsystem. 
The design priorities are affordability, reproducibility, and sufficient performance for cyclic voltammetry and corrosion characterization of Cu and W in semiconductor-relevant electrolytes.

## Design requirements and constraints

### Functional requirements
CV - Cyclic Voltammetry:
The working electrode potential is swept linearly from an initial value to a final value, then reversed back to the initial value. Current at the working electrode is measured continuously as a function of applied potential. Used for characterizing oxidation and reduction reactions, corrosion behaviour, and reaction reversibility.

LSV - Linear Sweep Voltammetry
The working electrode potential is swept linearly from an initial value to a final value in one direction only, with no reverse scan. Current is measured continuously during the sweep. Used for Tafel analysis and corrosion potential determination.

CA - Chronoamperometry
The working electrode potential is stepped to a value and held constant while current at the working electrode is measured as a function of time. Used for studying reaction kinetics.

OCP - Open Circuit Potential Measurement
The working electrode potential is measured relative to the reference electrode with no applied current or voltage. Records the natural resting potential over time until equilibrium is reached. Performed before CV and LSV experiments to establish the equilibrium potential.

