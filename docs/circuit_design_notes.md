# Component Selection and Circuit Design

## Overview
This document describes the circuit design of the open-source potentiostat, The design priorities are affordability, reproducibility, and sufficient performance.

## Design requirements and constraints

### Functional requirements
CV - Cyclic Voltammetry:
The working electrode potential is swept linearly from an initial value to a final value, then reversed back to the initial value. Current at the working electrode is measured continuously as a function of applied potential. Used for characterizing oxidation and reduction reactions, corrosion behaviour, reaction reversibility, etc.

LSV - Linear Sweep Voltammetry
The working electrode potential is swept linearly from an initial value to a final value in one direction only, with no reverse scan. Current is measured continuously during the sweep.

CA - Chronoamperometry
The working electrode potential is stepped to a value and held constant while current at the working electrode is measured as a function of time. Used for studying reaction kinetics.

### Performance requirements
The instrument must operate within a voltage, current, and scan rate range sufficient to perform the electrochemical techniques described in Section 2.1.

Potential Range:
A potential control range of ±2V was selected to cover all planned experiments with comfortable margin while keeping circuit complexity and cost minimal.

Current Measurement Range:
The working electrode current during the planned experiments spans approximately from 10 nA to 2 mA. Four switchable transimpedance gain ranges (1 kΩ, 10 kΩ, 100 kΩ, 1 MΩ) were selected to cover this range with adequate resolution at each decade.

Resolution and Accuracy:
In order to have sufficient accuracy, the following minimum resolution specifications were established:
- current resolution less than 1 nA
- voltage resolution at least 1 mV
- ADC resolution at least 16-bit
- potential accuracy of ± 5mV

### Cost and accessibility constraints
- Cost should be kept under $200
- Components must be available from major suppliers
- Assembly should be relatively simple and require hand soldering only


## Component selection and circuit design

### Microcontroller

#### Microcontroller consideration
The microcontroller must satisfy the following requirements:
- Sufficient processing speed for precise sweep timing across the full scan rate range of 1 mV/s to 500 mV/s without timing jitter that would distort CV curve measurements.
- Hardware I2C and SPI peripherals for communication with the DAC and ADC.
- A regulated 3.3V output and a 5V output.
- Compatibility with the Arduino IDE to maximise accessibility and reproducibility.

#### Microcontroller selection
The Teensy 4.1 was selected. It operates at 600 MHz with an ARM Cortex-M7 processor, providing sufficient processing speed, and is fully compatible with the Arduino IDE via the Teensyduino add-on. I2C and SPI peripherals are available for communication with the DAC and ADC. The board provides a regulated 3.3V output and a 5V VUSB output. It does not include an onboard DAC; this is addressed through the use of an external I2C DAC, which adds only one low-cost component to the design and has negligible impact on circuit complexity.

### DAC

#### DAC considerations
The Teensy 4.1 microcontroller does not include an onboard DAC, so an external DAC is required. The DAC receives a digital value from the Teensy and generates the analog voltage setpoint applied to the control loop, Vset. The DAC must have sufficient resolution to achieve at least 1mV per step, be able to cover the ±2V potential range, and be compatible with the Teensy 4.1 I2C interface.

#### DAC selection
The MCP4725 12-bit DAC was selected for this design. It operates from the Teensy 4.1's 3.3V supply. At 12-bit resolution over a 0 to 3.3V output range, the voltage step size is:

V = 3.3V / 2^12 = 0.806 mV/step

This meets the sub-mV resolution requirement. It is low cost, widely used and available, and breakout boards are widely available for breadboarding.

#### Bipolar output
The MCP4725 produces a unipolar output from 0V to 3.3V. The instrument must scan across negative potentials, so a bipolar potential range is required. A unipolar-to-bipolar converter circuit is placed between the DAC output and the control loop. A difference amplifier is used to shift and scale the DAC output to the required range.

For this circuit, a TL072 dual op-amp is used, with one channel as the differential amplifier and the other as a buffer for the 1.65V reference voltage.

