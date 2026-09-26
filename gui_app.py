import sys
import os
import json
import subprocess
from pathlib import Path
from dotenv import load_dotenv

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QMessageBox, QDialog, QFormLayout, QGroupBox, QPlainTextEdit, QFrame
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QColor

load_dotenv()

BASE_DIR = Path(__file__).parent.resolve()
JOBS_FILE = BASE_DIR / "jobs.json"
CONFIG_FILE = BASE_DIR / "config.json"
LOGS_FILE = BASE_DIR / "logs" / "tiktok_uploader.log"
ENV_FILE = BASE_DIR / ".env"

# --- WORKER THREAD FOR RUNNING PIPELINE ---
class PipelineThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def run(self):
        try:
            cmd = [sys.executable, "main.py", "run-pipeline"]
            process = subprocess.Popen(
                cmd, cwd=str(BASE_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in iter(process.stdout.readline, ''):
                if line:
                    self.log_signal.emit(line.strip())
            process.wait()
            self.finished_signal.emit(process.returncode == 0)
        except Exception as e:
            self.log_signal.emit(f"❌ Error: {e}")
            self.finished_signal.emit(False)

# --- STYLESHEET (DARK MODE MODERN UI) ---
QSS_THEME = """
QMainWindow {
    background-color: #0f1117;
}
QWidget {
    background-color: #0f1117;
    color: #f1f5f9;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #1e293b;
    background: #181b24;
    border-radius: 8px;
}
QTabBar::tab {
    background: #181b24;
    color: #94a3b8;
    padding: 10px 20px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: bold;
}
QTabBar::tab:selected {
    background: #fe2c55;
    color: #ffffff;
}
QTabBar::tab:hover:!selected {
    background: #242936;
    color: #f1f5f9;
}
QGroupBox {
    border: 1px solid #1e293b;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: bold;
    color: #fe2c55;
}
QPushButton {
    background-color: #181b24;
    border: 1px solid #334155;
    color: #f1f5f9;
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #334155;
    border-color: #475569;
}
QPushButton#btnPrimary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #fe2c55, stop:1 #e01e43);
    color: #ffffff;
    border: none;
}
QPushButton#btnPrimary:hover {
    background-color: #ff476e;
}
QPushButton#btnSuccess {
    background-color: #10b981;
    color: #ffffff;
    border: none;
}
QPushButton#btnSuccess:hover {
    background-color: #059669;
}
QPushButton#btnDanger {
    background-color: #ef4444;
    color: #ffffff;
    border: none;
}
QPushButton#btnDanger:hover {
    background-color: #dc2626;
}
QTableWidget {
    background-color: #181b24;
    gridline-color: #1e293b;
    border: 1px solid #1e293b;
    border-radius: 6px;
}
QHeaderView::section {
    background-color: #0f1117;
    color: #94a3b8;
    padding: 8px;
    border: none;
    font-weight: bold;
}
QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #181b24;
    border: 1px solid #334155;
    color: #f1f5f9;
    padding: 6px;
    border-radius: 6px;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border-color: #fe2c55;
}
QPlainTextEdit#logConsole {
    background-color: #090a0f;
    color: #a7f3d0;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    border: 1px solid #1e293b;
    border-radius: 6px;
}
"""

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TikTok Studio Auto Uploader & AI Script Desktop App v2.5")
        self.resize(1150, 750)
        self.setStyleSheet(QSS_THEME)

        self.pipeline_thread = None

        # Main Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Header Title Area
        header = QHBoxLayout()
        title_lbl = QLabel("🎵 TikTok Studio Auto Uploader Desktop")
        title_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #fe2c55;")
        header.addWidget(title_lbl)

        header.addStretch()

        self.btn_run = QPushButton("🚀 Bắt đầu Chạy Pipeline")
        self.btn_run.setObjectName("btnPrimary")
        self.btn_run.setFixedHeight(38)
        self.btn_run.clicked.connect(self.run_pipeline)
        header.addWidget(self.btn_run)

        main_layout.addLayout(header)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.init_jobs_tab()
        self.init_batch_tab()
        self.init_logs_tab()
        self.init_settings_tab()

        # Timer to auto-update jobs table & logs
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_jobs_table)
        self.timer.start(3000)

    # --- TAB 1: JOBS QUEUE ---
    def init_jobs_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Top Metric Cards
        metrics_layout = QHBoxLayout()
        self.card_total = self._create_card("Tổng Jobs", "0", "#3b82f6")
        self.card_pending = self._create_card("Đang Chờ", "0", "#f59e0b")
        self.card_processing = self._create_card("Đang Xử Lý", "0", "#8b5cf6")
        self.card_failed = self._create_card("Thất Bại", "0", "#ef4444")

        metrics_layout.addWidget(self.card_total)
        metrics_layout.addWidget(self.card_pending)
        metrics_layout.addWidget(self.card_processing)
        metrics_layout.addWidget(self.card_failed)

        layout.addLayout(metrics_layout)

        # Action bar
        act_layout = QHBoxLayout()
        btn_add = QPushButton("➕ Thêm Link Thủ Công")
        btn_add.clicked.connect(self.add_single_job_dialog)

        btn_reset = QPushButton("🔄 Chạy Lại Job Chọn")
        btn_reset.clicked.connect(self.reset_selected_job)

        btn_delete = QPushButton("❌ Xóa Job Chọn")
        btn_delete.setObjectName("btnDanger")
        btn_delete.clicked.connect(self.delete_selected_job)

        act_layout.addWidget(btn_add)
        act_layout.addWidget(btn_reset)
        act_layout.addWidget(btn_delete)
        act_layout.addStretch()

        layout.addLayout(act_layout)

        # Jobs Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Link Sản Phẩm TikTok Shop", "Tên Sản Phẩm", "Prompt AI", "Segments", "Tài Khoản", "Trạng Thái"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        self.tabs.addTab(tab, "📋 Quản Lý Danh Sách Jobs")
        self.refresh_jobs_table()

    def _create_card(self, title, val, color):
        box = QFrame()
        box.setStyleSheet(f"""
            QFrame {{
                background-color: #181b24;
                border: 1px solid #1e293b;
                border-left: 4px solid {color};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        lay = QVBoxLayout(box)
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        v_lbl = QLabel(val)
        v_lbl.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {color};")
        v_lbl.setObjectName("cardVal")
        lay.addWidget(t_lbl)
        lay.addWidget(v_lbl)
        return box

    # --- TAB 2: BATCH PASTE LINKS ---
    def init_batch_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        lbl = QLabel("⚡ Dán Danh Sách Links TikTok Shop (Mỗi dòng 1 link):")
        lbl.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl)

        self.txt_batch = QTextEdit()
        self.txt_batch.setPlaceholderText("https://vt.tiktok.com/ZS9AqBpAdFKc8-PuDJK/\nhttps://vt.tiktok.com/ZS9AqBG1cvk7R-fhGrV/")
        layout.addWidget(self.txt_batch)

        btn_sub = QPushButton("➕ Thêm Hàng Loạt Vào Danh Sách Jobs")
        btn_sub.setObjectName("btnPrimary")
        btn_sub.clicked.connect(self.submit_batch_links)
        layout.addWidget(btn_sub)

        self.tabs.addTab(tab, "⚡ Thêm Hàng Loạt Links")

    # --- TAB 3: LOGS ---
    def init_logs_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.log_edit = QPlainTextEdit()
        self.log_edit.setObjectName("logConsole")
        self.log_edit.setReadOnly(True)
        layout.addWidget(self.log_edit)

        btn_ref = QPushButton("🔄 Tải Lại Log")
        btn_ref.clicked.connect(self.load_logs)
        layout.addWidget(btn_ref)

        self.tabs.addTab(tab, "💻 Nhật Ký Hệ Thống (Logs)")
        self.load_logs()

    # --- TAB 4: SETTINGS ---
    def init_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        group = QGroupBox("Cấu Hình LLM API & Headless")
        form = QFormLayout(group)

        self.inp_api_key = QLineEdit(os.getenv("LLM_API_KEY", ""))
        self.inp_base_url = QLineEdit(os.getenv("LLM_BASE_URL", "https://api.vilao.ai/v1"))
        self.inp_model = QLineEdit(os.getenv("LLM_MODEL", "gemini-3.6-flash"))

        self.combo_headless = QComboBox()
        self.combo_headless.addItems(["false - Mở trình duyệt hiển thị (Khuyên dùng)", "true - Ẩn trình duyệt ngầm"])

        form.addRow("LLM API Key:", self.inp_api_key)
        form.addRow("LLM Base URL:", self.inp_base_url)
        form.addRow("LLM Model ID:", self.inp_model)
        form.addRow("Headless Mode:", self.combo_headless)

        layout.addWidget(group)

        btn_save = QPushButton("💾 Lưu Cấu Hình")
        btn_save.setObjectName("btnSuccess")
        btn_save.clicked.connect(self.save_settings)
        layout.addWidget(btn_save)
        layout.addStretch()

        self.tabs.addTab(tab, "⚙️ Cấu Hình Hệ Thống")

    # --- HELPER & LOGIC METHODS ---
    def refresh_jobs_table(self):
        jobs = self._load_jobs()
        self.table.setRowCount(len(jobs))

        total = len(jobs)
        pending = sum(1 for j in jobs if j.get("status") == "pending")
        processing = sum(1 for j in jobs if j.get("status") == "processing")
        failed = sum(1 for j in jobs if j.get("status") == "failed")

        # Update metric cards
        self.card_total.findChild(QLabel, "cardVal").setText(str(total))
        self.card_pending.findChild(QLabel, "cardVal").setText(str(pending))
        self.card_processing.findChild(QLabel, "cardVal").setText(str(processing))
        self.card_failed.findChild(QLabel, "cardVal").setText(str(failed))

        for row, job in enumerate(jobs):
            self.table.setItem(row, 0, QTableWidgetItem(job.get("product_url", "")))
            self.table.setItem(row, 1, QTableWidgetItem(job.get("product_name", "") or "Tự động cào"))
            self.table.setItem(row, 2, QTableWidgetItem(job.get("prompt", "auto")))
            self.table.setItem(row, 3, QTableWidgetItem(str(job.get("video_segments", 2))))
            self.table.setItem(row, 4, QTableWidgetItem(job.get("tiktok_account", "acc1")))

            status = job.get("status", "pending")
            item_status = QTableWidgetItem(status.upper())
            if status == "pending":
                item_status.setForeground(QColor("#f59e0b"))
            elif status == "processing":
                item_status.setForeground(QColor("#8b5cf6"))
            elif status == "failed":
                item_status.setForeground(QColor("#ef4444"))
            else:
                item_status.setForeground(QColor("#10b981"))
            self.table.setItem(row, 5, item_status)

    def _load_jobs(self):
        if not JOBS_FILE.exists():
            return []
        try:
            with open(JOBS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_jobs(self, jobs):
        with open(JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump(jobs, f, indent=2, ensure_ascii=False)

    def add_single_job_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Thêm Job TikTok Mới")
        layout = QFormLayout(dialog)

        url_inp = QLineEdit()
        name_inp = QLineEdit()

        layout.addRow("Link Sản Phẩm TikTok Shop:", url_inp)
        layout.addRow("Tên Sản Phẩm (Bỏ trống để tự cào):", name_inp)

        btn_ok = QPushButton("Thêm Job")
        btn_ok.setObjectName("btnPrimary")
        btn_ok.clicked.connect(dialog.accept)
        layout.addRow(btn_ok)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            url = url_inp.text().strip()
            if url:
                jobs = self._load_jobs()
                jobs.append({
                    "product_url": url,
                    "product_name": name_inp.text().strip(),
                    "prompt": "auto",
                    "caption": "auto",
                    "video_segments": 2,
                    "tiktok_account": "acc1",
                    "status": "pending"
                })
                self._save_jobs(jobs)
                self.refresh_jobs_table()

    def submit_batch_links(self):
        text = self.txt_batch.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng dán ít nhất 1 đường dẫn TikTok Shop!")
            return
        urls = [u.strip() for u in text.splitlines() if u.strip()]
        jobs = self._load_jobs()
        for u in urls:
            jobs.append({
                "product_url": u,
                "product_name": "",
                "prompt": "auto",
                "caption": "auto",
                "video_segments": 2,
                "tiktok_account": "acc1",
                "status": "pending"
            })
        self._save_jobs(jobs)
        self.txt_batch.clear()
        self.refresh_jobs_table()
        QMessageBox.information(self, "Thành công", f"Đã thêm thành công {len(urls)} jobs mới!")

    def reset_selected_job(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Thông báo", "Vui lòng chọn 1 dòng job cần chạy lại!")
            return
        jobs = self._load_jobs()
        if 0 <= row < len(jobs):
            jobs[row]["status"] = "pending"
            jobs[row].pop("error_msg", None)
            jobs[row].pop("success", None)
            self._save_jobs(jobs)
            self.refresh_jobs_table()

    def delete_selected_job(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Thông báo", "Vui lòng chọn 1 dòng job cần xóa!")
            return
        jobs = self._load_jobs()
        if 0 <= row < len(jobs):
            jobs.pop(row)
            self._save_jobs(jobs)
            self.refresh_jobs_table()

    def load_logs(self):
        if not LOGS_FILE.exists():
            self.log_edit.setPlainText("Chưa có file nhật ký log.")
            return
        try:
            with open(LOGS_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
                self.log_edit.setPlainText("".join(lines[-250:]))
                self.log_edit.verticalScrollBar().setValue(self.log_edit.verticalScrollBar().maximum())
        except Exception as e:
            self.log_edit.setPlainText(f"Lỗi đọc log: {e}")

    def save_settings(self):
        # Update .env
        env_text = (
            f"LLM_BASE_URL={self.inp_base_url.text().strip()}\n"
            f"LLM_API_KEY={self.inp_api_key.text().strip()}\n"
            f"LLM_MODEL={self.inp_model.text().strip()}\n"
            "VIDEOS_DIR=./videos\n"
            "LOGS_DIR=./logs\n"
            "JOBS_FILE=./jobs.json\n"
        )
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.write(env_text)

        # Update config.json
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                cfg["headless"] = "true" in self.combo_headless.currentText()
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2, ensure_ascii=False)
            except Exception:
                pass

        QMessageBox.information(self, "Thành công", "Đã lưu cài đặt cấu hình!")

    def run_pipeline(self):
        if self.pipeline_thread and self.pipeline_thread.isRunning():
            QMessageBox.warning(self, "Cảnh báo", "Pipeline đang chạy, vui lòng đợi hoàn tất!")
            return

        self.btn_run.setEnabled(False)
        self.btn_run.setText("⏳ Đang Chạy Pipeline...")

        self.pipeline_thread = PipelineThread()
        self.pipeline_thread.log_signal.connect(self._on_pipeline_log)
        self.pipeline_thread.finished_signal.connect(self._on_pipeline_finished)
        self.pipeline_thread.start()

    def _on_pipeline_log(self, text):
        self.log_edit.appendPlainText(text)

    def _on_pipeline_finished(self, success):
        self.btn_run.setEnabled(True)
        self.btn_run.setText("🚀 Bắt đầu Chạy Pipeline")
        self.refresh_jobs_table()
        if success:
            QMessageBox.information(self, "Hoàn tất", "🎉 Pipeline đã chạy hoàn tất!")
        else:
            QMessageBox.warning(self, "Thông báo", "⚠️ Pipeline kết thúc với một số thông báo/lỗi.")

def run_gui():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    run_gui()
