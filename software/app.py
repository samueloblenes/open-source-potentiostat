import csv
import queue
import sys
import serial
import serial.tools.list_ports
from datetime import datetime

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

from PyQt6.QtCore import (
    Qt, QObject, QThread, QTimer, pyqtSignal, pyqtSlot,
)
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QSizePolicy, QSpinBox, QSplitter, QStackedWidget,
    QStatusBar, QTextEdit, QVBoxLayout, QWidget,
)

STYLESHEET = """
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", sans-serif;
    font-size: 10pt;
}
QMainWindow, QDialog { background-color: #181825; }
QFrame#panel {
    background-color: #24273a;
    border: 1px solid #313244;
    border-radius: 6px;
}
QComboBox, QDoubleSpinBox, QSpinBox {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 3px 6px;
    color: #cdd6f4;
}
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background-color: #313244;
    selection-background-color: #585b70;
}
QPushButton {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 5px 12px;
    color: #cdd6f4;
}
QPushButton:hover  { background-color: #45475a; }
QPushButton:pressed { background-color: #585b70; }
QPushButton:disabled { color: #6c7086; border-color: #313244; }
QPushButton#run_btn {
    background-color: #a6e3a1;
    color: #1e1e2e;
    font-weight: bold;
    border: none;
}
QPushButton#run_btn:hover    { background-color: #94d08e; }
QPushButton#run_btn:disabled { background-color: #313244; color: #6c7086; }
QPushButton#stop_btn {
    background-color: #f38ba8;
    color: #1e1e2e;
    font-weight: bold;
    border: none;
}
QPushButton#stop_btn:hover    { background-color: #e07a96; }
QPushButton#stop_btn:disabled { background-color: #313244; color: #6c7086; }
QPushButton#connect_btn {
    background-color: #89b4fa;
    color: #1e1e2e;
    font-weight: bold;
    border: none;
}
QPushButton#connect_btn:hover { background-color: #74a8f5; }
QLabel#led_connected    { color: #a6e3a1; font-size: 14pt; }
QLabel#led_disconnected { color: #f38ba8; font-size: 14pt; }
QTextEdit#serial_log {
    background-color: #11111b;
    color: #a6adc8;
    font-family: "Consolas", monospace;
    font-size: 9pt;
    border: 1px solid #313244;
    border-radius: 4px;
}
QStatusBar { background-color: #181825; color: #a6adc8; }
QSplitter::handle { background-color: #313244; }
NavigationToolbar2QT { background-color: #1e1e2e; }
"""

# ── DataLogger ─────────────────────────────────────────────────────────────────
class DataLogger:
    def __init__(self):
        self._file = None
        self._writer = None

    def start(self, filepath: str, technique: str, params: dict):
        self._file = open(filepath, "w", newline="", encoding="utf-8")
        self._file.write(f"# Technique: {technique}\n")
        for k, v in params.items():
            self._file.write(f"# {k}: {v}\n")
        self._file.write(f"# Started: {datetime.now().isoformat()}\n")
        self._writer = csv.writer(self._file)
        self._writer.writerow(["E_V", "I_A", "t_s"])
        self._file.flush()

    def log(self, E: float, I: float, t: float):
        if self._writer:
            self._writer.writerow([f"{E:.4f}", f"{I:.6e}", f"{t:.3f}"])
            self._file.flush()

    def stop(self):
        if self._file:
            self._file.close()
        self._file = None
        self._writer = None

    @property
    def is_open(self) -> bool:
        return self._file is not None


