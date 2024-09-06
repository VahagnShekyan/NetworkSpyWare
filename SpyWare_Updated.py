import sys
import psutil
import time
import socket
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
                             QPushButton, QFileDialog, QMessageBox, QSystemTrayIcon, QMenu,
                             QAction, QInputDialog)
from PyQt5.QtCore import QTimer, Qt, QSettings
from PyQt5.QtGui import QColor, QFont, QIcon
import pyqtgraph as pg
import csv
import os


def bytes_to_mb(bytes_value):
    return bytes_value / (1024 * 1024)


class NetworkMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Enhanced Network Monitor")
        self.setGeometry(100, 100, 1600, 900)

        self.settings = QSettings("YourCompany", "NetworkMonitor")
        self.dark_mode = self.settings.value("dark_mode", True, type=bool)
        self.selected_interface = self.settings.value("selected_interface", "", type=str)
        self.auto_start = self.settings.value("auto_start", False, type=bool)

        self.setup_ui()
        self.setup_tray_icon()

        self.data = {key: {"times": [], "values": []} for key in self.graphs.keys()}
        self.start_time = time.time()
        self.last_total_download = 0
        self.last_total_upload = 0
        self.last_process_bytes = {}
        self.max_data_points = 3600
        self.alert_threshold = None
        self.bandwidth_alert_threshold = None  # Initially, alert system is off
        self.bandwidth_alert_period = None  # Set the time frame for alert monitoring

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(1000)

    def setup_ui(self):
        self.apply_theme()

        main_layout = QHBoxLayout()

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        controls_layout = QHBoxLayout()

        self.time_range_combo = QComboBox()
        self.time_range_combo.addItems(["1 minute", "5 minutes", "15 minutes", "1 hour"])
        self.time_range_combo.currentIndexChanged.connect(self.update_time_range)
        controls_layout.addWidget(self.time_range_combo)

        self.export_button = QPushButton("Export Data")
        self.export_button.clicked.connect(self.export_data)
        controls_layout.addWidget(self.export_button)

        self.alert_threshold_combo = QComboBox()
        self.alert_threshold_combo.addItems(["No Alert", "1 MB/s", "5 MB/s", "10 MB/s", "Custom"])
        self.alert_threshold_combo.currentIndexChanged.connect(self.set_alert_threshold)
        controls_layout.addWidget(QLabel("Alert Threshold:"))
        controls_layout.addWidget(self.alert_threshold_combo)

        self.interface_combo = QComboBox()
        self.interface_combo.addItems(self.get_network_interfaces())
        self.interface_combo.setCurrentText(self.selected_interface)
        self.interface_combo.currentTextChanged.connect(self.update_selected_interface)
        controls_layout.addWidget(QLabel("Network Interface:"))
        controls_layout.addWidget(self.interface_combo)

        self.theme_toggle = QPushButton("Toggle Theme")
        self.theme_toggle.clicked.connect(self.toggle_theme)
        controls_layout.addWidget(self.theme_toggle)

        self.alert_settings_button = QPushButton("Set Bandwidth Alert")
        self.alert_settings_button.clicked.connect(self.set_bandwidth_alert_conditions)
        controls_layout.addWidget(self.alert_settings_button)

        left_layout.addLayout(controls_layout)

        self.graphs = {
            "download_speed": self.create_plot('g'),
            "upload_speed": self.create_plot('r'),
            "total_download": self.create_plot('c'),
            "total_upload": self.create_plot('m')
        }
        for graph in self.graphs.values():
            left_layout.addWidget(graph)

        main_layout.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.stats_label = QLabel()
        right_layout.addWidget(self.stats_label)

        self.process_table = QTableWidget()
        self.process_table.setColumnCount(4)
        self.process_table.setHorizontalHeaderLabels(["Process", "Download (MB/s)", "Upload (MB/s)", "Total (MB/s)"])
        self.process_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.process_table.setAlternatingRowColors(True)
        right_layout.addWidget(self.process_table)

        main_layout.addWidget(right_panel)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def setup_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon_path = "icon.png"
        if not os.path.exists(icon_path):
            icon_path = None  # or set a default icon here
        self.tray_icon.setIcon(QIcon(icon_path))

        tray_menu = QMenu()
        show_action = QAction("Show", self)
        quit_action = QAction("Exit", self)
        show_action.triggered.connect(self.show)
        quit_action.triggered.connect(self.close)
        tray_menu.addAction(show_action)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def apply_theme(self):
        if self.dark_mode:
            self.setStyleSheet("""
                QMainWindow, QWidget { background-color: #1e1e1e; color: #ffffff; }
                QTableWidget { 
                    gridline-color: #3a3a3a; 
                    color: #ffffff;
                    background-color: #2b2b2b;
                    alternate-background-color: #323232;
                }
                QHeaderView::section { 
                    background-color: #3a3a3a; 
                    color: #ffffff; 
                    padding: 5px;
                    border: 1px solid #4a4a4a;
                }
                QTableCornerButton::section { background-color: #3a3a3a; }
                QComboBox, QPushButton { 
                    background-color: #3a3a3a; 
                    color: #ffffff; 
                    border: 1px solid #555555;
                    padding: 5px;
                    min-width: 6em;
                }
                QComboBox::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 15px;
                    border-left-width: 1px;
                    border-left-color: #555555;
                    border-left-style: solid;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                }
                QLabel { color: #ffffff; }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow, QWidget { background-color: #f0f0f0; color: #000000; }
                QTableWidget { 
                    gridline-color: #d0d0d0; 
                    color: #000000;
                    background-color: #ffffff;
                    alternate-background-color: #f5f5f5;
                }
                QHeaderView::section { 
                    background-color: #e0e0e0; 
                    color: #000000; 
                    padding: 5px;
                    border: 1px solid #c0c0c0;
                }
                QTableCornerButton::section { background-color: #e0e0e0; }
                QComboBox, QPushButton { 
                    background-color: #ffffff; 
                    color: #000000; 
                    border: 1px solid #c0c0c0;
                    padding: 5px;
                    min-width: 6em;
                }
                QComboBox::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 15px;
                    border-left-width: 1px;
                    border-left-color: #c0c0c0;
                    border-left-style: solid;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
                QLabel { color: #000000; }
            """)

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.apply_theme()
        self.settings.setValue("dark_mode", self.dark_mode)

    def get_network_interfaces(self):
        return list(psutil.net_if_stats().keys())

    def update_selected_interface(self, interface):
        self.selected_interface = interface
        self.settings.setValue("selected_interface", interface)

    def create_plot(self, color):
        plot = pg.PlotWidget()
        plot.showGrid(x=True, y=True)
        plot.setBackground(None)
        plot.getAxis('left').setPen(pg.mkPen(color='#ffffff' if self.dark_mode else '#000000'))
        plot.getAxis('bottom').setPen(pg.mkPen(color='#ffffff' if self.dark_mode else '#000000'))
        curve = plot.plot(pen=color)
        return plot

    def update_data(self):
        current_time = time.time() - self.start_time

        if self.selected_interface:
            net_io = psutil.net_io_counters(pernic=True)[self.selected_interface]
        else:
            net_io = psutil.net_io_counters()

        download_speed = bytes_to_mb(net_io.bytes_recv - self.last_total_download)
        upload_speed = bytes_to_mb(net_io.bytes_sent - self.last_total_upload)
        total_download = bytes_to_mb(net_io.bytes_recv)
        total_upload = bytes_to_mb(net_io.bytes_sent)

        if self.alert_threshold and (download_speed > self.alert_threshold or upload_speed > self.alert_threshold):
            self.show_alert(f"Network usage exceeded {self.alert_threshold} MB/s!")

        if self.bandwidth_alert_threshold and self.bandwidth_alert_period:
            self.check_bandwidth_alert(download_speed, upload_speed)

        for key, value in zip(self.data.keys(), [download_speed, upload_speed, total_download, total_upload]):
            self.data[key]["times"].append(current_time)
            self.data[key]["values"].append(value)

        for key, graph in self.graphs.items():
            graph.getPlotItem().curves[0].setData(self.data[key]["times"], self.data[key]["values"])

        self.stats_label.setText(f"Download Speed: {download_speed:.2f} MB/s | Upload Speed: {upload_speed:.2f} MB/s\n"
                                 f"Total Downloaded: {total_download:.2f} MB | Total Uploaded: {total_upload:.2f} MB")

        processes = self.get_process_network_usage()
        self.update_process_table(processes)

        self.last_total_download = net_io.bytes_recv
        self.last_total_upload = net_io.bytes_sent

        for key in self.data.keys():
            if len(self.data[key]["times"]) > self.max_data_points:
                self.data[key]["times"] = self.data[key]["times"][-self.max_data_points:]
                self.data[key]["values"] = self.data[key]["values"][-self.max_data_points:]

    def get_process_network_usage(self):
        # Dictionary to accumulate network usage per process
        process_network_usage = {}

        # Get active network connections (only 'inet' type to ignore local sockets)
        connections = psutil.net_connections(kind='inet')

        # Iterate over each connection
        for conn in connections:
            if conn.status == psutil.CONN_ESTABLISHED and conn.pid:  # Only consider established connections with a valid PID
                try:
                    proc = psutil.Process(conn.pid)
                    with proc.oneshot():
                        # Get process name
                        process_name = proc.name()
                        if process_name not in process_network_usage:
                            process_network_usage[process_name] = {'download': 0, 'upload': 0}

                        # Accumulate network usage data based on connection type (upload/download)
                        if conn.raddr:  # If there's a remote address, it's uploading
                            process_network_usage[process_name]['upload'] += conn.raddr[1]  # Upload (assuming raddr represents remote)
                        if conn.laddr:  # If there's a local address, it's downloading
                            process_network_usage[process_name]['download'] += conn.laddr[1]  # Download (assuming laddr represents local)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass

        # Convert usage to MB and return sorted by total traffic
        sorted_processes = sorted(process_network_usage.items(),
                                  key=lambda x: x[1]['download'] + x[1]['upload'],
                                  reverse=True)

        # Prepare the process list for table updates
        process_list = []
        for process_name, usage in sorted_processes:
            process_list.append({
                'name': process_name,
                'download': bytes_to_mb(usage['download']),
                'upload': bytes_to_mb(usage['upload'])
            })

        return process_list

    def update_process_table(self, processes):
        self.process_table.setRowCount(len(processes))
        for i, proc in enumerate(processes):
            name_item = QTableWidgetItem(proc['name'])
            download_item = QTableWidgetItem(f"{proc['download']:.2f}")
            upload_item = QTableWidgetItem(f"{proc['upload']:.2f}")
            total_item = QTableWidgetItem(f"{proc['download'] + proc['upload']:.2f}")

            font = QFont()
            font.setBold(True)
            name_item.setFont(font)

            self.process_table.setItem(i, 0, name_item)
            self.process_table.setItem(i, 1, download_item)
            self.process_table.setItem(i, 2, upload_item)
            self.process_table.setItem(i, 3, total_item)

            total_usage = proc['download'] + proc['upload']
            if total_usage > 5:
                color = QColor(255, 100, 100)
                text_color = QColor(0, 0, 0)
            elif total_usage > 1:
                color = QColor(255, 255, 100)
                text_color = QColor(0, 0, 0)
            else:
                color = QColor(100, 255, 100)
                text_color = QColor(0, 0, 0)

            for j in range(4):
                item = self.process_table.item(i, j)
                item.setBackground(color)
                item.setForeground(text_color)

    def update_time_range(self):
        time_range = self.time_range_combo.currentText()
        if time_range == "1 minute":
            self.max_data_points = 60
        elif time_range == "5 minutes":
            self.max_data_points = 300
        elif time_range == "15 minutes":
            self.max_data_points = 900
        elif time_range == "1 hour":
            self.max_data_points = 3600

        if self.data["download_speed"]["times"]:
            x_min = max(0, self.data["download_speed"]["times"][-1] - self.max_data_points)
            x_max = self.data["download_speed"]["times"][-1]
            for graph in self.graphs.values():
                graph.getViewBox().setXRange(x_min, x_max)

    def export_data(self):
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Data", "", "CSV Files (*.csv)")
        if file_name:
            with open(file_name, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(
                    ["Time", "Download Speed (MB/s)", "Upload Speed (MB/s)", "Total Downloaded (MB)",
                     "Total Uploaded (MB)"])
                for i in range(len(self.data["download_speed"]["times"])):
                    writer.writerow([
                        self.data["download_speed"]["times"][i],
                        self.data["download_speed"]["values"][i],
                        self.data["upload_speed"]["values"][i],
                        self.data["total_download"]["values"][i],
                        self.data["total_upload"]["values"][i]
                    ])
            QMessageBox.information(self, "Export Successful", "Data has been exported successfully.")

    def set_alert_threshold(self):
        threshold_text = self.alert_threshold_combo.currentText()
        if threshold_text == "No Alert":
            self.alert_threshold = None
        elif threshold_text == "Custom":
            custom_threshold, ok = QInputDialog.getDouble(self, "Custom Alert Threshold", "Enter threshold (MB/s):")
            if ok:
                self.alert_threshold = custom_threshold
        else:
            self.alert_threshold = float(threshold_text.split()[0])

    def set_bandwidth_alert_conditions(self):
        period, ok1 = QInputDialog.getInt(self, "Set Alert Period", "Enter alert period (seconds):", 60, 1)
        if ok1:
            self.bandwidth_alert_period = period
        threshold, ok2 = QInputDialog.getDouble(self, "Set Bandwidth Threshold", "Enter threshold (MB):", 100)
        if ok2:
            self.bandwidth_alert_threshold = threshold

    def show_alert(self, message):
        QMessageBox.warning(self, "Network Alert", message)

    def check_bandwidth_alert(self, download_speed, upload_speed):
        current_time = time.time()
        self.data["total_bandwidth"] = self.data.get("total_bandwidth", []) + [
            (current_time, download_speed + upload_speed)]

        # Remove data points older than the alert period
        self.data["total_bandwidth"] = [
            (t, v) for t, v in self.data["total_bandwidth"]
            if current_time - t <= self.bandwidth_alert_period
        ]

        total_bandwidth = sum(v for _, v in self.data["total_bandwidth"])
        if total_bandwidth >= self.bandwidth_alert_threshold:
            self.show_alert(
                f"High bandwidth usage: {total_bandwidth:.2f} MB in the last {self.bandwidth_alert_period} seconds!")

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self, 'Exit', "Are you sure you want to exit?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.tray_icon.hide()
            event.accept()
        else:
            event.ignore()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = NetworkMonitor()
    window.show()
    sys.exit(app.exec_())
