import sys
import psutil
import time
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView
from PyQt5.QtCore import QTimer, Qt
import pyqtgraph as pg

def bytes_to_mb(bytes_value):
    return bytes_value / (1024 * 1024)

class NetworkMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Four-Graph Network Monitor")
        self.setGeometry(100, 100, 1600, 900)  # Increased size to accommodate 4 graphs

        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #2b2b2b; color: #ffffff; }
            QTableWidget { gridline-color: #3a3a3a; }
            QHeaderView::section { background-color: #3a3a3a; color: #ffffff; }
            QTableCornerButton::section { background-color: #3a3a3a; }
        """)

        main_layout = QHBoxLayout()

        # Left panel for graphs
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Download Speed graph
        self.download_speed_plot = self.create_plot("Download Speed (MB/s)", 'g')
        left_layout.addWidget(self.download_speed_plot)

        # Upload Speed graph
        self.upload_speed_plot = self.create_plot("Upload Speed (MB/s)", 'r')
        left_layout.addWidget(self.upload_speed_plot)

        # Total Download graph
        self.total_download_plot = self.create_plot("Total Data Downloaded (MB)", 'c')
        left_layout.addWidget(self.total_download_plot)

        # Total Upload graph
        self.total_upload_plot = self.create_plot("Total Data Uploaded (MB)", 'm')
        left_layout.addWidget(self.total_upload_plot)

        main_layout.addWidget(left_panel)

        # Right panel for process list and overall stats
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Overall network stats
        self.stats_label = QLabel()
        right_layout.addWidget(self.stats_label)

        # Process list
        self.process_table = QTableWidget()
        self.process_table.setColumnCount(4)
        self.process_table.setHorizontalHeaderLabels(["Process", "Download (MB/s)", "Upload (MB/s)", "Total (MB/s)"])
        self.process_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_layout.addWidget(self.process_table)

        main_layout.addWidget(right_panel)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Initialize data
        self.times = []
        self.download_speeds = []
        self.upload_speeds = []
        self.total_download = []
        self.total_upload = []
        self.start_time = time.time()
        self.last_total_download = 0
        self.last_total_upload = 0
        self.last_process_bytes = {}

        # Update timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(1000)  # Update every second

    def create_plot(self, title, color):
        plot = pg.PlotWidget(title=title)
        plot.setLabel('left', title)
        plot.setLabel('bottom', "Time (s)")
        plot.showGrid(x=True, y=True)
        plot.addLegend()
        curve = plot.plot(pen=color, name=title)
        return plot

    def update_data(self):
        current_time = time.time() - self.start_time
        self.times.append(current_time)

        # Get network stats
        net_io = psutil.net_io_counters()
        download_speed = bytes_to_mb(net_io.bytes_recv - self.last_total_download)  # MB/s
        upload_speed = bytes_to_mb(net_io.bytes_sent - self.last_total_upload)  # MB/s
        total_download = bytes_to_mb(net_io.bytes_recv)  # MB
        total_upload = bytes_to_mb(net_io.bytes_sent)  # MB

        self.download_speeds.append(download_speed)
        self.upload_speeds.append(upload_speed)
        self.total_download.append(total_download)
        self.total_upload.append(total_upload)

        # Update graphs
        self.download_speed_plot.getPlotItem().curves[0].setData(self.times, self.download_speeds)
        self.upload_speed_plot.getPlotItem().curves[0].setData(self.times, self.upload_speeds)
        self.total_download_plot.getPlotItem().curves[0].setData(self.times, self.total_download)
        self.total_upload_plot.getPlotItem().curves[0].setData(self.times, self.total_upload)

        # Update stats label
        self.stats_label.setText(f"Download Speed: {download_speed:.2f} MB/s | Upload Speed: {upload_speed:.2f} MB/s\n"
                                 f"Total Downloaded: {total_download:.2f} MB | Total Uploaded: {total_upload:.2f} MB")

        # Update process list (same as before)
        processes = []
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                with proc.oneshot():
                    net_io = proc.io_counters()
                    pid = proc.pid
                    if pid in self.last_process_bytes:
                        last_read, last_write = self.last_process_bytes[pid]
                        read_speed = bytes_to_mb(net_io.read_bytes - last_read)
                        write_speed = bytes_to_mb(net_io.write_bytes - last_write)
                    else:
                        read_speed = write_speed = 0
                    self.last_process_bytes[pid] = (net_io.read_bytes, net_io.write_bytes)
                    processes.append({
                        'name': proc.name(),
                        'download': read_speed,
                        'upload': write_speed,
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        processes.sort(key=lambda x: x['download'] + x['upload'], reverse=True)
        self.process_table.setRowCount(len(processes))

        for i, proc in enumerate(processes):
            self.process_table.setItem(i, 0, QTableWidgetItem(proc['name']))
            self.process_table.setItem(i, 1, QTableWidgetItem(f"{proc['download']:.2f}"))
            self.process_table.setItem(i, 2, QTableWidgetItem(f"{proc['upload']:.2f}"))
            self.process_table.setItem(i, 3, QTableWidgetItem(f"{proc['download'] + proc['upload']:.2f}"))

        # Prepare for next update
        self.last_total_download = net_io.bytes_recv
        self.last_total_upload = net_io.bytes_sent

        # Keep only last 60 seconds of data
        if len(self.times) > 60:
            self.times = self.times[-60:]
            self.download_speeds = self.download_speeds[-60:]
            self.upload_speeds = self.upload_speeds[-60:]
            self.total_download = self.total_download[-60:]
            self.total_upload = self.total_upload[-60:]

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = NetworkMonitor()
    window.show()
    sys.exit(app.exec_())