# ── SerialWorker ───────────────────────────────────────────────────────────────
class SerialWorker(QObject):
    """
    Handles USB serial I/O on a background QThread.
    Callers emit request signals; results arrive via response signals.
    """

    # connect_requested is the only signal-based request.
    # send_command() and disconnect_now() are called directly (thread-safe)
    # because _read_loop() blocks the worker's Qt event loop while connected.
    connect_requested = pyqtSignal(str)

    # Responses
    connected    = pyqtSignal()
    disconnected = pyqtSignal()
    data_point   = pyqtSignal(float, float, float)  # E, I, t
    status_msg   = pyqtSignal(str)                  # OK / DONE / ERR,... / PONG
    error        = pyqtSignal(str)

    # Raw serial traffic (every line, used by the debug monitor)
    raw_tx = pyqtSignal(str)   # line sent to device
    raw_rx = pyqtSignal(str)   # line received from device

    def __init__(self):
        super().__init__()
        self._serial: serial.Serial | None = None
        self._running = False
        self._cmd_queue: queue.Queue = queue.Queue()  # thread-safe outgoing command queue

        self.connect_requested.connect(self._connect)

    # ── private slots (run on worker thread) ──────────────────────────────────

    @pyqtSlot(str)
    def _connect(self, port: str):
        try:
            ser = serial.Serial(port, 115200, timeout=2)
        except serial.SerialException as exc:
            self.error.emit(f"Cannot open {port}: {exc}")
            return

        # PING / PONG handshake — up to 3 attempts
        for _ in range(3):
            ser.write(b"PING\n")
            self.raw_tx.emit("PING")
            line = ser.readline().decode("ascii", errors="ignore").strip()
            if line:
                self.raw_rx.emit(line)
            if line == "PONG":
                # Switch to a short timeout so the read loop iterates
                # frequently enough to drain the outgoing command queue.
                ser.timeout = 0.05
                self._serial = ser
                self._running = True
                self.connected.emit()
                self._read_loop()
                return

        ser.close()
        self.error.emit(f"Connection failed: no response from {port}.\nCheck that the Teensy is plugged in and powered on.")

    def send_command(self, cmd: str):
        """Thread-safe: put a command in the outgoing queue. Called from main thread."""
        self._cmd_queue.put(cmd)
        self.raw_tx.emit(cmd)  # log immediately so the monitor shows it right away

    def disconnect_now(self):
        """Thread-safe: stop the read loop and close the port. Called from main thread."""
        self._running = False
        if self._serial and self._serial.is_open:
            try:
                self._serial.close()  # interrupts readline() on the worker thread
            except Exception:
                pass

    def _read_loop(self):
        """Blocking loop — runs for the lifetime of a serial connection.

        Each iteration: drain the outgoing command queue first, then block
        on readline() for up to timeout=0.05 s before looping again.
        This keeps send latency under ~50 ms without busy-waiting.
        """
        while self._running:
            # ── Drain outgoing commands ───────────────────────────────────────
            while not self._cmd_queue.empty():
                try:
                    cmd = self._cmd_queue.get_nowait()
                    if self._serial and self._serial.is_open:
                        self._serial.write((cmd + "\n").encode("ascii"))
                except queue.Empty:
                    break
                except serial.SerialException as exc:
                    self.error.emit(f"Write error: {exc}")
                    self._running = False
                    break

            if not self._running:
                break

            # ── Read one line (blocks up to timeout=0.05 s) ───────────────────
            try:
                raw = self._serial.readline()
            except serial.SerialException:
                # Port closed externally (e.g. disconnect_now()) — exit cleanly
                break
            line = raw.decode("ascii", errors="ignore").strip()
            if line:
                self.raw_rx.emit(line)
                self._parse(line)

        self.disconnected.emit()

    def _parse(self, line: str):
        parts = line.split(",")
        if line.startswith("ERR") or line in ("OK", "DONE", "PONG"):
            self.status_msg.emit(line)
        elif len(parts) == 3:
            try:
                self.data_point.emit(float(parts[0]), float(parts[1]), float(parts[2]))
            except ValueError:
                pass  # ignore malformed lines