The reference voltage is derived from an ADR4533 fixed 3.3V precision voltage reference IC, powered directly from the +12V rail. A matched 10kΩ:10kΩ resistor divider on the ADR4533's output sets the 1.65V midpoint, which is then buffered by the second TL072 channel. Per the ADR4533 datasheet, a minimum 0.1µF output capacitor and a 1µF/0.1µF input capacitor pair are required for stability and noise reduction.

Decoupling capacitors (100nF and 10µF) are placed on the ±12V rails to reduce noise, and a 100nF capacitor decouples the buffered reference voltage node.

### Potentiostatic control circuit
The potentiostatic control circuit receives the set voltage from the DAC, Vset, and maintains the potential in the cell at that value. To do this, the design uses another TL072 dual op-amp, with one channel configured as a reference buffer to read the reference electrode's potential without drawing any current from it, and the other as a control amplifier to maintain the potential in the cell equal to Vset.

### Transimpedance amplifier
The current from the working electrode must be converted into voltage so that the ADC can convert it to a digital signal. This is accomplished using a transimpedance amplifier (TIA). An OPA134 op-amp is used for its low input bias current. This is important because input bias current adds a fixed offset error to the measured current, which becomes significant at the nanoampere level. A feedback resistor is connected between the op-amp's inverting input and the output, and sets the transimpedance gain. The output voltage is determined by the product of the input current and the feedback resistance; for smaller currents a larger feedback resistance is required to get a voltage that the ADC can read. Decoupling capacitors (100nF and 10µF) are placed on the ±12V rails to reduce noise. A feedback compensation capacitor connected in parallel with the feedback resistor prevents oscillations caused by the phase shift introduced by cable capacitance. 

#### Gain switching
To accommodate the current ranges specified above, a DG441 quad analog switch allows switching between four feedback resistances of 1 kΩ, 10 kΩ, 100 kΩ, and 1 MΩ. Each switch is controlled by a different GPIO pin on the Teensy; setting a pin high closes the corresponding switch, completing the circuit between the op-amp's inverting input and the desired feedback resistor, which is connected to the output. This circuit is shown in Figure 5.

A 50 pF compensation capacitor is placed in parallel with the feedback resistors to prevent oscillation caused by the phase shift introduced by the input capacitance. This value was determined by AC stability simulation across all four gain ranges.

#### TIA output offset
The TIA output is bipolar, but the ADC requires a unipolar input within its supply range. An offset is applied using a weighted summing amplifier circuit after the TIA.

The first stage is an inverting summing amplifier that adds a 2.5V offset to the TIA output, shifting the signal range upward while inverting its polarity. The second stage is an inverting unity-gain amplifier that restores the correct polarity. The combined effect is a non-inverting +2.5V shift, placing the full output range within the ADC input window.

The 2.5V reference for the summing stage is supplied directly by an ADR4525 fixed 2.5V precision voltage reference IC, powered from the +12V rail. Per the ADR4525 datasheet, a minimum 1.0µF output capacitor and a 1µF/0.1µF input capacitor pair are required for stability.

The 2.5V offset is subtracted in firmware to recover the true current value.

### ADC

#### ADC considerations
The analog-to-digital converter (ADC) digitises the TIA output voltage to be sent to the Teensy 4.1. The ADC must have a resolution of at least 16-bit to achieve the resolution specified above.

#### ADC selection
The ADS1115 16-bit ADC was selected. It shares the I2C bus with the MCP4725 DAC, and operates from the 5V VUSB pin. 

#### I2C pull-up resistors
The SDA and SCL lines require pull-up resistors to 3.3V for correct I2C operation. Two external 4.7 kΩ resistors are placed on the SDA and SCL nets.

### Power supply

#### +12V input and −12V generation
+12V is supplied externally via a barrel-jack input. The −12V rail required by the op-amps is generated from this +12V supply using a TC7662B switched-capacitor voltage inverter.

