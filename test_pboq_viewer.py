import pytest
import sqlite3
import os
import json
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from pboq_viewer import PBOQDialog

# Helper to create a dummy PBOQ database
def create_test_db(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create pboq_items table
    cursor.execute("""
        CREATE TABLE pboq_items (
            Sheet TEXT,
            "Column 0" TEXT,
            "Column 1" TEXT,
            "Column 2" TEXT,
            "Column 3" TEXT,
            "Column 4" TEXT,
            "Column 5" TEXT,
            GrossRate TEXT,
            RateCode TEXT
        )
    """)
    
    # Insert some dummy data
    data = [
        ('Sheet 1', 'Item 1', 'Description 1', '10', 'm', '25.00', '250.00', None, None),
        ('Sheet 1', 'Item 2', 'COLLECTION', '', '', '', '', None, None),
        ('Sheet 1', 'Item 3', 'Description 3', '5', 'm', '10.00', '50.00', None, None),
        ('Sheet 1', 'Item 4', 'CARRIED TO SUMMARY OF BILL', '', '', '', '', None, None),
    ]
    cursor.executemany("""
        INSERT INTO pboq_items (Sheet, "Column 0", "Column 1", "Column 2", "Column 3", "Column 4", "Column 5", GrossRate, RateCode)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, data)
    
    conn.commit()
    conn.close()

@pytest.fixture
def app(qtbot):
    # QApplication is handled by pytest-qt
    return QApplication.instance()

@pytest.fixture
def dialog(tmp_path, qtbot):
    # Setup project structure
    project_dir = str(tmp_path)
    pboq_folder = os.path.join(project_dir, "Priced BOQs")
    os.makedirs(pboq_folder)
    
    db_path = os.path.join(pboq_folder, "test_bill.db")
    create_test_db(db_path)
    
    # Instantiate dialog
    dialog = PBOQDialog(project_dir)
    qtbot.addWidget(dialog)
    return dialog

def test_load_database(dialog):
    # Verify that the database loaded and created tabs
    assert dialog.tabs.count() > 0
    assert dialog.tabs.tabText(0) == "Sheet 1"
    
    table = dialog.tabs.widget(0)
    assert table.rowCount() == 4
    assert table.item(0, 1).text() == "Description 1"

def test_column_mapping(dialog, qtbot):
    # Map columns
    dialog.cb_desc.setCurrentIndex(2) # Column 1
    dialog.cb_qty.setCurrentIndex(3)  # Column 2
    
    # The combo box remains "Column 1", but the header should update
    table = dialog.tabs.widget(0)
    assert table.horizontalHeaderItem(1).text() == "Description"
    assert table.horizontalHeaderItem(2).text() == "Quantity"

def test_extend_logic(dialog, qtbot):
    # Setup mapping
    dialog.cb_qty.setCurrentIndex(3)       # Column 2 (Quantity)
    dialog.cb_bill_rate.setCurrentIndex(6) # Column 5 (Bill Rate - using Column 4 index in DB is Column 3 display? No.)
    # In DB: Column 0, Column 1, Column 2, Column 3, Column 4, Column 5
    # display_col_names = Column 0 to Column 7 (if exist)
    # Column 0 is Item No, 1 is Desc, 2 is Qty, 3 is Unit, 4 is Rate, 5 is Amount
    
    dialog.cb_qty.setCurrentIndex(3)       # Column 2
    dialog.cb_bill_rate.setCurrentIndex(5) # Column 4
    dialog.cb_bill_amount.setCurrentIndex(6) # Column 5
    
    # Set alignment checkbox
    dialog.extend_cb0.setChecked(True) # Align to Column 0
    
    # Change dummy rate
    dialog.dummy_rate_spin.setValue(100.0)
    
    # We need a row where rate is empty and qty exists
    # Item 1 has rate 25.00, so it should be skipped by default logic if it preserves.
    # Let's clear Item 1 rate
    table = dialog.tabs.widget(0)
    table.item(0, 4).setText("")
    
    # Run extend
    qtbot.mouseClick(dialog.extend_btn, Qt.MouseButton.LeftButton)
    
    # Check if Item 1 got dummy rate
    assert table.item(0, 4).text() == "100.00"
    # Check amount: 10 * 100 = 1000.00
    assert table.item(0, 5).text() == "1,000.00"

def test_collect_logic(dialog, qtbot):
    # Map columns
    dialog.cb_desc.setCurrentIndex(2)        # Column 1
    dialog.cb_bill_amount.setCurrentIndex(6) # Column 5
    
    # Set keyword
    dialog.collect_search_bar.setText("COLLECTION")
    
    # Run collect
    qtbot.mouseClick(dialog.collect_btn, Qt.MouseButton.LeftButton)
    
    # Item 1 has 250.00 in column 5
    # Item 2 is COLLECTION. It should get sum 250.00
    table = dialog.tabs.widget(0)
    assert table.item(1, 5).text() == "250.00"
    assert table.item(1, 5).background().color().name().lower() == "#ffa500" # Orange

def test_summary_logic(dialog, qtbot):
    # Map columns
    dialog.cb_desc.setCurrentIndex(2)        # Column 1
    dialog.cb_bill_amount.setCurrentIndex(6) # Column 5
    
    # Step 1: Manual "Collect" to produce orange cells
    table = dialog.tabs.widget(0)
    # Highlight Item 2 (COLLECTION) manually as if collected
    item2_amt = table.item(1, 5)
    item2_amt.setText("250.00")
    item2_amt.setBackground(dialog.COLOR_COLLECT)
    
    # Also Item 3 has 50.00. Let's say it's uncollected but contributes if orange is not used?
    # Actually _run_summary_logic uses Orange cells if they exist.
    
    # Set summary target
    dialog.summary_target_bar.setText("SUMMARY")
    
    # Run summary
    qtbot.mouseClick(dialog.summarize_btn, Qt.MouseButton.LeftButton)
    
    # Item 4 matches "SUMMARY" (case insensitive target check in code)
    # It should sum the orange cells (250.00)
    assert table.item(3, 5).text() == "250.00"
    assert table.item(3, 5).background().color().name().lower() == "#00ff00" # lime

def test_live_links(dialog, qtbot):
    # Setup mapping
    dialog.cb_bill_amount.setCurrentIndex(6) # Column 5
    
    # Create a link manually or via populate
    # Source: Row 1 (Item 1), Col 5. rowid of Item 1 is 1.
    # Dest: Row 4 (Item 4), Col 5. rowid of Item 4 is 4.
    
    table = dialog.tabs.widget(0)
    src_rowid = table.item(0, 0).data(Qt.ItemDataRole.UserRole)
    dst_rowid = table.item(3, 0).data(Qt.ItemDataRole.UserRole)
    
    dialog._save_link_to_db(src_rowid, dst_rowid)
    
    # Update src item in UI and trigger sync via batch update simulation
    # In the app, this happens via _persist_batch_updates
    updates = [(src_rowid, "999.00")]
    dialog._persist_batch_updates(5, updates) # 5 is amount_idx
    
    # Check if destination updated
    assert table.item(3, 5).text() == "999.00"
    assert table.item(3, 5).background().color().name().lower() == "#ffff00" # yellow

