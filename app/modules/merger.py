"""文件合并模块 - 多文件合并为一个"""
import os
import logging
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QGroupBox, QComboBox, QFileDialog,
    QTableView, QListWidget, QAbstractItemView,
    QRadioButton, QButtonGroup
)

from app.modules.data_loader import PandasModel

logger = logging.getLogger("data_analyzer.merger")


class MergerWidget(QWidget):
    """文件合并工具"""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._file_list = []       # [(path, df), ...]
        self._merged_df = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 主布局：上下分割（可拖拽调整大小）
        from PyQt6.QtWidgets import QSplitter, QStackedWidget, QTextEdit
        from PyQt6.QtCore import Qt

        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)

        # === 上半部分：左右布局 ===
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)

        # 左上：文件列表
        files_group = QGroupBox("待合并文件")
        files_layout = QVBoxLayout(files_group)

        btn_row = QHBoxLayout()
        self.btn_add_files = QPushButton("📂 添加文件")
        self.btn_add_files.clicked.connect(self._add_files)
        btn_row.addWidget(self.btn_add_files)

        self.btn_remove_selected = QPushButton("➖ 移除")
        self.btn_remove_selected.clicked.connect(self._remove_selected)
        btn_row.addWidget(self.btn_remove_selected)

        self.btn_clear_list = QPushButton("🗑️ 清空")
        self.btn_clear_list.clicked.connect(self._clear_list)
        btn_row.addWidget(self.btn_clear_list)

        self.btn_move_up = QPushButton("⬆️")
        self.btn_move_up.setFixedWidth(30)
        self.btn_move_up.clicked.connect(self._move_up)
        btn_row.addWidget(self.btn_move_up)

        self.btn_move_down = QPushButton("⬇️")
        self.btn_move_down.setFixedWidth(30)
        self.btn_move_down.clicked.connect(self._move_down)
        btn_row.addWidget(self.btn_move_down)

        self.lbl_file_count = QLabel("0 个文件")
        btn_row.addWidget(self.lbl_file_count)
        files_layout.addLayout(btn_row)

        self.file_listwidget = QListWidget()
        self.file_listwidget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        files_layout.addWidget(self.file_listwidget)

        enc_row = QHBoxLayout()
        enc_row.addWidget(QLabel("编码:"))
        self.combo_encoding = QComboBox()
        self.combo_encoding.addItems(["utf-8", "gbk", "gb2312", "latin-1", "utf-16"])
        self.combo_encoding.setFixedWidth(80)
        enc_row.addWidget(self.combo_encoding)
        enc_row.addStretch()
        files_layout.addLayout(enc_row)

        top_layout.addWidget(files_group, 3)

        # 右上：合并方式 + 操作按钮
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        merge_group = QGroupBox("合并方式")
        merge_layout_inner = QVBoxLayout(merge_group)

        self.merge_btn_group = QButtonGroup(self)

        self.rb_vertical = QRadioButton("纵向合并（上下拼接）")
        self.rb_vertical.setChecked(True)
        self.merge_btn_group.addButton(self.rb_vertical, 0)
        merge_layout_inner.addWidget(self.rb_vertical)

        self.rb_horizontal = QRadioButton("横向合并（左右拼接）")
        self.merge_btn_group.addButton(self.rb_horizontal, 1)
        merge_layout_inner.addWidget(self.rb_horizontal)

        self.rb_join = QRadioButton("关联合并（按共同列 JOIN）")
        self.merge_btn_group.addButton(self.rb_join, 2)
        merge_layout_inner.addWidget(self.rb_join)

        right_layout.addWidget(merge_group)

        # 操作按钮
        action_layout = QVBoxLayout()

        self.btn_merge = QPushButton("🔗 执行合并")
        self.btn_merge.setStyleSheet("font-size: 13px; padding: 6px 12px;")
        self.btn_merge.clicked.connect(self._do_merge)
        action_layout.addWidget(self.btn_merge)

        btn_row2 = QHBoxLayout()
        self.btn_export = QPushButton("💾 导出")
        self.btn_export.clicked.connect(self._export_auto)
        self.btn_export.setEnabled(False)
        btn_row2.addWidget(self.btn_export)

        self.btn_to_main = QPushButton("📥 主数据")
        self.btn_to_main.clicked.connect(self._send_to_main)
        self.btn_to_main.setEnabled(False)
        btn_row2.addWidget(self.btn_to_main)

        self.btn_clear = QPushButton("🗑️ 清空")
        self.btn_clear.clicked.connect(self._clear_all)
        btn_row2.addWidget(self.btn_clear)
        action_layout.addLayout(btn_row2)

        right_layout.addLayout(action_layout)
        right_layout.addStretch()

        top_layout.addWidget(right_widget, 2)

        splitter.addWidget(top_widget)

        # === 下半部分：结果预览（可拖拽调整大小） ===
        result_widget = QWidget()
        result_layout = QVBoxLayout(result_widget)
        result_layout.setContentsMargins(4, 4, 4, 4)

        self.lbl_result_info = QLabel("合并结果预览")
        self.lbl_result_info.setStyleSheet("font-weight: bold;")
        result_layout.addWidget(self.lbl_result_info)

        self.preview_stack = QStackedWidget()

        self.table_view = QTableView()
        self.table_model = PandasModel()
        self.table_view.setModel(self.table_model)
        self.preview_stack.addWidget(self.table_view)

        self.doc_preview = QTextEdit()
        self.doc_preview.setReadOnly(True)
        self.doc_preview.setStyleSheet("font-size: 13px;")
        self.preview_stack.addWidget(self.doc_preview)

        result_layout.addWidget(self.preview_stack)
        splitter.addWidget(result_widget)

        # 设置分割比例
        splitter.setSizes([300, 400])

    def _add_files(self):
        """添加文件到列表"""
        file_filter = (
            "所有支持的格式 (*.csv *.xlsx *.xls *.json *.tsv *.parquet *.html *.db *.sqlite *.feather *.md *.pdf *.docx);;"
            "CSV (*.csv);;Excel (*.xlsx *.xls);;JSON (*.json);;TSV (*.tsv);;"
            "Parquet (*.parquet);;PDF (*.pdf);;Word (*.docx);;所有文件 (*)"
        )
        paths, _ = QFileDialog.getOpenFileNames(self, "选择文件（可多选）", "", file_filter)
        if not paths:
            return

        encoding = self.combo_encoding.currentText()
        for path in paths:
            try:
                df = self._read_file(path, encoding)
                self._file_list.append((path, df))
                name = os.path.basename(path)
                self.file_listwidget.addItem(f"{name}  ({len(df)} 行 × {len(df.columns)} 列)")
                self.main_window.log(f"已添加: {name} ({len(df)} 行)", "INFO")
            except Exception as e:
                self.main_window.log(f"❌ 读取失败: {os.path.basename(path)} - {e}", "ERROR")

        self.lbl_file_count.setText(f"{len(self._file_list)} 个文件")

    def _read_file(self, path, encoding="utf-8"):
        """读取文件"""
        from app.utils.file_reader import read_file
        return read_file(path, encoding=encoding)

    def _remove_selected(self):
        """移除选中的文件"""
        indices = sorted([i.row() for i in self.file_listwidget.selectedIndexes()], reverse=True)
        for idx in indices:
            self._file_list.pop(idx)
            self.file_listwidget.takeItem(idx)
        self.lbl_file_count.setText(f"{len(self._file_list)} 个文件")

    def _clear_list(self):
        """清空文件列表"""
        self._file_list.clear()
        self.file_listwidget.clear()
        self.lbl_file_count.setText("0 个文件")
        self.main_window.log("文件列表已清空", "INFO")

    def _move_up(self):
        """上移选中项"""
        row = self.file_listwidget.currentRow()
        if row > 0:
            self._file_list[row], self._file_list[row - 1] = self._file_list[row - 1], self._file_list[row]
            item = self.file_listwidget.takeItem(row)
            self.file_listwidget.insertItem(row - 1, item)
            self.file_listwidget.setCurrentRow(row - 1)

    def _move_down(self):
        """下移选中项"""
        row = self.file_listwidget.currentRow()
        if row < len(self._file_list) - 1:
            self._file_list[row], self._file_list[row + 1] = self._file_list[row + 1], self._file_list[row]
            item = self.file_listwidget.takeItem(row)
            self.file_listwidget.insertItem(row + 1, item)
            self.file_listwidget.setCurrentRow(row + 1)

    def _do_merge(self):
        """执行合并"""
        if len(self._file_list) < 2:
            self.main_window.log("请至少添加 2 个文件", "WARNING")
            return

        # 检测是否为文档类型
        import os
        doc_exts = {".docx", ".pdf", ".md", ".txt"}
        first_ext = os.path.splitext(self._file_list[0][0])[1].lower()
        is_document = first_ext in doc_exts

        if is_document:
            self._do_merge_documents()
        else:
            self._do_merge_tables()

    def _do_merge_documents(self):
        """合并文档类文件（保留原格式）"""
        import os

        first_ext = os.path.splitext(self._file_list[0][0])[1].lower()

        # PDF 合并：直接拼接页面
        if first_ext == ".pdf":
            self._do_merge_pdf()
            return

        # 其他文档：读取文本内容合并
        all_content = []
        for path, _ in self._file_list:
            ext = os.path.splitext(path)[1].lower()
            try:
                if ext == ".docx":
                    from docx import Document
                    doc = Document(path)
                    paragraphs = [p.text for p in doc.paragraphs]
                    all_content.append(f"--- {os.path.basename(path)} ---\n" + "\n".join(paragraphs))
                elif ext in (".md", ".txt"):
                    with open(path, "r", encoding="utf-8") as f:
                        all_content.append(f"--- {os.path.basename(path)} ---\n" + f.read())
            except Exception as e:
                all_content.append(f"--- {os.path.basename(path)} (读取失败: {e}) ---")

        self._merged_doc_content = "\n\n".join(all_content)
        self._merged_df = None
        self._is_document_merge = True
        self._is_pdf_merge = False

        self.preview_stack.setCurrentIndex(1)
        self.doc_preview.setPlainText(self._merged_doc_content)
        self.lbl_result_info.setText(f"文档合并: {len(self._file_list)} 个文件, {len(self._merged_doc_content)} 字符")
        self.btn_export.setEnabled(True)
        self.btn_to_main.setEnabled(False)
        self.main_window.log(f"✅ 文档合并完成: {len(self._file_list)} 个文件", "INFO")

    def _do_merge_pdf(self):
        """合并 PDF 文件（保留原始页面）"""
        import pymupdf

        merged_doc = pymupdf.open()

        for path, _ in self._file_list:
            try:
                doc = pymupdf.open(path)
                if doc.is_encrypted:
                    doc.authenticate("")
                merged_doc.insert_pdf(doc)
                doc.close()
                self.main_window.log(f"  已合并: {os.path.basename(path)}", "INFO")
            except Exception as e:
                self.main_window.log(f"  ❌ {os.path.basename(path)}: {e}", "ERROR")

        self._merged_pdf_doc = merged_doc
        self._merged_df = None
        self._is_document_merge = True
        self._is_pdf_merge = True

        # 预览：显示第一页的图片
        total_pages = len(merged_doc)

        # 渲染第一页为图片预览
        preview_html = f"<h3>合并后 PDF: {total_pages} 页</h3>"
        try:
            # 渲染前几页为图片
            max_preview = min(3, total_pages)
            for i in range(max_preview):
                page = merged_doc[i]
                pix = page.get_pixmap(matrix=pymupdf.Matrix(1.0, 1.0))
                img_data = pix.tobytes("png")
                import base64
                b64 = base64.b64encode(img_data).decode()
                preview_html += f'<p style="color:#888;">第 {i+1} 页:</p>'
                preview_html += f'<img src="data:image/png;base64,{b64}" style="max-width:100%;border:1px solid #ddd;margin-bottom:10px;"/>'
            if total_pages > max_preview:
                preview_html += f'<p style="color:#888;">... 还有 {total_pages - max_preview} 页</p>'
        except Exception:
            preview_html += "<p>预览生成失败</p>"

        preview_html += "<hr><p><b>文件列表:</b></p>"
        for path, _ in self._file_list:
            preview_html += f"<p>📄 {os.path.basename(path)}</p>"

        self.preview_stack.setCurrentIndex(1)
        self.doc_preview.setHtml(preview_html)
        self.lbl_result_info.setText(f"PDF 合并: {len(self._file_list)} 个文件, {total_pages} 页")
        self.btn_export.setEnabled(True)
        self.btn_to_main.setEnabled(False)
        self.main_window.log(f"✅ PDF 合并完成: {total_pages} 页", "INFO")

    def _do_merge_tables(self):
        """合并表格类文件"""
        dfs = [df for _, df in self._file_list]
        mode = self.merge_btn_group.checkedId()

        try:
            if mode == 0:
                merged = pd.concat(dfs, ignore_index=True)
                self.main_window.log(f"✅ 纵向合并: {len(merged)} 行 × {len(merged.columns)} 列", "INFO")
            elif mode == 1:
                merged = pd.concat(dfs, axis=1)
                self.main_window.log(f"✅ 横向合并: {len(merged)} 行 × {len(merged.columns)} 列", "INFO")
            else:
                merged = dfs[0]
                for i, df in enumerate(dfs[1:], 1):
                    common_cols = list(set(merged.columns) & set(df.columns))
                    if common_cols:
                        merged = merged.merge(df, on=common_cols, how="outer")
                        self.main_window.log(f"  第 {i+1} 个文件按 {common_cols} 关联", "INFO")
                    else:
                        merged = pd.concat([merged, df], axis=1)
                        self.main_window.log(f"  第 {i+1} 个文件无共同列，横向拼接", "WARNING")
                self.main_window.log(f"✅ 关联合并: {len(merged)} 行 × {len(merged.columns)} 列", "INFO")

            self._merged_df = merged
            self._is_document_merge = False

            # 显示表格预览
            self.preview_stack.setCurrentIndex(0)
            self.table_model.update_data(merged)
            self.lbl_result_info.setText(f"合并结果: {len(merged)} 行 × {len(merged.columns)} 列")
            self.btn_export.setEnabled(True)
            self.btn_to_main.setEnabled(True)

        except Exception as e:
            self.main_window.log(f"❌ 合并失败: {e}", "ERROR")

    def _export_auto(self):
        """导出为原格式"""
        import os

        # 文档合并导出
        if getattr(self, '_is_document_merge', False):
            # PDF 合并：直接保存 PDF
            if getattr(self, '_is_pdf_merge', False):
                path, _ = QFileDialog.getSaveFileName(self, "导出合并 PDF", "", "PDF文件 (*.pdf)")
                if not path:
                    return
                try:
                    self._merged_pdf_doc.save(path)
                    from app.utils.exporter import get_file_size_str
                    self.main_window.log(f"✅ 已导出 PDF: {path} ({get_file_size_str(path)})", "INFO")
                except Exception as e:
                    self.main_window.log(f"❌ 导出失败: {e}", "ERROR")
                return

            first_ext = os.path.splitext(self._file_list[0][0])[1].lower()
            ext_map = {
                ".docx": ("Word文件 (*.docx)", ".docx"),
                ".pdf": ("PDF文件 (*.pdf)", ".pdf"),
                ".md": ("Markdown文件 (*.md)", ".md"),
                ".txt": ("文本文件 (*.txt)", ".txt"),
            }
            filter_str, ext = ext_map.get(first_ext, ("文本文件 (*.txt)", ".txt"))
            path, _ = QFileDialog.getSaveFileName(self, "导出合并文档", "", filter_str)
            if not path:
                return

            try:
                out_ext = os.path.splitext(path)[1].lower()
                if out_ext == ".docx":
                    from docx import Document
                    doc = Document()
                    for line in self._merged_doc_content.splitlines():
                        if line.startswith("---") and line.endswith("---"):
                            doc.add_heading(line.strip("- "), level=2)
                        elif line.strip():
                            doc.add_paragraph(line)
                    doc.save(path)
                else:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(self._merged_doc_content)

                from app.utils.exporter import get_file_size_str
                self.main_window.log(f"✅ 已导出: {path} ({get_file_size_str(path)})", "INFO")
            except Exception as e:
                self.main_window.log(f"❌ 导出失败: {e}", "ERROR")
            return

        # 表格合并导出
        if self._merged_df is None:
            return

        if self._file_list:
            first_ext = os.path.splitext(self._file_list[0][0])[1].lower()
        else:
            first_ext = ".csv"

        ext_map = {
            ".csv": ("CSV文件 (*.csv)", ".csv"),
            ".xlsx": ("Excel文件 (*.xlsx)", ".xlsx"),
            ".xls": ("Excel文件 (*.xlsx)", ".xlsx"),
            ".json": ("JSON文件 (*.json)", ".json"),
            ".tsv": ("TSV文件 (*.tsv)", ".tsv"),
            ".parquet": ("Parquet文件 (*.parquet)", ".parquet"),
        }
        filter_str, ext = ext_map.get(first_ext, ("CSV文件 (*.csv)", ".csv"))

        path, _ = QFileDialog.getSaveFileName(self, "导出合并结果", "", filter_str)
        if not path:
            return

        try:
            from app.utils.exporter import export_dataframe, get_file_size_str
            out_ext = os.path.splitext(path)[1].lower()
            fmt_map = {".csv": "csv", ".xlsx": "xlsx", ".json": "json", ".tsv": "tsv", ".parquet": "parquet"}
            fmt = fmt_map.get(out_ext, "csv")

            export_dataframe(self._merged_df, path, fmt)
            size_str = get_file_size_str(path)
            self.main_window.log(f"✅ 已导出: {path} ({len(self._merged_df)} 行, {size_str})", "INFO")
        except Exception as e:
            self.main_window.log(f"❌ 导出失败: {e}", "ERROR")

    def _send_to_main(self):
        """发送到主数据"""
        if self._merged_df is not None:
            self.main_window.set_data(self._merged_df.copy())
            self.main_window.log(f"✅ 合并数据 ({len(self._merged_df)} 行) 已设置为当前工作数据", "INFO")

    def _clear_all(self):
        """清空所有"""
        self._clear_list()
        self._merged_df = None
        self.table_model.update_data(pd.DataFrame())
        self.lbl_result_info.setText("未合并")
        self.btn_export.setEnabled(False)
        self.btn_to_main.setEnabled(False)
        self.main_window.log("合并模块已清空", "INFO")
