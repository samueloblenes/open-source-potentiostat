// =============================================================================
//  Open-Source Potentiostat — Teensy 4.1 Firmware
//  Techniques implemented: CV (Cyclic Voltammetry)
//  Hardware:
//    DAC  — MCP4725 (I2C, addr 0x60)
//    ADC  — ADS1115 (I2C, addr 0x48)
//    TIA  — Fixed gain (gain switching NOT yet implemented)
//    Gain resistor: 100 kΩ (covers ~25 nA – 25 µA range)
//
//  Serial protocol (115200 baud, ASCII, newline-terminated):
//    PC → Teensy   PING
//    Teensy → PC   PONG
//
//    PC → Teensy   CV,<Ei_V>,<Ef_V>,<scanrate_V_per_s>,<cycles>
//                  e.g. CV,-0.5000,0.5000,0.0500,2
//    Teensy → PC   OK
//                  <E_V>,<I_A>,<t_s>   (one line per sample)
//                  DONE
//
//    PC → Teensy   STOP
//    Teensy → PC   (stops sending data; sends nothing extra)
//
//    On any parameter error:
//    Teensy → PC   ERR,<message>
// =============================================================================

#include <Wire.h>

// ── Hardware constants ────────────────────────────────────────────────────────

// I2C addresses
constexpr uint8_t MCP4725_ADDR = 0x62;
constexpr uint8_t ADS1115_ADDR = 0x48;

// MCP4725 write command (fast mode: no EEPROM write)
constexpr uint8_t MCP4725_CMD_FASTWRITE = 0x00;

// ADS1115 register addresses
constexpr uint8_t ADS_REG_CONVERT = 0x00;
constexpr uint8_t ADS_REG_CONFIG  = 0x01;

// ADS1115 configuration written once in setup().
// ALRT and ADDR pins are not used — ADDR is tied to GND (address 0x48),
// ALRT is left unconnected.
//
// Config register layout (written MSB first):
//   [15]    OS=1      start a single-shot conversion immediately
//   [14:12] MUX=100   AIN0 single-ended vs GND
//   [11:9]  PGA=000   ±6.144 V FSR — chosen so the full 0–5 V TIA output
//                     range fits within the ADC input window.
//                     NOTE: the ADS1115 input must not exceed VDD+0.3 V;
//                     with a 5 V supply this is fine.
//   [8]     MODE=1    single-shot (we trigger each conversion manually)
//   [7:5]   DR=100    128 SPS → conversion time ~7.8 ms, simple fixed delay
//   [4:2]             comparator fields — irrelevant, left at reset default (0)
//   [1:0]   COMP_QUE=11  disable comparator output on ALRT pin (reset default)
//
// 128 SPS is chosen over 860 SPS because it allows a simple fixed 8 ms delay
// instead of polling the OS bit, keeping the driver straightforward.
// At the slowest planned scan rate (1 mV/s, dV ~1 mV per step) one sample
// every ~8 ms is more than adequate.
constexpr uint16_t ADS_CONFIG =
    (1      << 15) |   // OS:  start conversion
    (0b100  << 12) |   // MUX: AIN0/GND
    (0b000  <<  9) |   // PGA: ±6.144 V
    (1      <<  8) |   // MODE: single-shot
    (0b100  <<  5) |   // DR:  128 SPS
    (0b11);            // COMP_QUE: disabled (ALRT stays high/floating)

// LSB size for PGA = ±6.144 V: 6.144 V / 32768 counts
constexpr float ADS_LSB_V = 6.144f / 32768.0f;

// Conversion time for 128 SPS with a small safety margin (ms)
constexpr uint8_t ADS_CONV_DELAY_MS = 9;

// DAC (MCP4725): 12-bit over 0–3.3 V
constexpr float DAC_VREF      = 3.3f;
constexpr float DAC_STEPS     = 4096.0f;  // 2^12
constexpr float DAC_LSB_V     = DAC_VREF / DAC_STEPS;

// Unipolar-to-bipolar converter (difference amplifier) transfer function:
//   Vset = GAIN * (Vdac - VREF_DAC)
// From component selection notes:
//   gain  = R4/R2 = 12.12k / 10k = 1.212
//   Vref  = 1.65 V  (half of 3.3 V rail)
constexpr float BIPOLAR_GAIN  = 1.212f;
constexpr float BIPOLAR_VREF  = 1.65f;   // V

