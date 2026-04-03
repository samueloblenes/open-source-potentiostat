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

### Performance requirements
The instrument must operate within a voltage, current, and scan rate range sufficient to perform the electrochemical techniques described in Section 2.1 on Cu, W, and other semiconductor relevant materials.

Potential Range:
Commercially available instruments like the Keithley 2450-EC and 2460-EC Electrochemistry Lab Systems use a potential window from -5 to +5 volts. However, the experiments planned for this instrument require more modest ranges: for the Ferri/ferrocyanide validation a typical scan range is from −0.2V to +0.6V. A typical scan range for copper in sulfuric acid is from −0.5V to +0.5V and for tungsten in sodium hydroxide is −1.0V to +0.8V. A potential control range of  ±2V was selected to cover all planned experiments with comfortable margin while keeping circuit complexity and cost minimal.

Current Measurement Range:
The working electrode current during the planned experiments spans approximately from 10 nA in the passive region of both Cu and W to approximately 2 mA during active Cu dissolution on a 0.1 cm² sample. Four switchable transimpedance gain ranges (1 kΩ, 10 kΩ, 100 kΩ, 1 MΩ) were selected to cover this range with adequate resolution at each decade.

Scan Rate Range:
A scan range of 1 mV/s to 500 mV/s was selected. This is sufficient for corrosion  characterization experiments are typically conducted at 10 mV/s to allow the electrode-electrolyte interface sufficient time to respond to each potential increment and allows for some flexibility. 

Resolution and Accuracy:
In order to have sufficient accuracy, the following minimum resolution specifications were established:
  current resolution less than 1nA
  Voltage resolution at least 1mV.
  ADC Resolution at least 16bit 
  Potential accuracy of ± 5mV

### Cost and accessibility constraints
Cost should be kept under $200
Components must be available from major suppliers
Assembly should be relatively simple and require hand soldering only


## Component selection and circuit design
### Microcontroler
#### Microcontroller consideration
The microcontroller must satisfy the following requirements:
   Sufficient processing speed for precise sweep timing across the full scan rate range of 1 mV/s to 500 mV/s without timing jitter that would distort CV curve 
measurements.
   Hardware I2C and SPI peripherals for communication with the DAC, and ADC.
   A regulated 3.3V output and a 5V output.
   Compatibility with the Arduino IDE to maximise accessibility and reproducibility.

#### Microcontroller selection
The Teensy 4.1 was selected. It operates at 600 MHz with an ARM Cortex-M7 processor, providing sufficient processing speed and is fully compatible with the Arduino IDE via the Teensyduino add-on. I2C and SPI peripherals are available for communication with the DAC and ADC. The board provides a regulated 3.3V output and a 5V VUSB output. It does not include an onboard DAC this is addressed through the use of an external I2C DAC, which adds only one low-cost component to the design and has negligible impact on circuit complexity.

### DAC
#### DAC Considerations
The Teensy 4.1 microcontroller does not include an onboard DAC, an external DAC is required. The DAC receives a digital value from the Teensy and generates the analog voltage setpoint applied to the control loop, Vset. The DAC must have sufficient resolution to achieve at least 1mV per step, be able to cover the ± 2V potential range, and be compatible with the Teensy 4.1 I2C interface.

#### DAC Selection
The MCP4725 12-bit DAC was selected for this design. It operates from Teensy 4.1 3.3V supply. At 12-bit resolution over a 0 to 3.3V output range the voltage step size is:

  V=3.3V/212=0.806 mV/step

This meets the sub mV resolution requirement. It is low cost, widely used and available, and breakout boards are widely available for breadboarding.

#### Bipolar output
The MCP4725 produces a unipolar output from 0V to 3.3V. The instrument must scan across negative potentials, so we require a bipolar potential range. A unipolar to bipolar converter circuit is required between the DAC output and the control loop. A difference amplifier is used to shift and scale the DAC output to the required range. 

For this circuit we are using a TL072 dual op-amp, with one channel as the differential amplifier, and the other as a buffer for the 1.65V reference voltage. The reference voltage is obtained using a 10KΩ voltage divider on the 3.3V supply from the teensy microcontroller. Decoupling capacitors (100nF and 10µF) capacitors are placed on the +- 12 volt rails to reduce noise, and a 100nF capacitor is used to decouple the reference voltage from the 3.3V rail.

