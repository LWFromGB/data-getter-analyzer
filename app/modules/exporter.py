"""报告导出模块（可选功能）"""
import os
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QGroupBox, QFileDialog, QCheckBox,
    QTextEdit, QMessageBox
)


class ExporterWidget(QWidget):
    """报告导出界面"""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 导出选项
        opts_group = QGroupBox("导出选项")
        opts_layout = QVBoxLayout(opts_group)

        self.chk_include_stats = QCheckBox("包含描述性统计")
        self.chk_include_stats.setChecked(True)
        opts_layout.addWidget(self.chk_include_stats)

        self.chk_include_corr = QCheckBox("包含相关性分析")
        self.chk_include_corr.setChecked(True)
        opts_layout.addWidget(self.chk_include_corr)

        self.chk_include_data = QCheckBox("包含原始数据（前100行）")
        self.chk_include_data.setChecked(False)
        opts_layout.addWidget(self.chk_include_data)

        layout.addWidget(opts_group)

        # 导出按钮
        btn_layout = QHBoxLayout()
        self.btn_export_html = QPushButton("📄 导出 HTML 报告")
        self.btn_export_html.clicked.connect(self._export_html)
        btn_layout.addWidget(self.btn_export_html)

        self.btn_clear = QPushButton("🗑️ 清空")
        self.btn_clear.clicked.connect(self._clear)
        btn_layout.addWidget(self.btn_clear)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 预览区
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("导出预览将显示在这里...")
        layout.addWidget(self.preview)

    def _get_data(self):
        df = self.main_window.current_data
        if df is None:
            QMessageBox.warning(self, "提示", "请先加载数据")
            return None
        return df

    def _export_csv(self):
        """导出为 CSV"""
        df = self._get_data()
        if df is None:
            return

        path, _ = QFileDialog.getSaveFileName(self, "保存CSV", "", "CSV文件 (*.csv)")
        if path:
            df.to_csv(path, index=False, encoding="utf-8-sig")
            self.preview.setText(f"✅ 已导出到: {path}")

    def _export_excel(self):
        """导出为 Excel"""
        df = self._get_data()
        if df is None:
            return

        path, _ = QFileDialog.getSaveFileName(self, "保存Excel", "", "Excel文件 (*.xlsx)")
        if path:
            df.to_excel(path, index=False)
            self.preview.setText(f"✅ 已导出到: {path}")

    def _export_html(self):
        """导出 HTML 报告"""
        df = self._get_data()
        if df is None:
            return

        path, _ = QFileDialog.getSaveFileName(self, "保存HTML报告", "", "HTML文件 (*.html)")
        if not path:
            return

        html_parts = [
            "<!DOCTYPE html><html><head><meta charset='utf-8'>",
            "<title>数据分析报告</title>",
            "<style>body{font-family:sans-serif;margin:40px;background:#f5f5f5;}",
            "table{border-collapse:collapse;width:100%;margin:20px 0;}",
            "th,td{border:1px solid #ddd;padding:8px;text-align:left;}",
            "th{background:#4a90d9;color:white;}",
            "tr:nth-child(even){background:#f9f9f9;}",
            "h1{color:#333;}h2{color:#4a90d9;border-bottom:2px solid #4a90d9;padding-bottom:5px;}",
            ".card{background:white;padding:20px;margin:15px 0;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1);}",
            "</style></head><body>",
            "<h1>📊 数据分析报告</h1>",
            f"<div class='card'><h2>数据概览</h2><p>行数: {len(df)} | 列数: {len(df.columns)}</p></div>",
        ]

        if self.chk_include_stats.isChecked():
            desc = df.describe()
            html_parts.append(f"<div class='card'><h2>描述性统计</h2>{desc.to_html()}</div>")

        if self.chk_include_corr.isChecked():
            numeric_df = df.select_dtypes(include=["number"])
            if not numeric_df.empty:
                corr = numeric_df.corr()
                html_parts.append(f"<div class='card'><h2>相关性矩阵</h2>{corr.to_html()}</div>")

        if self.chk_include_data.isChecked():
            html_parts.append(f"<div class='card'><h2>数据预览（前100行）</h2>{df.head(100).to_html(index=False)}</div>")

        html_parts.append("</body></html>")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(html_parts))

        self.preview.setText(f"✅ HTML报告已导出到: {path}\n\n报告包含:\n"
                            f"- 数据概览\n"
                            f"- {'描述性统计 ✓' if self.chk_include_stats.isChecked() else ''}\n"
                            f"- {'相关性分析 ✓' if self.chk_include_corr.isChecked() else ''}\n"
                            f"- {'原始数据 ✓' if self.chk_include_data.isChecked() else ''}")

    def _clear(self):
        """清空导出预览"""
        self.preview.clear()
        self.main_window.log("导出模块已清空", "INFO")