// TIA output: Vout = (Iin * Rfeedback) + TIA_OFFSET_V
//   The output is already the correct sign; the +2.5 V offset is a DC shift
//   so the bipolar current signal fits within the ADC input range.
//   Recovery: Iin = (Vout - TIA_OFFSET_V) / Rfeedback  (no sign flip)
constexpr float TIA_OFFSET_V  = 2.5f;
constexpr float TIA_RFEEDBACK = 100000.0f;  // 100 kΩ

// Instrument voltage limits (hard clamp — protects hardware)
constexpr float VSET_MAX_V    =  2.0f;
constexpr float VSET_MIN_V    = -2.0f;

// ── Experiment state ──────────────────────────────────────────────────────────

enum class State { IDLE, RUNNING };
static State gState = State::IDLE;
static bool  gStopRequested = false;

// ── Forward declarations ──────────────────────────────────────────────────────

void      dacWrite(float vset_V);
float     adcRead_V();
float     adcRead_current_A();
void      runCV(float Ei, float Ef, float scanrate, int cycles);
bool      parseCV(const String& cmd, float& Ei, float& Ef,
                  float& scanrate, int& cycles);
void      sendDataPoint(float E_V, float I_A, float t_s);
void      sendError(const char* msg);

// ── Setup ─────────────────────────────────────────────────────────────────────

void setup() {
    Serial.begin(115200);
    Wire.begin();
    Wire.setClock(400000);  // 400 kHz fast-mode I2C

    // Write the ADS1115 config register once at startup.
    // All subsequent reads just trigger a conversion and read the result —
    // no need to reconfigure between reads since PGA, MUX, and data rate
    // don't change during normal operation.
    Wire.beginTransmission(ADS1115_ADDR);
    Wire.write(ADS_REG_CONFIG);
    Wire.write((uint8_t)(ADS_CONFIG >> 8));
    Wire.write((uint8_t)(ADS_CONFIG & 0xFF));
    Wire.endTransmission();

    // Drive DAC to mid-rail (Vset = 0 V) on startup
    dacWrite(0.0f);
}

// ── Main loop ─────────────────────────────────────────────────────────────────

void loop() {
    if (!Serial.available()) return;

    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() == 0) return;

    // ── PING ─────────────────────────────────────────────────────────────────
    if (line == "PING") {
        Serial.println("PONG");
        return;
    }

    // ── STOP ─────────────────────────────────────────────────────────────────
    if (line == "STOP") {
        gStopRequested = true;
        // The running experiment checks gStopRequested and exits cleanly.
        return;
    }

    // ── CV ───────────────────────────────────────────────────────────────────
    if (line.startsWith("CV,")) {
        if (gState == State::RUNNING) {
            sendError("experiment already running");
            return;
        }

        float Ei, Ef, scanrate;
        int   cycles;
        if (!parseCV(line, Ei, Ef, scanrate, cycles)) return;  // error already sent

        gStopRequested = false;
        gState = State::RUNNING;
        Serial.println("OK");
        runCV(Ei, Ef, scanrate, cycles);
        gState = State::IDLE;

        if (!gStopRequested) {
            // Experiment completed naturally — return electrode to 0 V
            dacWrite(0.0f);
            Serial.println("DONE");
        }
        // If stopped mid-run, do not send DONE (the PC already knows via STOP)
        dacWrite(0.0f);
        return;
    }

    // ── Unknown command ───────────────────────────────────────────────────────
    sendError("unknown command");
}

// =============================================================================
//  CV Implementation
// =============================================================================

