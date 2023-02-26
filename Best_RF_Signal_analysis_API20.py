import os
import csv
from qgis.core import QgsApplication, QgsProject, QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsRasterLayer, QgsPointXY, QgsGeometry, QgsField, QgsVectorLayer, QgsFeature, QgsFeatureSink
from qgis.gui import QgsMessageBar
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QFileDialog, QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QMessageBox

class MyDialog(QDialog):
    def __init__(self, parent=None):
        super(MyDialog, self).__init__(parent)
        
        # Set up the UI elements
        self.setWindowTitle('Extract Roof Heights')
        
        self.civic_data_label = QLabel('Civic Data CSV:')
        self.civic_data_lineedit = QLineEdit()
        self.civic_data_browse_button = QPushButton('Browse')
        self.civic_data_browse_button.clicked.connect(self.select_civic_data)
        
        self.dem_label = QLabel('DEM Raster:')
        self.dem_lineedit = QLineEdit()
        self.dem_browse_button = QPushButton('Browse')
        self.dem_browse_button.clicked.connect(self.select_dem)
        
        self.dsm_label = QLabel('DSM Raster:')
        self.dsm_lineedit = QLineEdit()
        self.dsm_browse_button = QPushButton('Browse')
        self.dsm_browse_button.clicked.connect(self.select_dsm)
        
        self.output_csv_label = QLabel('Output CSV:')
        self.output_csv_lineedit = QLineEdit()
        self.output_csv_browse_button = QPushButton('Browse')
        self.output_csv_browse_button.clicked.connect(self.select_output_csv)
        
        self.run_button = QPushButton('Run')
        self.run_button.clicked.connect(self.run_script)
        
        layout = QVBoxLayout()
        layout.addWidget(self.civic_data_label)
        layout.addWidget(self.civic_data_lineedit)
        layout.addWidget(self.civic_data_browse_button)
        layout.addWidget(self.dem_label)
        layout.addWidget(self.dem_lineedit)
        layout.addWidget(self.dem_browse_button)
        layout.addWidget(self.dsm_label)
        layout.addWidget(self.dsm_lineedit)
        layout.addWidget(self.dsm_browse_button)
        layout.addWidget(self.output_csv_label)
        layout.addWidget(self.output_csv_lineedit)
        layout.addWidget(self.output_csv_browse_button)
        layout.addWidget(self.run_button)
        self.setLayout(layout)
        
        # Set up instance variables to store the file paths
        self.civic_data_path = None
        self.dem_path = None
        self.dsm_path = None
        self.output_csv_path = None
        
        # Set up the QGIS message bar
        self.msg_bar = QgsMessageBar()
        self.layout().addWidget(self.msg_bar)
        
    def select_civic_data(self):
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilter('CSV Files (*.csv)')
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        if file_dialog.exec_() == QFileDialog.Accepted:
            self.civic_data_path = file_dialog.selectedFiles()[0]
            self.civic_data_lineedit.setText(self.civic_data_path)
            
    def select_dem(self):
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilter('GeoTIFF Files (*.tif *.tiff)')
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        if file_dialog.exec_() == QFileDialog.Accepted:
            self.dem_path = file_dialog.selectedFiles()[0]
            self.dsm_lineedit.setText(self.dsm_path)

def select_output_csv(self):
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilter('CSV Files (*.csv)')
        file_dialog.setAcceptMode(QFileDialog.AcceptSave)
        file_dialog.setDefaultSuffix('csv')
        if file_dialog.exec_() == QFileDialog.Accepted:
            self.output_csv_path = file_dialog.selectedFiles()[0]
            self.output_csv_lineedit.setText(self.output_csv_path)
            
def run_script(self):
        # Check that all necessary paths have been provided
        if not self.civic_data_path:
            self.msg_bar.pushMessage('Error', 'Please select a civic data CSV file.', level=Qgis.Critical, duration=5)
            return
        if not self.dem_path:
            self.msg_bar.pushMessage('Error', 'Please select a DEM raster file.', level=Qgis.Critical, duration=5)
            return
        if not self.dsm_path:
            self.msg_bar.pushMessage('Error', 'Please select a DSM raster file.', level=Qgis.Critical, duration=5)
            return
        if not self.output_csv_path:
            self.msg_bar.pushMessage('Error', 'Please select an output CSV file.', level=Qgis.Critical, duration=5)
            return
        
        # Open the civic data CSV file and create a reader object
        with open(self.civic_data_path, 'r') as f:
            reader = csv.DictReader(f)
            
            # Create a list to store the output data
            output_data = []
            
            # Load the DEM raster layer
            dem_layer = QgsRasterLayer(self.dem_path, 'DEM')
            if not dem_layer.isValid():
                self.msg_bar.pushMessage('Error', 'Failed to load DEM raster layer.', level=Qgis.Critical, duration=5)
                return
            
            # Load the DSM raster layer
            dsm_layer = QgsRasterLayer(self.dsm_path, 'DSM')
            if not dsm_layer.isValid():
                self.msg_bar.pushMessage('Error', 'Failed to load DSM raster layer.', level=Qgis.Critical, duration=5)
                return
            
            # Loop through each row in the civic data CSV file
            for row in reader:
                # Extract the latitude and longitude coordinates from the row
                latitude = float(row['Latitude'])
                longitude = float(row['Longitude'])
                
                # Convert the coordinates to the CRS of the DEM and DSM raster layers
                crs_transform = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), dem_layer.crs())
                point = QgsPointXY(longitude, latitude)
                point = crs_transform.transform(point)
                
                # Get the elevation value from the DEM and DSM rasters at the specified point
                dem_value, dem_success = dem_layer.dataProvider().sample(point, 1)
                dsm_value, dsm_success = dsm_layer.dataProvider().sample(point, 1)
                
                # If both DEM and DSM sampling was successful, calculate the roof height
                if dem_success and dsm_success:
                    roof_height = dsm_value - dem_value
                else:
                    roof_height = None
                
                # Add the row to the output data list
                output_row = {
                    'Civic Data': row['Civic Data'],
                    'New Height': roof_height,
                    'Latitude': row['Latitude'],
                    'Longitude': row['Longitude']
                }
                output_data.append(output_row)
                
        # Write the output data to a CSV file

        with open(self.output_csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=output_data[0].keys())
            writer.writeheader()
            writer.writerows(output_data)
            
        # Show a success message in the message bar
        self.msg_bar.pushMessage('Success', 'Script completed successfully.', level=Qgis.Info, duration=5)