# ── ConfigPanel ────────────────────────────────────────────────────────────────
class ConfigPanel(QWidget):
    """Stacked form for CV / LSV / CA / OCP parameters."""

    run_requested  = pyqtSignal(str)   # validated command string
    stop_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _dspin(self, lo, hi, val, dec=3, suffix=""):
        w = QDoubleSpinBox()
        w.setRange(lo, hi)
        w.setValue(val)
        w.setDecimals(dec)
        if suffix:
            w.setSuffix(f"  {suffix}")
        return w

    def _ispin(self, lo, hi, val):
        w = QSpinBox()
        w.setRange(lo, hi)
        w.setValue(val)
        return w

    # ── UI construction ───────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        root.addWidget(QLabel("Technique"))
        self.technique_combo = QComboBox()
        self.technique_combo.addItems(["CV", "LSV", "CA", "OCP"])
        self.technique_combo.currentIndexChanged.connect(self._switch_page)
        root.addWidget(self.technique_combo)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._cv_page())
        self.stack.addWidget(self._lsv_page())
        self.stack.addWidget(self._ca_page())
        self.stack.addWidget(self._ocp_page())
        root.addWidget(self.stack)

        btn_row = QHBoxLayout()
        self.run_btn  = QPushButton("Run")
        self.stop_btn = QPushButton("Stop")
        self.run_btn.setObjectName("run_btn")
        self.stop_btn.setObjectName("stop_btn")
        self.run_btn.setEnabled(False)   # enabled after connection
        self.stop_btn.setEnabled(False)
        self.run_btn.clicked.connect(self._on_run)
        self.stop_btn.clicked.connect(self.stop_requested)
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self.stop_btn)
        root.addLayout(btn_row)
        root.addStretch()

    def _cv_page(self):
        w = QWidget()
        f = QFormLayout(w)
        self.cv_Ei     = self._dspin(-3.0, 3.0, -0.5, suffix="V")
        self.cv_Ef     = self._dspin(-3.0, 3.0,  0.5, suffix="V")
        self.cv_v      = self._dspin(0.001, 10.0, 0.05, suffix="V/s")
        self.cv_cycles = self._ispin(1, 100, 2)
        f.addRow("Ei",        self.cv_Ei)
        f.addRow("Ef",        self.cv_Ef)
        f.addRow("Scan rate", self.cv_v)
        f.addRow("Cycles",    self.cv_cycles)
        return w

    def _lsv_page(self):
        w = QWidget()
        f = QFormLayout(w)
        self.lsv_Ei = self._dspin(-3.0, 3.0, -0.5, suffix="V")
        self.lsv_Ef = self._dspin(-3.0, 3.0,  0.5, suffix="V")
        self.lsv_v  = self._dspin(0.001, 10.0, 0.05, suffix="V/s")
        f.addRow("Ei",        self.lsv_Ei)
        f.addRow("Ef",        self.lsv_Ef)
        f.addRow("Scan rate", self.lsv_v)
        return w

    def _ca_page(self):
        w = QWidget()
        f = QFormLayout(w)
        self.ca_Estep    = self._dspin(-3.0, 3.0, 0.2, suffix="V")
        self.ca_duration = self._dspin(0.1, 3600.0, 60.0, dec=1, suffix="s")
        f.addRow("Estep",    self.ca_Estep)
        f.addRow("Duration", self.ca_duration)
        return w

    def _ocp_page(self):
        w = QWidget()
        f = QFormLayout(w)
        self.ocp_duration = self._dspin(0.1, 3600.0, 120.0, dec=1, suffix="s")
        f.addRow("Duration", self.ocp_duration)
        return w

    # ── public API ────────────────────────────────────────────────────────────

    def technique(self) -> str:
        return self.technique_combo.currentText()

    def command(self) -> str:
        t = self.technique()
        if t == "CV":
            return (f"CV,{self.cv_Ei.value():.4f},{self.cv_Ef.value():.4f},"
                    f"{self.cv_v.value():.4f},{self.cv_cycles.value()}")
        if t == "LSV":
            return (f"LSV,{self.lsv_Ei.value():.4f},{self.lsv_Ef.value():.4f},"
                    f"{self.lsv_v.value():.4f}")
        if t == "CA":
            return f"CA,{self.ca_Estep.value():.4f},{self.ca_duration.value():.1f}"
        # OCP
        return f"OCP,{self.ocp_duration.value():.1f}"

    def params(self) -> dict:
        t = self.technique()
        if t == "CV":
            return {"Ei": f"{self.cv_Ei.value()} V", "Ef": f"{self.cv_Ef.value()} V",
                    "Scan rate": f"{self.cv_v.value()} V/s",
                    "Cycles": self.cv_cycles.value()}
        if t == "LSV":
            return {"Ei": f"{self.lsv_Ei.value()} V", "Ef": f"{self.lsv_Ef.value()} V",
                    "Scan rate": f"{self.lsv_v.value()} V/s"}
        if t == "CA":
            return {"Estep": f"{self.ca_Estep.value()} V",
                    "Duration": f"{self.ca_duration.value()} s"}
        return {"Duration": f"{self.ocp_duration.value()} s"}

    def set_running(self, running: bool):
        self.run_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.technique_combo.setEnabled(not running)
        self.stack.setEnabled(not running)

    def set_connected(self, connected: bool):
        self.run_btn.setEnabled(connected)

    # ── internal ──────────────────────────────────────────────────────────────

    def _switch_page(self, index: int):
        self.stack.setCurrentIndex(index)

    def _on_run(self):
        self.run_requested.emit(self.command())