// runCV — executes a complete cyclic voltammetry sweep.
//
// Parameters:
//   Ei       : initial potential  (V vs RE)
//   Ef       : final/vertex potential (V vs RE)
//   scanrate : potential scan rate (V/s), positive value
//   cycles   : number of complete cycles (Ei → Ef → Ei counts as one cycle)
//
// Each cycle consists of two legs:
//   Forward leg: Ei → Ef
//   Reverse leg: Ef → Ei
//
// The step interval is calculated so that the DAC advances by exactly one LSB
// per step. The ADC is read once per step and the result is sent immediately.
void runCV(float Ei, float Ef, float scanrate, int cycles) {
    // Step size: one DAC LSB mapped back to volts at the cell.
    // Vset = GAIN * (Vdac - Vref), so:
    //   dVset = GAIN * dVdac = GAIN * DAC_LSB_V
    const float dV_step = BIPOLAR_GAIN * DAC_LSB_V;  // ~0.976 mV

    // Time between steps (µs) derived from scan rate and voltage step size.
    //   step_interval = dV_step / scanrate   (in seconds)
    const float step_interval_s  = dV_step / scanrate;
    const uint32_t step_us       = (uint32_t)(step_interval_s * 1e6f);

    // Clamp step_us to a minimum that allows the ADC to complete a conversion.
    // At 128 SPS with a 9 ms safety margin, each read takes ~9 ms minimum.
    const uint32_t MIN_STEP_US = 9000;
    const uint32_t actual_step_us = max(step_us, MIN_STEP_US);

    // Recalculate effective dV if clamped (scan rate limited by ADC speed)
    // We keep dV_step fixed at one DAC LSB and just accept the slower rate.
    // The true scan rate sent back to the PC is implicit in the (E, t) pairs.

    // Experiment start time (reference for all reported timestamps)
    const uint32_t t0_us = micros();

    for (int cycle = 0; cycle < cycles; cycle++) {
        // ── Forward leg: Ei → Ef ─────────────────────────────────────────────
        {
            float V     = Ei;
            float V_end = Ef;
            float sign  = (Ef >= Ei) ? +1.0f : -1.0f;

            while ((sign > 0 && V <= Ef) || (sign < 0 && V >= Ef)) {
                if (gStopRequested) return;

                dacWrite(V);

                uint32_t step_start = micros();

                float I_A = adcRead_current_A();
                float t_s = (float)(micros() - t0_us) * 1e-6f;

                sendDataPoint(V, I_A, t_s);

                // Busy-wait for remainder of step interval
                while ((micros() - step_start) < actual_step_us) {}

                V += sign * dV_step;
            }
            // Ensure the vertex potential is hit exactly
            dacWrite(Ef);
            {
                float I_A = adcRead_current_A();
                float t_s = (float)(micros() - t0_us) * 1e-6f;
                sendDataPoint(Ef, I_A, t_s);
            }
        }

        // ── Reverse leg: Ef → Ei ─────────────────────────────────────────────
        {
            float V    = Ef;
            float sign = (Ei >= Ef) ? +1.0f : -1.0f;

            while ((sign > 0 && V <= Ei) || (sign < 0 && V >= Ei)) {
                if (gStopRequested) return;

                dacWrite(V);

                uint32_t step_start = micros();

                float I_A = adcRead_current_A();
                float t_s = (float)(micros() - t0_us) * 1e-6f;

                sendDataPoint(V, I_A, t_s);

                while ((micros() - step_start) < actual_step_us) {}

                V += sign * dV_step;
            }
            // Ensure Ei is hit exactly at end of cycle
            dacWrite(Ei);
            {
                float I_A = adcRead_current_A();
                float t_s = (float)(micros() - t0_us) * 1e-6f;
                sendDataPoint(Ei, I_A, t_s);
            }
        }
    }
}

// =============================================================================
//  DAC — MCP4725
// =============================================================================

// dacWrite — set the cell potential to vset_V (volts vs reference electrode).
//
// Converts the desired cell potential to the DAC output voltage required by
// the unipolar-to-bipolar difference amplifier, then writes the 12-bit code.
//
//   Vset = GAIN * (Vdac - Vref_dac)   ⟹   Vdac = (Vset / GAIN) + Vref_dac
void dacWrite(float vset_V) {
    // Hard clamp to ±2 V to protect hardware
    vset_V = constrain(vset_V, VSET_MIN_V, VSET_MAX_V);

    float vdac = (vset_V / BIPOLAR_GAIN) + BIPOLAR_VREF;

    // Clamp Vdac to DAC output range
    vdac = constrain(vdac, 0.0f, DAC_VREF);

    uint16_t code = (uint16_t)(vdac / DAC_VREF * (DAC_STEPS - 1.0f) + 0.5f);
    code = min(code, (uint16_t)4095);

    // MCP4725 fast-write: [0x0] [D11..D8] [D7..D0]
    Wire.beginTransmission(MCP4725_ADDR);
    Wire.write((MCP4725_CMD_FASTWRITE << 4) | (uint8_t)(code >> 8));
    Wire.write((uint8_t)(code & 0xFF));
    Wire.endTransmission();
}

// =============================================================================
//  ADC — ADS1115
// =============================================================================

