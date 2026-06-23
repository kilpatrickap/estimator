import sys
import os
import pytest
from PyQt6.QtWidgets import QApplication

# Add project root to system path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from settings_dialog import SettingsDialog
from database import DatabaseManager

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app

def test_settings_dialog_model_loading_and_saving(qapp, monkeypatch):
    # Mock settings storage in memory to avoid writing to construction_costs.db
    settings_store = {
        "ai_model_name": "lfm2.5:8b",
        "company_name": "Test Company",
        "company_logo": ""
    }
    
    def mock_get_setting(self, key, default=None):
        return settings_store.get(key, default)
        
    def mock_set_setting(self, key, value):
        settings_store[key] = str(value)

    monkeypatch.setattr(DatabaseManager, "get_setting", mock_get_setting)
    monkeypatch.setattr(DatabaseManager, "set_setting", mock_set_setting)

    # Mock QMessageBox.information to prevent blocking/crashing in headless mode
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information", lambda parent, title, text, *args, **kwargs: QMessageBox.StandardButton.Ok)


    # 1. Mock get_installed_ollama_models to return mock models
    mock_models = ["lfm2.5:8b", "llama3"]
    monkeypatch.setattr(SettingsDialog, "get_installed_ollama_models", lambda self: mock_models)

    # Instantiate SettingsDialog
    dialog = SettingsDialog(estimate=None, project_dir="", library_path="", parent=None)

    # Verify combobox options
    combo_items = [dialog.ai_model_combo.itemText(i) for i in range(dialog.ai_model_combo.count())]
    assert "None" in combo_items
    assert "lfm2.5:8b" in combo_items
    assert "llama3" in combo_items
    
    # Verify the current selected item matches the mocked saved model
    assert dialog.ai_model_combo.currentText() == "lfm2.5:8b"

    # 2. Test saving a different model (llama3)
    dialog.ai_model_combo.setCurrentText("llama3")
    dialog.save_settings()
    assert settings_store["ai_model_name"] == "llama3"

    # 3. Test saving "None" translates to empty string in db
    dialog.ai_model_combo.setCurrentText("None")
    dialog.save_settings()
    assert settings_store["ai_model_name"] == ""

    # 4. Test offline saved model handling:
    # If the saved model is "offline-model:7b" but Ollama is offline or doesn't have it installed
    settings_store["ai_model_name"] = "offline-model:7b"
    # Re-instantiate
    dialog_offline = SettingsDialog(estimate=None, project_dir="", library_path="", parent=None)
    combo_items_offline = [dialog_offline.ai_model_combo.itemText(i) for i in range(dialog_offline.ai_model_combo.count())]
    assert "offline-model:7b" in combo_items_offline
    assert dialog_offline.ai_model_combo.currentText() == "offline-model:7b"