# ── PlotWidget ─────────────────────────────────────────────────────────────────
class PlotWidget(QWidget):
    """Live-updating Matplotlib canvas, redrawn at ≤10 Hz."""

    BG   = "#1e1e2e"
    FG   = "#cdd6f4"
    LINE = "#89b4fa"
    GRID = "#313244"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._E: list[float] = []
        self._I: list[float] = []
        self._t: list[float] = []
        self._technique = "CV"
        self._dirty = False

        fig = Figure(facecolor=self.BG)
        self._canvas = FigureCanvasQTAgg(fig)
        self._ax = fig.add_subplot(111)
        self._apply_style()
        self._line, = self._ax.plot([], [], color=self.LINE, linewidth=1.5)

        toolbar = NavigationToolbar2QT(self._canvas, self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(toolbar)
        layout.addWidget(self._canvas)

        self._timer = QTimer(self)
        self._timer.setInterval(100)   # 10 Hz cap
        self._timer.timeout.connect(self._redraw)
        self._timer.start()

    def _apply_style(self):
        ax = self._ax
        ax.set_facecolor(self.BG)
        ax.tick_params(colors=self.FG)
        ax.xaxis.label.set_color(self.FG)
        ax.yaxis.label.set_color(self.FG)
        ax.title.set_color(self.FG)
        ax.grid(True, color=self.GRID, linestyle="--", linewidth=0.5)
        for spine in ax.spines.values():
            spine.set_edgecolor(self.GRID)

    def reset(self, technique: str):
        self._technique = technique
        self._E.clear(); self._I.clear(); self._t.clear()
        ax = self._ax
        ax.cla()
        self._apply_style()
        labels = {
            "CV":  ("E  (V)",   "I  (A)",   "Cyclic Voltammetry"),
            "LSV": ("E  (V)",   "I  (A)",   "Linear Sweep Voltammetry"),
            "CA":  ("t  (s)",   "I  (A)",   "Chronoamperometry"),
            "OCP": ("t  (s)",   "E  (V)",   "Open Circuit Potential"),
        }
        xl, yl, title = labels.get(technique, ("x", "y", technique))
        ax.set_xlabel(xl); ax.set_ylabel(yl); ax.set_title(title)
        self._line, = ax.plot([], [], color=self.LINE, linewidth=1.5)
        self._canvas.draw()

    def add_point(self, E: float, I: float, t: float):
        self._E.append(E); self._I.append(I); self._t.append(t)
        self._dirty = True

    def _redraw(self):
        if not self._dirty:
            return
        self._dirty = False
        if self._technique in ("CV", "LSV"):
            self._line.set_data(self._E, self._I)
        elif self._technique == "CA":
            self._line.set_data(self._t, self._I)
        elif self._technique == "OCP":
            self._line.set_data(self._t, self._E)
        self._ax.relim()
        self._ax.autoscale_view()
        self._canvas.draw_idle()


# ── SerialMonitorWindow ────────────────────────────────────────────────────────
class SerialMonitorWindow(QWidget):
    """
    Standalone debug window that shows every raw TX/RX serial line.
    TX lines are shown in green, RX data points in dim grey,
    RX status/error lines in blue/red.
    """

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("Serial Monitor")
        self.resize(600, 450)

        self._tx_count = 0
        self._rx_count = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Counter label
        self._counter = QLabel("TX: 0   RX: 0")
        self._counter.setStyleSheet("color: #6c7086; font-size: 9pt;")
        layout.addWidget(self._counter)

        # Traffic log
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setObjectName("serial_log")
        layout.addWidget(self._log)

        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear)
        layout.addWidget(clear_btn)

    def _ts(self) -> str:
        return datetime.now().strftime("%H:%M:%S.%f")[:-3]

    def _append(self, html: str):
        self._log.append(html)
        # Auto-scroll to bottom
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

    @pyqtSlot(str)
    def on_tx(self, line: str):
        self._tx_count += 1
        self._counter.setText(f"TX: {self._tx_count}   RX: {self._rx_count}")
        self._append(
            f'<span style="color:#6c7086">[{self._ts()}]</span> '
            f'<span style="color:#a6e3a1"><b>TX</b> {line}</span>'
        )

    @pyqtSlot(str)
    def on_rx(self, line: str):
        self._rx_count += 1
        self._counter.setText(f"TX: {self._tx_count}   RX: {self._rx_count}")
        # Colour by content type
        if line.startswith("ERR"):
            colour = "#f38ba8"   # red
        elif line in ("OK", "DONE", "PONG"):
            colour = "#89b4fa"   # blue
        else:
            colour = "#6c7086"   # dim grey (data points)
        self._append(
            f'<span style="color:#6c7086">[{self._ts()}]</span> '
            f'<span style="color:{colour}"><b>RX</b> {line}</span>'
        )

    def _clear(self):
        self._log.clear()
        self._tx_count = 0
        self._rx_count = 0
        self._counter.setText("TX: 0   RX: 0")


