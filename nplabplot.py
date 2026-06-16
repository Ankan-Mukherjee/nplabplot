import sys
import os
import numpy as np
import pyqtgraph as pg
import pyqtgraph.exporters
from pyqtgraph.Qt import QtCore, QtGui
from qcodes_loop.data.data_set import load_data
from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QWidget, QSplitter, QVBoxLayout,
    QPushButton, QLabel, QHBoxLayout, QLineEdit, QComboBox,
    QFileDialog, QSizePolicy, QTabWidget, QToolButton
)
from PyQt5.QtCore import Qt


class LineDrawerTab(QWidget):
    def __init__(self):
        super().__init__()

        self.loaded_folder_path = None
        self.setAcceptDrops(True)

        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')

        self.color_map = {
            'Black': 'k',
            'Red': 'r',
            'Green': 'g',
            'Blue': 'b'
        }

        self.style_map = {
            'Line': QtCore.Qt.SolidLine,
        }

        self.style_options = list(self.style_map.keys()) + ['Scatter', 'Scatter_line']

        main_layout = QHBoxLayout(self)

        splitter = QSplitter(QtCore.Qt.Vertical)
        main_layout.addWidget(splitter)

        control_container = QWidget()
        container_v_layout = QVBoxLayout(control_container)
        container_v_layout.setContentsMargins(5, 5, 5, 5)

        control_row_widget = QWidget()
        control_row_layout = QHBoxLayout(control_row_widget)
        control_row_layout.setContentsMargins(0, 0, 0, 0)

        self.open_btn = QPushButton("Open Folder")
        self.open_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.open_btn.clicked.connect(self.open_folder)

        self.x_dropdown = QComboBox()
        self.y_dropdown = QComboBox()
        self.z_dropdown = QComboBox()

        self.color_dropdown = QComboBox()
        self.style_dropdown = QComboBox()

        self.color_dropdown.addItems(self.color_map.keys())
        self.style_dropdown.addItems(self.style_options)

        for dropdown in [
            self.x_dropdown, self.y_dropdown, self.z_dropdown,
            self.color_dropdown, self.style_dropdown
        ]:
            dropdown.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.x_dropdown.activated.connect(self.change_x)
        self.y_dropdown.activated.connect(self.change_y)
        self.z_dropdown.activated.connect(self.change_z)
        self.color_dropdown.currentTextChanged.connect(self.update_pen)
        self.style_dropdown.currentTextChanged.connect(self.update_pen)

        self.x_label = QLabel("X:")
        self.y_label = QLabel("Y:")
        self.z_label = QLabel("Z:")
        self.color_label = QLabel("Color:")
        self.style_label = QLabel("Style:")

        control_row_layout.addWidget(self.open_btn, 2)
        control_row_layout.addWidget(self.x_label)
        control_row_layout.addWidget(self.x_dropdown, 2)
        control_row_layout.addWidget(self.y_label)
        control_row_layout.addWidget(self.y_dropdown, 2)

        control_row_layout.addWidget(self.z_label)
        control_row_layout.addWidget(self.z_dropdown, 2)

        control_row_layout.addWidget(self.color_label)
        control_row_layout.addWidget(self.color_dropdown, 2)
        control_row_layout.addWidget(self.style_label)
        control_row_layout.addWidget(self.style_dropdown, 2)

        self.folder_label = QLineEdit("No folder loaded")
        self.folder_label.setReadOnly(True)
        # self.folder_label.setStyleSheet(
        #     "color: #444; font-weight: bold; font-size: 11px; padding-left: 5px;"
        # )

        container_v_layout.addWidget(control_row_widget)
        container_v_layout.addWidget(self.folder_label)

        self.z_label.setVisible(False)
        self.z_dropdown.setVisible(False)
        self.color_label.setVisible(False)
        self.color_dropdown.setVisible(False)
        self.style_label.setVisible(False)
        self.style_dropdown.setVisible(False)

        self.is_2d = False

        self.win = pg.GraphicsLayoutWidget()

        self.plot = self.win.addPlot(row=0, col=0)
        self.plot.setAspectLocked(False)

        self.img = pg.ImageItem()
        self.plot.addItem(self.img)

        self.line = pg.PlotDataItem(pen=pg.mkPen('b', width=2))
        self.plot.addItem(self.line)

        self.hist = pg.HistogramLUTItem()
        self.hist.setImageItem(self.img)
        self.hist.gradient.setColorMap(pg.colormap.get('viridis'))
        self.win.addItem(self.hist, row=0, col=1)

        self.copy_action = QtGui.QAction("Copy to clipboard", self.plot)
        self.copy_action.triggered.connect(self.copy_to_clipboard)
        self.plot.vb.menu.addSeparator()
        self.plot.vb.menu.addAction(self.copy_action)

        self.img.setVisible(False)
        self.line.setVisible(False)
        self.hist.setVisible(False)

        splitter.addWidget(control_container)
        splitter.addWidget(self.win)
        splitter.setSizes([80, 750])

    def copy_to_clipboard(self):
        pixmap = self.win.grab()
        QApplication.clipboard().setPixmap(pixmap)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                folder_path = str(url.toLocalFile())
                if os.path.isdir(folder_path):
                    self.load_dataset(folder_path)
                    break
            event.acceptProposedAction()

    def open_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            self.load_dataset(folder_path)

    def get_axis_label(self, key):
        if not hasattr(self, 'data') or key not in self.data.arrays:
            return key
        arr = self.data.arrays[key]
        label = getattr(arr, 'label', key) or key
        unit = getattr(arr, 'unit', '')
        return f"{label} ({unit})" if unit else label

    def update_axes_labels(self):
        x_key = self.x_dropdown.currentText()
        y_key = self.y_dropdown.currentText()

        if x_key:
            self.plot.setLabel('bottom', self.get_axis_label(x_key))

        if self.is_2d:
            z_key = self.z_dropdown.currentText()
            if y_key:
                self.plot.setLabel('left', self.get_axis_label(y_key))
            if z_key:
                self.hist.axis.setLabel(self.get_axis_label(z_key))
        else:
            if y_key:
                self.plot.setLabel('left', self.get_axis_label(y_key))

    def load_dataset(self, folder_path):
        folder_path = folder_path.strip().rstrip('\\').rstrip('/')

        try:
            abs_path = os.path.abspath(folder_path)
            self.data = load_data(abs_path)
            self.loaded_folder_path = abs_path
            self.folder_label.setText(f"{abs_path}")
            window = self.window()
            if hasattr(window, "setCurrentTabName"):
                window.setCurrentTabName(os.path.basename(abs_path))
        except Exception as e:
            print(f"Failed to load dataset from {folder_path}: {e}")
            self.folder_label.setText("Error loading selected folder")
            return

        data_list = list(self.data.arrays.keys())
        data_arrays = list(self.data.arrays.values())

        self.is_2d = any(arr[:].ndim >= 2 for arr in data_arrays)

        self.x_dropdown.blockSignals(True)
        self.y_dropdown.blockSignals(True)
        self.z_dropdown.blockSignals(True)

        self.x_dropdown.clear()
        self.y_dropdown.clear()
        self.z_dropdown.clear()

        self.x_dropdown.addItems(data_list)
        self.y_dropdown.addItems(data_list)
        self.z_dropdown.addItems(data_list)

        if self.is_2d:
            self.z_label.setVisible(True)
            self.z_dropdown.setVisible(True)
            self.color_label.setVisible(False)
            self.color_dropdown.setVisible(False)
            self.style_label.setVisible(False)
            self.style_dropdown.setVisible(False)

            if len(data_arrays) >= 3:
                self.x_dropdown.setCurrentText(data_list[1])
                self.y_dropdown.setCurrentText(data_list[0])
                self.z_dropdown.setCurrentText(data_list[2])
        else:
            self.z_label.setVisible(False)
            self.z_dropdown.setVisible(False)
            self.color_label.setVisible(True)
            self.color_dropdown.setVisible(True)
            self.style_label.setVisible(True)
            self.style_dropdown.setVisible(True)

            if len(data_arrays) >= 2:
                self.x_dropdown.setCurrentText(data_list[0])
                self.y_dropdown.setCurrentText(data_list[1])

        self.x_dropdown.blockSignals(False)
        self.y_dropdown.blockSignals(False)
        self.z_dropdown.blockSignals(False)

        self.sync_active_arrays()
        self.update_plot()

    def sync_active_arrays(self):
        if not hasattr(self, 'data'):
            return

        x_key = self.x_dropdown.currentText()
        y_key = self.y_dropdown.currentText()
        z_key = self.z_dropdown.currentText()

        self.X = self.data.arrays[x_key][:] if x_key in self.data.arrays else None
        self.Y = self.data.arrays[y_key][:] if y_key in self.data.arrays else None

        if self.is_2d and z_key in self.data.arrays:
            self.Z = self.data.arrays[z_key][:].T
        else:
            self.Z = None

    def update_pen(self, _=None):
        if hasattr(self, 'is_2d') and not self.is_2d:
            color_name = self.color_dropdown.currentText()
            style_name = self.style_dropdown.currentText()
            c = self.color_map.get(color_name, 'b')

            pen = None
            symbol = None

            if style_name == 'Scatter':
                pen = None
                symbol = 'o'
            elif style_name == 'Scatter_line':
                pen = pg.mkPen(color=c, style=QtCore.Qt.SolidLine, width=2)
                symbol = 'o'
            else:
                s = self.style_map.get(style_name, QtCore.Qt.SolidLine)
                pen = pg.mkPen(color=c, style=s, width=2)
                symbol = None

            self.line.setPen(pen)
            self.line.setSymbol(symbol)

            if symbol:
                self.line.setSymbolBrush(c)
                self.line.setSymbolPen(c)
                self.line.setSymbolSize(7)

    def update_plot(self):
        if not hasattr(self, 'X') or self.X is None or self.Y is None:
            return

        self.update_axes_labels()

        if self.is_2d and self.Z is not None:
            self.img.setVisible(True)
            self.hist.setVisible(True)
            self.line.setVisible(False)

            x_vec = self.X[0] if self.X.ndim > 1 else self.X
            y_vec = self.Y[:, 0] if self.Y.ndim > 1 else self.Y

            valid_x = x_vec[~np.isnan(x_vec)]
            valid_y = y_vec[~np.isnan(y_vec)]

            if len(valid_x) < 2 or len(valid_y) < 2 or np.isnan(self.Z).all():
                return

            dx = (valid_x[-1] - valid_x[0]) / (len(valid_x) - 1)
            dy = (valid_y[-1] - valid_y[0]) / (len(valid_y) - 1)

            Zdisp = self.Z

            transform = QtGui.QTransform()
            transform.translate(valid_x[0] - 0.5 * dx, valid_y[0] - 0.5 * dy)
            transform.scale(dx, dy)

            self.img.setImage(Zdisp, autoLevels=False)
            self.img.setTransform(transform)

            self.plot.setXRange(np.nanmin(valid_x), np.nanmax(valid_x), padding=0.04)
            self.plot.setYRange(np.nanmin(valid_y), np.nanmax(valid_y), padding=0.04)

            p5, p95 = np.nanpercentile(Zdisp, [5, 95])
            if p5 == p95:
                p5 -= 0.1
                p95 += 0.1
            self.hist.setLevels(p5, p95)

        else:
            self.img.setVisible(False)
            self.hist.setVisible(False)
            self.line.setVisible(True)

            self.update_pen()

            x_arr = self.X.flatten() if self.X.ndim > 1 else self.X
            y_arr = self.Y.flatten() if self.Y.ndim > 1 else self.Y

            min_len = min(len(x_arr), len(y_arr))
            x_arr, y_arr = x_arr[:min_len], y_arr[:min_len]

            mask = ~np.isnan(x_arr) & ~np.isnan(y_arr)
            clean_x = x_arr[mask]
            clean_y = y_arr[mask]

            if len(clean_x) == 0:
                return

            self.line.setData(clean_x, clean_y)
            self.plot.setXRange(np.nanmin(clean_x), np.nanmax(clean_x), padding=0.04)
            self.plot.setYRange(np.nanmin(clean_y), np.nanmax(clean_y), padding=0.04)

    def change_x(self, index):
        self.sync_active_arrays()
        self.update_plot()

    def change_y(self, index):
        self.sync_active_arrays()
        self.update_plot()

    def change_z(self, index):
        self.sync_active_arrays()
        self.update_plot()


class LineDrawerApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("NPLab Data Plotter")
        self.setGeometry(100, 100, 1000, 650)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.setCentralWidget(self.tabs)

        self.plus_btn = QToolButton()
        self.plus_btn.setText("+")
        self.plus_btn.setFixedSize(30, 28)
        self.plus_btn.clicked.connect(self.add_tab)

        self.tabs.setCornerWidget(self.plus_btn, Qt.TopRightCorner)

        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #bdbdbd;
                top: -1px;
            }

            QTabBar {
                qproperty-drawBase: 0;
            }

            QTabBar::tab {
                background: #e8e8e8;
                border: 1px solid #bdbdbd;
                border-bottom: none;
                padding: 3px 8px;
                margin-right: 2px;
                min-width: 105px;
                min-height: 24px;
                font-size: 13px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }

            QTabBar::tab:selected {
                background: white;
                font-weight: bold;
            }

            QTabBar::tab:hover {
                background: #f5f5f5;
            }
        """)

        self.add_tab()

    def add_tab(self):
        tab = LineDrawerTab()
        index = self.tabs.addTab(tab, "New Tab")
        self.tabs.setCurrentIndex(index)

    def close_tab(self, index):
        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.add_tab()

    def setCurrentTabName(self, name):
        index = self.tabs.currentIndex()
        if index >= 0:
            self.tabs.setTabText(index, name)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LineDrawerApp()
    window.show()
    sys.exit(app.exec_())