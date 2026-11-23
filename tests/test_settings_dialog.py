from PySide6.QtWidgets import QDialog

from yt_dlp_gui.settings import AppConfig
from yt_dlp_gui.settings_dialog import SettingsDialog


def test_dialog_populates_from_config(qapp, tmp_path):
    config = AppConfig(download_dir=str(tmp_path), format_preset="720p", max_concurrent=2)
    dialog = SettingsDialog(config)
    try:
        assert dialog.folder_edit.text() == str(tmp_path)
        assert dialog.preset_combo.currentData() == "720p"
        assert dialog.concurrent_spin.value() == 2
        assert dialog.on_top_check.isChecked() is config.always_on_top
        assert dialog.split_chapters_check.isChecked() is config.split_chapters
        assert dialog.split_chapters_note.text()
        assert dialog.player_combo.currentData() == "vlc"
        assert dialog.player_status.text()
    finally:
        dialog.deleteLater()


def test_dialog_accept_builds_new_config(qapp, tmp_path):
    dialog = SettingsDialog(AppConfig(download_dir=str(tmp_path)))
    try:
        dialog.preset_combo.setCurrentIndex(dialog.preset_combo.findData("audio_mp3"))
        dialog.clipboard_check.setChecked(True)
        dialog.split_chapters_check.setChecked(True)
        dialog.concurrent_spin.setValue(3)
        dialog.template_edit.setText("%(title)s.%(ext)s")
        dialog.player_combo.setCurrentIndex(dialog.player_combo.findData("mpv"))
        dialog._on_accept()  # folder exists, so no modal dialog appears
        config = dialog.result_config()
        assert config.format_preset == "audio_mp3"
        assert config.clipboard_watch is True
        assert config.split_chapters is True
        assert config.max_concurrent == 3
        assert config.filename_template == "%(title)s.%(ext)s"
        assert config.media_player == "mpv"
        assert dialog.result() == QDialog.DialogCode.Accepted
    finally:
        dialog.deleteLater()


def test_dialog_rejects_empty_folder(qapp, tmp_path):
    dialog = SettingsDialog(AppConfig(download_dir=str(tmp_path)))
    try:
        dialog.folder_edit.setText("")
        # An empty folder shows a warning; monkeypatch QMessageBox to avoid a modal.
        import yt_dlp_gui.settings_dialog as module

        original = module.QMessageBox.warning
        module.QMessageBox.warning = staticmethod(lambda *args, **kwargs: None)
        try:
            dialog._on_accept()
        finally:
            module.QMessageBox.warning = original
        assert dialog.result() != QDialog.DialogCode.Accepted
    finally:
        dialog.deleteLater()