// adcRead_V — trigger a single-shot conversion and return the result in volts.
//
// Sequence:
//   1. Write the config register with OS=1 to start a conversion.
//      The rest of the config word is identical to what was written in setup(),
//      so PGA, MUX, and data rate are unchanged.
//   2. Wait a fixed delay (ADS_CONV_DELAY_MS) for the conversion to finish.
//      At 128 SPS one conversion takes 7.8 ms; 9 ms gives a safe margin
//      without needing to poll the OS bit or use the ALRT pin.
//   3. Point the address pointer at the conversion register and read 2 bytes.
float adcRead_V() {
    // Step 1: trigger conversion (OS bit = 1, rest of config unchanged)
    Wire.beginTransmission(ADS1115_ADDR);
    Wire.write(ADS_REG_CONFIG);
    Wire.write((uint8_t)(ADS_CONFIG >> 8));   // MSB — OS=1 starts conversion
    Wire.write((uint8_t)(ADS_CONFIG & 0xFF)); // LSB
    Wire.endTransmission();

    // Step 2: wait for conversion to complete
    delay(ADS_CONV_DELAY_MS);

    // Step 3: read the conversion register
    Wire.beginTransmission(ADS1115_ADDR);
    Wire.write(ADS_REG_CONVERT);
    Wire.endTransmission();
    Wire.requestFrom((uint8_t)ADS1115_ADDR, (uint8_t)2);
    int16_t raw = ((int16_t)Wire.read() << 8) | Wire.read();

    return (float)raw * ADS_LSB_V;
}

// adcRead_current_A — read TIA output voltage and convert to current in amperes.
//
//   TIA output: Vout = (Iin * Rfeedback) + 2.5 V
//   The signal is already the correct sign; subtract the 2.5 V DC offset
//   and divide by Rfeedback to recover the current.
//   Iin = (Vout - TIA_OFFSET_V) / Rfeedback
float adcRead_current_A() {
    float vout = adcRead_V();
    float current = (vout - TIA_OFFSET_V) / TIA_RFEEDBACK;
    return current;
}

// =============================================================================
//  Serial helpers
// =============================================================================

// sendDataPoint — emit one CSV data line: E (V), I (A), t (s)
void sendDataPoint(float E_V, float I_A, float t_s) {
    // Use print / println to avoid heap allocation from String concatenation
    // Format: "E,I,t\n" matching what the PC parser expects
    Serial.print(E_V, 4);
    Serial.print(',');
    Serial.print(I_A, 6);
    Serial.print(',');
    Serial.println(t_s, 3);
}

// sendError — emit "ERR,<msg>" to the PC
void sendError(const char* msg) {
    Serial.print("ERR,");
    Serial.println(msg);
}

// =============================================================================
//  Command parser
// =============================================================================

// parseCV — parse a "CV,Ei,Ef,scanrate,cycles" command string.
//
// Returns true if all parameters are valid, false (with error sent) otherwise.
bool parseCV(const String& cmd, float& Ei, float& Ef,
             float& scanrate, int& cycles)
{
    // Expected format: CV,<Ei>,<Ef>,<scanrate>,<cycles>
    // Field indices after splitting on ',': 0=CV 1=Ei 2=Ef 3=scanrate 4=cycles
    int idx0 = cmd.indexOf(',');
    if (idx0 < 0) { sendError("CV parse: missing Ei"); return false; }

    int idx1 = cmd.indexOf(',', idx0 + 1);
    if (idx1 < 0) { sendError("CV parse: missing Ef"); return false; }

    int idx2 = cmd.indexOf(',', idx1 + 1);
    if (idx2 < 0) { sendError("CV parse: missing scanrate"); return false; }

    int idx3 = cmd.indexOf(',', idx2 + 1);
    if (idx3 < 0) { sendError("CV parse: missing cycles"); return false; }

    Ei       = cmd.substring(idx0 + 1, idx1).toFloat();
    Ef       = cmd.substring(idx1 + 1, idx2).toFloat();
    scanrate = cmd.substring(idx2 + 1, idx3).toFloat();
    cycles   = cmd.substring(idx3 + 1).toInt();

    // Validation
    if (Ei == Ef) {
        sendError("CV: Ei must not equal Ef");
        return false;
    }
    if (Ei < VSET_MIN_V || Ei > VSET_MAX_V) {
        sendError("CV: Ei out of range (-2 to +2 V)");
        return false;
    }
    if (Ef < VSET_MIN_V || Ef > VSET_MAX_V) {
        sendError("CV: Ef out of range (-2 to +2 V)");
        return false;
    }
    if (scanrate <= 0.0f) {
        sendError("CV: scanrate must be positive");
        return false;
    }
    if (cycles < 1 || cycles > 100) {
        sendError("CV: cycles must be 1 – 100");
        return false;
    }

    return true;
}
