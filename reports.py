# reports.py

import os
import sqlite3
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QComboBox, QFileDialog, QMessageBox, QFrame, QScrollArea, QListWidget, QListWidgetItem)
from PyQt6.QtCore import Qt, pyqtSignal
from report_generator import ReportGenerator
from database import DatabaseManager

class ReportsDialog(QWidget):
    """Reports management window."""
    stateChanged = pyqtSignal()

    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.setWindowTitle("Reports & Exports")
        self._init_ui()
        self.load_available_projects()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header
        header = QLabel("Project Reports")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #1b5e20;")
        layout.addWidget(header)

        # Description
        desc = QLabel("Select a project and configuration to generate a professional PDF report.")
        desc.setStyleSheet("color: #666; font-size: 13px;")
        layout.addWidget(desc)

        # Project Selection Section
        selection_group = QFrame()
        selection_group.setStyleSheet("background-color: white; border-radius: 8px; border: 1px solid #ddd;")
        selection_layout = QVBoxLayout(selection_group)
        selection_layout.setContentsMargins(15, 15, 15, 15)

        selection_layout.addWidget(QLabel("<b>Available Projects:</b>"))
        self.project_list = QListWidget()
        self.project_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #eee;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #f5f5f5;
            }
            QListWidget::item:selected {
                background-color: #e8f5e9;
                color: #2e7d32;
                border-radius: 4px;
            }
        """)
        selection_layout.addWidget(self.project_list)
        
        layout.addWidget(selection_group)

        # Options Section
        options_group = QFrame()
        options_group.setStyleSheet("background-color: #f9f9f9; border-radius: 8px; border: 1px solid #eee;")
        options_layout = QHBoxLayout(options_group)
        options_layout.setContentsMargins(15, 15, 15, 15)

        # Left side: Company details
        company_layout = QVBoxLayout()
        company_layout.addWidget(QLabel("Company Name:"))
        self.company_input = QComboBox()
        self.company_input.setEditable(True)
        self.company_input.addItem("Consar Limited") # Default for this project
        company_layout.addWidget(self.company_input)
        options_layout.addLayout(company_layout, 2)

        # Right side: Logo selection
        logo_layout = QVBoxLayout()
        logo_layout.addWidget(QLabel("Company Logo:"))
        logo_btn_layout = QHBoxLayout()
        self.logo_path_label = QLabel("No logo selected")
        self.logo_path_label.setStyleSheet("color: #888; font-size: 11px;")
        self.select_logo_btn = QPushButton("Browse...")
        self.select_logo_btn.clicked.connect(self.select_logo)
        logo_btn_layout.addWidget(self.logo_path_label, 1)
        logo_btn_layout.addWidget(self.select_logo_btn)
        logo_layout.addLayout(logo_btn_layout)
        options_layout.addLayout(logo_layout, 3)

        layout.addWidget(options_group)

        # Action Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.generate_btn = QPushButton("Generate PDF Report")
        self.generate_btn.setFixedSize(200, 45)
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1b5e20;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        self.generate_btn.clicked.connect(self.generate_report)
        button_layout.addWidget(self.generate_btn)
        
        layout.addLayout(button_layout)
        layout.addStretch()

        self.logo_path = None

    def select_logo(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Logo", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            self.logo_path = file_path
            self.logo_path_label.setText(os.path.basename(file_path))

    def load_available_projects(self):
        self.project_list.clear()
        
        # Get projects from current session if available
        db_manager = DatabaseManager()
        last_dir = db_manager.get_setting('last_project_dir', '')
        
        if last_dir and os.path.exists(last_dir):
            db_dir = os.path.join(last_dir, "Project Database")
            if os.path.exists(db_dir):
                dbs = [f for f in os.listdir(db_dir) if f.endswith('.db')]
                for db_file in dbs:
                    db_path = os.path.join(db_dir, db_file)
                    try:
                        temp_db = DatabaseManager(db_path)
                        summaries = temp_db.get_saved_estimates_summary()
                        for s in summaries:
                            item = QListWidgetItem(f"{s['project_name']} ({s['rate_code']})")
                            item.setData(Qt.ItemDataRole.UserRole, (db_path, s['id']))
                            self.project_list.addItem(item)
                    except:
                        pass

    def generate_report(self):
        selected = self.project_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a project from the list.")
            return

        db_path, estimate_id = selected.data(Qt.ItemDataRole.UserRole)
        
        try:
            db_manager = DatabaseManager(db_path)
            estimate = db_manager.load_estimate_details(estimate_id)
            
            if not estimate:
                QMessageBox.critical(self, "Error", "Failed to load estimate details.")
                return

            # Ask where to save
            save_path, _ = QFileDialog.getSaveFileName(
                self, "Save Report", 
                f"{estimate.project_name}_Report.pdf", 
                "PDF Files (*.pdf)"
            )
            
            if not save_path:
                return

            self.generate_btn.setEnabled(False)
            self.generate_btn.setText("Generating...")
            
            # Use the existing ReportGenerator
            generator = ReportGenerator(estimate)
            success = generator.export_to_pdf(
                save_path, 
                company_name=self.company_input.currentText(),
                company_logo=self.logo_path
            )
            
            if success:
                QMessageBox.information(self, "Success", f"Report generated successfully:\n{save_path}")
                # Try to open it
                import subprocess
                try:
                    os.startfile(save_path)
                except:
                    pass
            else:
                QMessageBox.critical(self, "Error", "Failed to generate PDF report. Check logs for details.")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")
        finally:
            self.generate_btn.setEnabled(True)
            self.generate_btn.setText("Generate PDF Report")
