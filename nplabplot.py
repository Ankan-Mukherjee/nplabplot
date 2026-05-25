import sys
import os
import numpy as np
import pyqtgraph as pg
import pyqtgraph.exporters  # CRITICAL: Required for exporting image layouts to disk
from pyqtgraph.Qt import QtCore, QtGui
from qcodes_loop.data.data_set import load_data
from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QWidget, QSplitter, QVBoxLayout,
    QListWidget, QPushButton, QTableWidget, QTableWidgetItem,
    QLabel, QHBoxLayout, QLineEdit, QComboBox,
    QHeaderView, QDoubleSpinBox, QFileDialog, QSizePolicy
)
from PyQt5.QtCore import Qt

class LineDrawerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Track the raw folder location to construct dynamic image export paths later
        self.loaded_folder_path = None
        
        # Windows configuration
        self.setWindowTitle("NPLab Data Plotter")
        self.setGeometry(100, 100, 1000, 650) # Expanded width slightly to cleanly fit the button row

        # CRITICAL: Tell the window to listen for drag and drop events
        self.setAcceptDrops(True)

        # Set background color to white and other stuff to black
        pg.setConfigOption('background', 'w')  
        pg.setConfigOption('foreground', 'k') 

        # Style Mappings
        self.color_map = {
            'Black': 'k',
            'Red': 'r',
            'Green': 'g',
            'Blue': 'b'
        }
        
        self.style_map = {
            'Line': QtCore.Qt.SolidLine,
        }
        
        # We append the scatter options to the style list
        self.style_options = list(self.style_map.keys()) + ['Scatter', 'Scatter_line']

        # Main UI Stack
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        main_layout = QHBoxLayout(self.main_widget)

        # Split UI (Splits controls vertically from the plots)
        splitter = QSplitter(QtCore.Qt.Vertical)
        main_layout.addWidget(splitter)
        
        # ---------------------------------------------------------
        # Control panel UI (Vertical Container for row + folder status)
        # ---------------------------------------------------------
        control_container = QWidget()
        container_v_layout = QVBoxLayout(control_container)
        container_v_layout.setContentsMargins(5, 5, 5, 5)

        # The Horizontal row containing all buttons and dropdowns
        control_row_widget = QWidget()
        control_row_layout = QHBoxLayout(control_row_widget)
        control_row_layout.setContentsMargins(0, 0, 0, 0)

        # 1. Open Button
        self.open_btn = QPushButton("Open Folder")
        self.open_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.open_btn.clicked.connect(self.open_folder)

        # Data Dropdowns
        self.x_dropdown = QComboBox()
        self.y_dropdown = QComboBox()
        self.z_dropdown = QComboBox()
        
        # Style Dropdowns
        self.color_dropdown = QComboBox()
        self.style_dropdown = QComboBox()
        
        self.color_dropdown.addItems(self.color_map.keys())
        self.style_dropdown.addItems(self.style_options)

        # NEW: 2. Save Image Button
        # self.save_btn = QPushButton("Save Image")
        # self.save_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # self.save_btn.clicked.connect(self.save_image)

        # Set sizing policies
        for dropdown in [self.x_dropdown, self.y_dropdown, self.z_dropdown, self.color_dropdown, self.style_dropdown]:
            dropdown.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # Connections (using activated instead of currentTextChanged prevents cascading updates during clear cycles)
        self.x_dropdown.activated.connect(self.change_x)
        self.y_dropdown.activated.connect(self.change_y)
        self.z_dropdown.activated.connect(self.change_z)
        self.color_dropdown.currentTextChanged.connect(self.update_pen)
        self.style_dropdown.currentTextChanged.connect(self.update_pen)

        # Labels
        self.x_label = QLabel("X:")
        self.y_label = QLabel("Y:")
        self.z_label = QLabel("Z:")
        self.color_label = QLabel("Color:")
        self.style_label = QLabel("Style:")

        # Add items to the single row layout
        control_row_layout.addWidget(self.open_btn, 2)
        control_row_layout.addWidget(self.x_label)
        control_row_layout.addWidget(self.x_dropdown, 2)
        control_row_layout.addWidget(self.y_label)
        control_row_layout.addWidget(self.y_dropdown, 2)
        
        # Z elements (for 2D)
        control_row_layout.addWidget(self.z_label)
        control_row_layout.addWidget(self.z_dropdown, 2)
        
        # Style elements (for 1D)
        control_row_layout.addWidget(self.color_label)
        control_row_layout.addWidget(self.color_dropdown, 2)
        control_row_layout.addWidget(self.style_label)
        control_row_layout.addWidget(self.style_dropdown, 2)
        
        # NEW: Inject Save Button onto the far right side of the row layout
        # control_row_layout.addWidget(self.save_btn, 2)
        
        # Folder Status Label (Now sits cleanly underneath the ENTIRE row)
        self.folder_label = QLabel("No folder loaded")
        self.folder_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.folder_label.setWordWrap(True)
        self.folder_label.setStyleSheet("color: #444; font-weight: bold; font-size: 11px; padding-left: 5px;") 

        # Stack the row and the folder status label vertically
        container_v_layout.addWidget(control_row_widget)
        container_v_layout.addWidget(self.folder_label)
        
        # Start with Z, styles, and Save button hidden until data is loaded
        self.z_label.setVisible(False)
        self.z_dropdown.setVisible(False)
        self.color_label.setVisible(False)
        self.color_dropdown.setVisible(False)
        self.style_label.setVisible(False)
        self.style_dropdown.setVisible(False)
        # self.save_btn.setVisible(False) 
        
        # Track dataset type (2D or 1D)
        self.is_2d = False
        # ---------------------------------------------------------

        # Plot and image setup
        self.win = pg.GraphicsLayoutWidget()
        
        self.plot = self.win.addPlot(row=0, col=0)
        self.plot.setAspectLocked(False)
        
        # Initialize 2D Image Item
        self.img = pg.ImageItem()
        self.plot.addItem(self.img)
        
        # Initialize 1D Line Item
        self.line = pg.PlotDataItem(pen=pg.mkPen('b', width=2))
        self.plot.addItem(self.line)

        # Histogram colorbar
        self.hist = pg.HistogramLUTItem()
        self.hist.setImageItem(self.img)
        self.hist.gradient.setColorMap(pg.colormap.get('viridis'))
        self.win.addItem(self.hist, row=0, col=1)

        # Log scale
        self.log_mode = False
        self.log_action = QtGui.QAction("Log scale", self.hist)
        self.log_action.setCheckable(True)
        self.log_action.triggered.connect(self.set_log_mode)
        self.hist.vb.menu.addSeparator()
        self.hist.vb.menu.addAction(self.log_action)
        
        # Start with visuals hidden
        self.img.setVisible(False)
        self.line.setVisible(False)
        self.hist.setVisible(False)

        # Add panels to splitter
        splitter.addWidget(control_container)
        splitter.addWidget(self.win)
        splitter.setSizes([80, 750]) # Adjusted spacing to comfortably fit the row + tracking label

    # =========================================================================
    # DRAG AND DROP HANDLERS
    # =========================================================================
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
    # =========================================================================

    def open_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:  
            self.load_dataset(folder_path)

    def get_axis_label(self, key):
        """Helper to safely extract qcodes labels and units for pyqtgraph display"""
        if not hasattr(self, 'data') or key not in self.data.arrays:
            return key
        arr = self.data.arrays[key]
        label = getattr(arr, 'label', key) or key
        unit = getattr(arr, 'unit', '')
        return f"{label} ({unit})" if unit else label

    def update_axes_labels(self):
        """Pushes current dropdown selections to pyqtgraph axis labels"""
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
        """Loads data, evaluates dimensions, and completely initializes UI selections."""
        folder_path = folder_path.strip().rstrip('\\').rstrip('/')
        
        try:
            abs_path = os.path.abspath(folder_path)
            self.data = load_data(abs_path)
            self.loaded_folder_path = abs_path
            self.folder_label.setText(f"{abs_path}")
        except Exception as e:
            print(f"Failed to load dataset from {folder_path}: {e}")
            self.folder_label.setText("Error loading selected folder")
            return

        data_list = list(self.data.arrays.keys())
        data_arrays = list(self.data.arrays.values())

        # Determine global dimensionality baseline
        self.is_2d = any(arr[:].ndim >= 2 for arr in data_arrays)

        # Temporarily block widget signals to avoid layout initialization loops
        self.x_dropdown.blockSignals(True)
        self.y_dropdown.blockSignals(True)
        self.z_dropdown.blockSignals(True)

        self.x_dropdown.clear()
        self.y_dropdown.clear()
        self.z_dropdown.clear()

        self.x_dropdown.addItems(data_list)
        self.y_dropdown.addItems(data_list)
        self.z_dropdown.addItems(data_list)

        # self.save_btn.setVisible(True)

        if self.is_2d:
            self.z_label.setVisible(True)
            self.z_dropdown.setVisible(True)
            self.color_label.setVisible(False)
            self.color_dropdown.setVisible(False)
            self.style_label.setVisible(False)
            self.style_dropdown.setVisible(False)
            
            # Map typical QCodes 2D sweeps: [0]=Y page coordinates, [1]=X horizontal coordinates, [2]=Z raw data values
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

        # Directly synchronize references and run display configurations
        self.sync_active_arrays()
        self.update_plot()

    def sync_active_arrays(self):
        """Safely updates self.X, self.Y, and self.Z based on active dropdown configuration values."""
        if not hasattr(self, 'data'):
            return

        x_key = self.x_dropdown.currentText()
        y_key = self.y_dropdown.currentText()
        z_key = self.z_dropdown.currentText()

        self.X = self.data.arrays[x_key][:] if x_key in self.data.arrays else None
        self.Y = self.data.arrays[y_key][:] if y_key in self.data.arrays else None
        
        if self.is_2d and z_key in self.data.arrays:
            # Transpose here on ingestion dynamically to meet PyQtGraph image expectations
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
            
            # 1. Extract 1D vectors for coordinates
            x_vec = self.X[0] if self.X.ndim > 1 else self.X
            y_vec = self.Y[:, 0] if self.Y.ndim > 1 else self.Y
            
            # Remove NaNs to find clean bounding ranges for the view limits
            valid_x = x_vec[~np.isnan(x_vec)]
            valid_y = y_vec[~np.isnan(y_vec)]
            
            if len(valid_x) < 2 or len(valid_y) < 2 or np.isnan(self.Z).all():
                return
            
            # 2. Determine step directions and sizes
            # This captures whether your sweep goes backward or forward!
            dx = (valid_x[-1] - valid_x[0]) / (len(valid_x) - 1)
            dy = (valid_y[-1] - valid_y[0]) / (len(valid_y) - 1)

            if self.log_mode:
                Zdisp = np.sign(self.Z) * np.log10(np.abs(self.Z))
            else:
                Zdisp = self.Z
            self.img.setImage(Zdisp, autoLevels=False)
            
            # 3. Use QTransform to scale and map pixel grid to spatial axes.
            # We offset by -0.5 * step so coordinates target pixel centers, 
            # matching standard matrix transforms.
            transform = QtGui.QTransform()
            transform.translate(valid_x[0] - 0.5 * dx, valid_y[0] - 0.5 * dy)
            transform.scale(dx, dy)


            # Load data cleanly into ImageItem
            self.img.setImage(Zdisp, autoLevels=False)
            self.img.setTransform(transform)
            
            # 4. Correctly fit your PlotWidget view boundaries 
            self.plot.setXRange(np.nanmin(valid_x), np.nanmax(valid_x), padding=0.04)
            self.plot.setYRange(np.nanmin(valid_y), np.nanmax(valid_y), padding=0.04)
            
            # Update histogram intensities
            p5, p95 = np.nanpercentile(Zdisp, [5, 95])
            if p5 == p95: p5 -= 0.1; p95 += 0.1
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

    def set_log_mode(self, checked):
        self.log_mode = checked
        self.update_plot()
    
    
    # UI Interaction Events mapped to runtime syncing
    def change_x(self, index):
        self.sync_active_arrays()
        self.update_plot()

    def change_y(self, index):
        self.sync_active_arrays()
        self.update_plot()

    def change_z(self, index):
        self.sync_active_arrays()
        self.update_plot()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LineDrawerApp()
    window.show()
    sys.exit(app.exec_())