### Potentiostatic control circuit
The potentiostatic control circuit shown in figure 3. receives the set voltage from the DAC, Vset and maintains the potential in the cell at that value. To do this, the design uses another TL072 dual op-amp, with one channel configured as a reference buffer, to read the reference electrode’s potential without drawing any current from it and the other as a control amplifier to maintain the potential in the cell equal to Vset.

### Trans Impedence Amplifier
The current from the working electrode must be converted into voltage so that the ADC can convert it to a digital signal. This is accomplished using a Transimpedance amplifier (TIA). An OPA134 op-amp is used for its low input bias current. This is important because input bias current adds a fixed offset error to the measured current, which becomes significant at the nanoampere level. A feedback resistor is connected between the op-amps inverting input and the output, and sets the transimpedance gain. The output voltage is determined by the product of the input current and the feedback resistance, for smaller currents a larger feedback resistance is required to get a voltage that the ADC can read. Decoupling capacitors (100nF and 10µF) capacitors are placed on the +- 12 volt rails to reduce noise. A feedback compensation capacitor connected in parallel with the feedback resistor prevents oscillations caused by the phase shift introduced by cable capacitance (value to be determined during simulation). The TIA circuit is shown in Figure 4.

#### Gain switching
To accommodate the current ranges specified in section 2.2.2,  a  DG441 quad analog  switch allows for switching between four feedback resistances of 1 kΩ, 10 kΩ, 100 kΩ, and 1 MΩ. Each switch is controlled by a different GPIO pin on the Teensy, setting a pin high closes the corresponding switch completing the circuit between the op-amps inverting input and the desired feedback resistor which is connected to the output. This circuit is shown in Figure 5.

A 50 pF compensation capacitor is placed in parallel with the feedback resistors to
prevent oscillation caused by the phase shift introduced by the input capacitance.
This value was determined by AC stability simulation across all four gain ranges.

#### TIA output offset
The TIA output is bipolar, but the ADC requires a unipolar input within its supply range. An offset is applied using a weighted summing amplifier circuit after the TIA.

The first stage is an inverting summing amplifier that adds a 2.5V offset to the TIA
output, shifting the signal range upward while inverting its polarity. The second stage
is an inverting unity-gain amplifier that restores the correct polarity. The combined
effect is a non-inverting +2.5V shift, placing the full output range within the
ADC input window. The 2.5V reference for the summing stage is derived from a voltage
divider on the 5VUSB supply from the Teensy, buffered by a voltage follower to prevent the divider from
being loaded and skewing the reference voltage. The 2.5V offset is subtracted in firmware
to recover the true signed current value.


### ADC
#### ADC considerations
The analog-to-digital converter (ADC) digitises the TIA output voltage to be sent to the Teensy 4.1. The ADC must  have a resolution of at least 16-bit to achieve the sub-nanoampere current resolution specified

#### ADC Selection
The ADS1115 16-bit ADC was selected.  It shares the I2C bus with the MCP4725 DAC, and operates from the 5V VUSB pin. A breakout board is available for prototyping and the bare IC can be assembled by JLCPCB for the final PCB. 

#### I2C pull-up resistors
The SDA and SCL lines require pull-up resistors to 3.3V for correct I2C operation.
Internal pull-ups on the Teensy are insufficient for reliable operation so two external 4.7 kΩ resistors are placed on the SDA and SCL nets.

### Power supply

The op-amps in the control loop and TIA output conditioning circuit, and the DG441
analog switch, require supply rails sufficient to produce the required output voltages
with adequate headroom. The minimum supply requirements per component are:

| Component       | Min V+ | Min V− |
|:----------------|:------:|:------:|
| TL072           | +3.5V  | −3.5V  |
| OPA134 (TIA)    | +3.0V  | −3.0V  |
| DG441           | +4.5V  | −4.5V  |
| **Overall minimum** | **+4.5V** | **−4.5V** |

A ±5V supply would be sufficient but leaves little margin; supply variation could cause
clipping or signal distortion. Applying a headroom factor of approximately 2× gives a
±9V minimum; the closest standard supply voltage is ±12V, which was selected for this
design.