# ── MainWindow ─────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Open-Source Potentiostat")
        self.resize(1150, 720)

        self._logger = DataLogger()
        self._csv_path: str | None = None
        self._running = False

        # Serial worker on its own thread
        self._thread = QThread(self)
        self._worker = SerialWorker()
        self._worker.moveToThread(self._thread)
        self._thread.start()

        self._worker.connected.connect(self._on_connected)
        self._worker.disconnected.connect(self._on_disconnected)
        self._worker.data_point.connect(self._on_data_point)
        self._worker.status_msg.connect(self._on_status_msg)
        self._worker.error.connect(self._on_error)

        # Serial monitor (separate debug window)
        self._monitor = SerialMonitorWindow()
        self._worker.raw_tx.connect(self._monitor.on_tx)
        self._worker.raw_rx.connect(self._monitor.on_rx)

        self._build_ui()
        self._refresh_ports()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # ── Left panel ────────────────────────────────────────────────────────
        left = QWidget()
        left.setFixedWidth(230)
        left_vbox = QVBoxLayout(left)
        left_vbox.setContentsMargins(0, 0, 0, 0)
        left_vbox.setSpacing(8)

        # Connection frame
        conn = QFrame(); conn.setObjectName("panel")
        cl = QVBoxLayout(conn); cl.setSpacing(6)

        top_row = QHBoxLayout()
        self.led = QLabel("●")
        self.led.setObjectName("led_disconnected")
        top_row.addWidget(self.led)
        top_row.addWidget(QLabel("Connection"), 1)
        cl.addLayout(top_row)

        port_row = QHBoxLayout()
        self.port_combo = QComboBox()
        self.refresh_btn = QPushButton("R")
        self.refresh_btn.setFixedWidth(28)
        self.refresh_btn.setToolTip("Refresh serial ports")
        self.refresh_btn.clicked.connect(self._refresh_ports)
        port_row.addWidget(self.port_combo, 1)
        port_row.addWidget(self.refresh_btn)
        cl.addLayout(port_row)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("connect_btn")
        self.connect_btn.clicked.connect(self._toggle_connection)
        cl.addWidget(self.connect_btn)

        monitor_btn = QPushButton("Serial Monitor")
        monitor_btn.setToolTip("Open raw serial traffic debug window")
        monitor_btn.clicked.connect(self._show_monitor)
        cl.addWidget(monitor_btn)
        left_vbox.addWidget(conn)

        # Config panel frame
        cfg_frame = QFrame(); cfg_frame.setObjectName("panel")
        cfg_layout = QVBoxLayout(cfg_frame)
        cfg_layout.setContentsMargins(6, 6, 6, 6)
        self.config = ConfigPanel()
        self.config.run_requested.connect(self._on_run_requested)
        self.config.stop_requested.connect(self._on_stop_requested)
        cfg_layout.addWidget(self.config)
        left_vbox.addWidget(cfg_frame, 1)

        root.addWidget(left)

        # ── Right panel (plot + log) ──────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Vertical)

        self.plot = PlotWidget()
        splitter.addWidget(self.plot)

        self.log_box = QTextEdit()
        self.log_box.setObjectName("serial_log")
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Serial traffic will appear here…")
        splitter.addWidget(self.log_box)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._set_status("Not connected")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _refresh_ports(self):
        self.port_combo.clear()
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo.addItems(ports if ports else ["(no ports)"])

    def _log(self, text: str):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.log_box.append(f"[{ts}]  {text}")

    def _set_status(self, msg: str):
        self.status_bar.showMessage(msg)

    def _set_led(self, connected: bool):
        name = "led_connected" if connected else "led_disconnected"
        self.led.setObjectName(name)
        self.led.style().unpolish(self.led)
        self.led.style().polish(self.led)

    # ── Connection ────────────────────────────────────────────────────────────

    def _toggle_connection(self):
        if self._worker._serial and self._worker._serial.is_open:
            self._worker.disconnect_now()  # direct call — safe while read_loop is blocking
        else:
            port = self.port_combo.currentText()
            self._log(f"→ Connecting to {port}…")
            self._set_status(f"Connecting to {port}…")
            self.connect_btn.setEnabled(False)
            self._worker.connect_requested.emit(port)

    @pyqtSlot()
    def _on_connected(self):
        self._set_led(True)
        self.connect_btn.setText("Disconnect")
        self.connect_btn.setEnabled(True)
        self.config.set_connected(True)
        self._log("← PONG — connected")
        self._set_status("Connected — IDLE")

    @pyqtSlot()
    def _on_disconnected(self):
        self._set_led(False)
        self.connect_btn.setText("Connect")
        self.connect_btn.setEnabled(True)
        self.config.set_connected(False)
        self._log("— Disconnected")
        self._set_status("Not connected")
        if self._running:
            self._end_experiment(save=True)

    # ── Experiment control ────────────────────────────────────────────────────

    def _on_run_requested(self, cmd: str):
        # Choose save file before starting
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Experiment Data", "", "CSV Files (*.csv)"
        )
        if not path:
            return   # user cancelled
        if not path.lower().endswith(".csv"):
            path += ".csv"

        technique = self.config.technique()
        self._logger.start(path, technique, self.config.params())
        self._csv_path = path
        self._running = True

        self.plot.reset(technique)
        self.config.set_running(True)
        self._log(f"→ {cmd}")
        self._log(f"  Saving to: {path}")
        self._set_status("Running…")

        # Open the serial monitor automatically so all traffic is visible
        self._show_monitor()

        self._worker.send_command(cmd)

    def _on_stop_requested(self):
        self._log("→ STOP")
        self._worker.send_command("STOP")
        self._end_experiment(save=True)

    def _end_experiment(self, save: bool = True):
        self._running = False
        self.config.set_running(False)
        if save and self._logger.is_open:
            self._logger.stop()
            self._log(f"  Data saved → {self._csv_path}")
        self._csv_path = None
        self._set_status("Connected — IDLE")

    # ── Serial responses ──────────────────────────────────────────────────────

    @pyqtSlot(float, float, float)
    def _on_data_point(self, E: float, I: float, t: float):
        self.plot.add_point(E, I, t)
        self._logger.log(E, I, t)

    @pyqtSlot(str)
    def _on_status_msg(self, msg: str):
        self._log(f"← {msg}")
        if msg == "DONE":
            self._end_experiment(save=True)
            self._set_status("Connected — experiment complete")
        elif msg.startswith("ERR"):
            QMessageBox.warning(self, "Device Error", msg)
            self._end_experiment(save=True)
            self._set_status(f"Error: {msg}")

    @pyqtSlot()
    def _show_monitor(self):
        self._monitor.show()
        self._monitor.raise_()
        self._monitor.activateWindow()

    @pyqtSlot(str)
    def _on_error(self, msg: str):
        self._log(f"[ERROR] {msg}")
        QMessageBox.critical(self, "Connection Error", msg)
        self._set_led(False)
        self.connect_btn.setText("Connect")
        self.connect_btn.setEnabled(True)
        self.config.set_connected(False)
        self._set_status("Not connected")

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._worker.disconnect_requested.emit()
        self._thread.quit()
        self._thread.wait(2000)
        event.accept()
