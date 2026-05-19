"""文件格式转换器 - 支持多种数据文件格式互转"""
import os
import json
import logging
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QGroupBox, QComboBox, QFileDialog,
    QTableView, QListWidget, QAbstractItemView,
    QCheckBox, QLineEdit, QMessageBox
)
from PyQt6.QtCore import QThread, pyqtSignal

from app.modules.data_loader import PandasModel

logger = logging.getLogger("data_analyzer.converter")

# 支持的格式
INPUT_FORMATS = {
    "CSV (.csv)": "csv",
    "Excel (.xlsx)": "xlsx",
    "Excel 旧版 (.xls)": "xls",
    "JSON (.json)": "json",
    "TSV (.tsv)": "tsv",
    "Parquet (.parquet)": "parquet",
    "HTML 表格 (.html)": "html",
    "SQLite (.db/.sqlite)": "sqlite",
    "Feather (.feather)": "feather",
    "Markdown 表格 (.md)": "md",
    "PDF 表格 (.pdf)": "pdf",
    "Word 表格 (.docx)": "docx",
}

OUTPUT_FORMATS = {
    "CSV (.csv)": "csv",
    "Excel (.xlsx)": "xlsx",
    "JSON (.json)": "json",
    "TSV (.tsv)": "tsv",
    "Parquet (.parquet)": "parquet",
    "HTML (.html)": "html",
    "SQLite (.db)": "sqlite",
    "Feather (.feather)": "feather",
    "Markdown (.md)": "md",
    "LaTeX (.tex)": "latex",
    "XML (.xml)": "xml",
    "Word (.docx)": "docx",
    "PDF (.pdf)": "pdf",
}

FILE_FILTERS = (
    "所有支持的格式 (*.csv *.xlsx *.xls *.json *.tsv *.parquet *.html *.db *.sqlite *.feather *.md *.pdf *.docx);;"
    "CSV (*.csv);;Excel (*.xlsx *.xls);;JSON (*.json);;TSV (*.tsv);;"
    "Parquet (*.parquet);;HTML (*.html);;SQLite (*.db *.sqlite);;"
    "Feather (*.feather);;Markdown (*.md);;PDF (*.pdf);;Word (*.docx);;所有文件 (*)"
)


class FileReadThread(QThread):
    """后台文件读取线程（避免 UI 卡住）"""
    finished = pyqtSignal(object)  # DataFrame 或 错误字符串
    progress = pyqtSignal(str)

    def __init__(self, path, encoding, pdf_engine, pdf_password):
        super().__init__()
        self.path = path
        self.encoding = encoding
        self.pdf_engine = pdf_engine
        self.pdf_password = pdf_password

    def run(self):
        try:
            self.progress.emit(f"正在读取: {os.path.basename(self.path)}...")
            from app.utils.file_reader import read_file
            df = read_file(
                self.path,
                encoding=self.encoding,
                pdf_engine=self.pdf_engine,
                pdf_password=self.pdf_password
            )
            self.finished.emit(df)
        except Exception as e:
            import traceback
            self.finished.emit(f"文件读取失败: {e}\n{traceback.format_exc()}")


class ConvertThread(QThread):
    """后台转换线程"""
    finished = pyqtSignal(str)  # 成功消息或错误消息
    progress = pyqtSignal(str)

    def __init__(self, df, output_path, output_format, options):
        super().__init__()
        self.df = df
        self.output_path = output_path
        self.output_format = output_format
        self.options = options

    def run(self):
        try:
            fmt = self.output_format
            df = self.df
            path = self.output_path
            self.progress.emit(f"正在转换为 {fmt}...")

            if fmt == "csv":
                encoding = self.options.get("encoding", "utf-8-sig")
                df.to_csv(path, index=False, encoding=encoding)
            elif fmt == "xlsx":
                df.to_excel(path, index=False)
            elif fmt == "json":
                orient = self.options.get("orient", "records")
                df.to_json(path, orient=orient, force_ascii=False, indent=2)
            elif fmt == "tsv":
                df.to_csv(path, index=False, sep="\t", encoding="utf-8-sig")
            elif fmt == "parquet":
                df.to_parquet(path, index=False)
            elif fmt == "html":
                html = df.to_html(index=False, classes="table", border=1)
                full_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>数据表格</title>
<style>
body {{ font-family: sans-serif; margin: 20px; }}
.table {{ border-collapse: collapse; width: 100%; }}
.table th, .table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
.table th {{ background: #4a90d9; color: white; }}
.table tr:nth-child(even) {{ background: #f9f9f9; }}
</style></head><body>{html}</body></html>"""
                with open(path, "w", encoding="utf-8") as f:
                    f.write(full_html)
            elif fmt == "sqlite":
                import sqlite3
                table_name = self.options.get("table_name", "data")
                conn = sqlite3.connect(path)
                df.to_sql(table_name, conn, if_exists="replace", index=False)
                conn.close()
            elif fmt == "feather":
                df.to_feather(path)
            elif fmt == "md":
                md_text = df.to_markdown(index=False)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(md_text)
            elif fmt == "latex":
                latex_text = df.to_latex(index=False)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(latex_text)
            elif fmt == "xml":
                df.to_xml(path, index=False)
            elif fmt == "docx":
                self._export_docx(df, path)
            elif fmt == "pdf":
                self._export_pdf(df, path)
            else:
                self.finished.emit(f"❌ 不支持的输出格式: {fmt}")
                return

            size = os.path.getsize(path)
            size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / 1024 / 1024:.1f} MB"
            self.finished.emit(f"✅ 转换完成: {path}\n大小: {size_str} | {len(df)} 行 × {len(df.columns)} 列")

        except Exception as e:
            logger.error(f"转换失败: {e}", exc_info=True)
            self.finished.emit(f"❌ 转换失败: {str(e)}")

    def _export_docx(self, df, path):
        """导出为 Word 表格"""
        from docx import Document
        from docx.shared import Pt, Inches

        doc = Document()
        doc.add_heading("数据表格", level=1)

        # 创建表格
        table = doc.add_table(rows=1, cols=len(df.columns))
        table.style = "Table Grid"

        # 表头
        for i, col in enumerate(df.columns):
            table.rows[0].cells[i].text = str(col)

        # 数据行
        for _, row in df.iterrows():
            row_cells = table.add_row().cells
            for i, val in enumerate(row):
                row_cells[i].text = str(val) if pd.notna(val) else ""

        doc.save(path)

    def _export_pdf(self, df, path):
        """导出为 PDF 表格（使用 HTML 中转）"""
        # 生成 HTML 表格，然后用简单方式写入 PDF
        # 这里用 matplotlib 生成表格图片再存 PDF
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages

        with PdfPages(path) as pdf:
            # 每页最多显示 40 行
            page_size = 40
            total_pages = (len(df) + page_size - 1) // page_size

            for page in range(total_pages):
                start = page * page_size
                end = min(start + page_size, len(df))
                page_df = df.iloc[start:end]

                fig, ax = plt.subplots(figsize=(11, 8))
                ax.axis("off")
                ax.set_title(f"数据表格 (第 {page + 1}/{total_pages} 页)", fontsize=12, pad=20)

                # 创建表格
                col_labels = [str(c) for c in page_df.columns]
                cell_text = [[str(v) if pd.notna(v) else "" for v in row] for _, row in page_df.iterrows()]

                table = ax.table(
                    cellText=cell_text,
                    colLabels=col_labels,
                    loc="center",
                    cellLoc="left"
                )
                table.auto_set_font_size(False)
                table.set_fontsize(7)
                table.scale(1.2, 1.3)

                pdf.savefig(fig, bbox_inches="tight")
                plt.close(fig)


class ConverterWidget(QWidget):
    """文件格式转换器界面"""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._source_df = None
        self._convert_thread = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # === 输出设置（放在最上面，先选格式） ===
        output_group = QGroupBox("输出设置（先选择目标格式）")
        output_layout = QVBoxLayout(output_group)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("输出格式:"))
        self.combo_output_format = QComboBox()
        self.combo_output_format.addItems(OUTPUT_FORMATS.keys())
        row2.addWidget(self.combo_output_format)

        row2.addWidget(QLabel("  输出编码:"))
        self.combo_output_encoding = QComboBox()
        self.combo_output_encoding.addItems(["utf-8-sig", "utf-8", "gbk", "gb2312"])
        self.combo_output_encoding.setFixedWidth(100)
        row2.addWidget(self.combo_output_encoding)

        row2.addWidget(QLabel("  JSON orient:"))
        self.combo_json_orient = QComboBox()
        self.combo_json_orient.addItems(["records", "columns", "index", "values", "split"])
        self.combo_json_orient.setFixedWidth(100)
        row2.addWidget(self.combo_json_orient)

        row2.addStretch()
        output_layout.addLayout(row2)
        layout.addWidget(output_group)

        # === 输入区 ===
        input_group = QGroupBox("输入文件")
        input_layout = QVBoxLayout(input_group)

        row1 = QHBoxLayout()
        self.btn_select_file = QPushButton("📂 选择文件")
        self.btn_select_file.clicked.connect(self._select_file)
        row1.addWidget(self.btn_select_file)

        self.btn_use_current = QPushButton("📋 使用当前数据")
        self.btn_use_current.clicked.connect(self._use_current_data)
        row1.addWidget(self.btn_use_current)

        self.lbl_input_info = QLabel("未选择文件")
        row1.addWidget(self.lbl_input_info)
        row1.addStretch()
        input_layout.addLayout(row1)

        # 编码选择（CSV用）
        row_enc = QHBoxLayout()
        row_enc.addWidget(QLabel("输入编码:"))
        self.combo_input_encoding = QComboBox()
        self.combo_input_encoding.addItems(["utf-8", "gbk", "gb2312", "latin-1", "utf-16"])
        self.combo_input_encoding.setFixedWidth(100)
        row_enc.addWidget(self.combo_input_encoding)

        row_enc.addWidget(QLabel("  SQLite表名:"))
        self.input_table_name = QLineEdit("data")
        self.input_table_name.setFixedWidth(120)
        row_enc.addWidget(self.input_table_name)

        row_enc.addWidget(QLabel("  PDF引擎:"))
        self.combo_pdf_engine = QComboBox()
        self.combo_pdf_engine.addItems(["自动（PyMuPDF4LLM优先）", "PyMuPDF4LLM（快速）", "MinerU（AI高精度）"])
        self.combo_pdf_engine.setFixedWidth(200)
        row_enc.addWidget(self.combo_pdf_engine)

        row_enc.addStretch()
        input_layout.addLayout(row_enc)

        layout.addWidget(input_group)

        # 转换按钮
        row3 = QHBoxLayout()
        self.btn_convert = QPushButton("🔄 转换并保存")
        self.btn_convert.setStyleSheet("font-size: 13px; padding: 6px 16px;")
        self.btn_convert.clicked.connect(self._convert)
        row3.addWidget(self.btn_convert)

        self.btn_batch = QPushButton("📦 批量转换（多文件）")
        self.btn_batch.clicked.connect(self._batch_convert)
        row3.addWidget(self.btn_batch)

        self.btn_clear = QPushButton("🗑️ 清空")
        self.btn_clear.clicked.connect(self._clear)
        row3.addWidget(self.btn_clear)

        row3.addStretch()
        layout.addLayout(row3)

        # === 预览区 ===
        preview_group = QGroupBox("数据预览（前 50 行）")
        preview_layout = QVBoxLayout(preview_group)

        self.table_view = QTableView()
        self.table_model = PandasModel()
        self.table_view.setModel(self.table_model)
        preview_layout.addWidget(self.table_view)

        layout.addWidget(preview_group)

    def _select_file(self):
        """选择输入文件"""
        path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", FILE_FILTERS)
        if not path:
            return

        self._source_path = path
        fmt_key = self.combo_output_format.currentText()
        fmt = OUTPUT_FORMATS[fmt_key]

        # 只有输出为表格格式时才解析为 DataFrame
        table_formats = ["csv", "xlsx", "tsv", "parquet", "sqlite", "feather"]

        if fmt in table_formats:
            # 先检测 PDF 是否需要密码（在主线程处理）
            pdf_password = ""
            ext = os.path.splitext(path)[1].lower()
            if ext == ".pdf":
                import pymupdf
                doc = pymupdf.open(path)
                if doc.is_encrypted:
                    doc.close()
                    from PyQt6.QtWidgets import QInputDialog
                    pwd, ok = QInputDialog.getText(self, "PDF 需要密码", "请输入 PDF 密码:")
                    if ok:
                        pdf_password = pwd
                    else:
                        return
                else:
                    doc.close()
            self._pdf_password = pdf_password

            # 异步读取，不阻塞 UI
            self.btn_select_file.setEnabled(False)
            self.lbl_input_info.setText("正在读取...")
            self.main_window.log(f"开始读取: {path}", "INFO")

            # 获取 PDF 引擎和密码设置
            engine = self.combo_pdf_engine.currentText()
            if "MinerU" in engine and "优先" not in engine:
                pdf_engine = "mineru"
            elif "PyMuPDF4LLM" in engine and "优先" not in engine:
                pdf_engine = "pymupdf4llm"
            else:
                pdf_engine = "auto"

            self._read_thread = FileReadThread(
                path,
                self.combo_input_encoding.currentText(),
                pdf_engine,
                self._pdf_password
            )
            self._read_thread.progress.connect(lambda msg: self.main_window.log(msg, "INFO"))
            self._read_thread.finished.connect(self._on_file_read_done)
            self._read_thread.start()
        else:
            # 非表格输出，只记录路径，不解析
            self._source_df = None
            self.table_model.update_data(pd.DataFrame())
            self.lbl_input_info.setText(
                f"{os.path.basename(path)} → 将保留原文档布局输出为 {fmt.upper()}"
            )
            self.main_window.log(f"已选择: {path}（将保留原布局转换）", "INFO")

    def _on_file_read_done(self, result):
        """文件读取完成回调"""
        self.btn_select_file.setEnabled(True)

        if isinstance(result, pd.DataFrame):
            self._source_df = result
            self.table_model.update_data(result.head(50))
            self.lbl_input_info.setText(
                f"{os.path.basename(self._source_path)} ({len(result)} 行 × {len(result.columns)} 列)"
            )
            self.main_window.log(f"✅ 已加载: {len(result)} 行 × {len(result.columns)} 列", "INFO")
        else:
            self._source_df = None
            self.lbl_input_info.setText("读取失败")
            self.main_window.log(str(result), "ERROR")

    def _read_file(self, path, encoding="utf-8"):
        """读取文件（使用统一文件读取模块）"""
        from app.utils.file_reader import read_file

        # 获取 PDF 引擎设置
        engine = "auto"
        if hasattr(self, 'combo_pdf_engine'):
            choice = self.combo_pdf_engine.currentText()
            if "MinerU" in choice:
                engine = "mineru"
            elif "PyMuPDF4LLM" in choice:
                engine = "pymupdf4llm"

        password = getattr(self, '_pdf_password', "") or ""
        return read_file(path, encoding=encoding, pdf_engine=engine, pdf_password=password)

    def _read_markdown_table(self, path, encoding="utf-8"):
        """解析 Markdown 表格"""
        with open(path, "r", encoding=encoding) as f:
            lines = f.readlines()

        # 找到表格行（包含 | 的行）
        table_lines = [l.strip() for l in lines if "|" in l]
        if len(table_lines) < 2:
            raise ValueError("未找到 Markdown 表格")

        # 解析表头
        headers = [c.strip() for c in table_lines[0].split("|") if c.strip()]
        # 跳过分隔行（---）
        data_lines = [l for l in table_lines[1:] if not all(c in "-| " for c in l)]
        rows = []
        for line in data_lines:
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) == len(headers):
                rows.append(cells)

        return pd.DataFrame(rows, columns=headers)

    def _read_pdf(self, path):
        """读取 PDF - 支持两种模式：MinerU（AI高精度）/ PyMuPDF4LLM（快速）"""
        import pymupdf

        # 检测是否加密
        password = ""
        doc = pymupdf.open(path)
        if doc.is_encrypted:
            doc.close()
            from PyQt6.QtWidgets import QInputDialog
            pwd, ok = QInputDialog.getText(
                self, "PDF 需要密码", "请输入 PDF 密码:",
            )
            if ok:
                password = pwd
                doc = pymupdf.open(path)
                if not doc.authenticate(password):
                    doc.close()
                    raise ValueError("PDF 密码错误")
                doc.close()
            else:
                raise ValueError("取消打开 PDF")
        else:
            doc.close()

        # 保存密码供布局转换使用
        self._pdf_password = password

        # 根据选项决定引擎
        engine = getattr(self, 'combo_pdf_engine', None)
        engine_choice = engine.currentText() if engine else "自动（PyMuPDF4LLM优先）"

        if engine_choice == "MinerU（AI高精度）":
            return self._read_pdf_mineru(path, password)
        elif engine_choice == "PyMuPDF4LLM（快速）":
            return self._read_pdf_pymupdf4llm(path, password)
        else:
            # 自动：先尝试 PyMuPDF4LLM，失败回退 MinerU
            try:
                return self._read_pdf_pymupdf4llm(path, password)
            except Exception as e:
                logger.warning(f"PyMuPDF4LLM 解析失败，尝试 MinerU: {e}")

            try:
                return self._read_pdf_mineru(path, password)
            except Exception as e:
                err_str = str(e)
                if "No module named" in err_str or "cannot import" in err_str:
                    logger.info(f"MinerU 不可用: {e}")
                else:
                    logger.warning(f"MinerU 也失败: {e}")

            raise ValueError("PDF 解析失败，两种引擎均无法处理")

    def _read_pdf_mineru(self, path, password=""):
        """MinerU AI 高精度模式"""
        import tempfile
        import os
        import pymupdf

        # 先测试 MinerU 是否可用
        try:
            import transformers  # MinerU 依赖
            from mineru.cli.common import do_parse
        except Exception as e:
            raise ImportError(f"mineru.cli.common: {e}")

        logger.info("使用 MinerU AI 模式解析 PDF...")

        # 如果有密码，先解密再传给 MinerU
        if password:
            doc = pymupdf.open(path)
            doc.authenticate(password)
            pdf_bytes = doc.tobytes(deflate=True)
            doc.close()
        else:
            # 尝试用空密码解密（有些 PDF 有权限限制但无用户密码）
            doc = pymupdf.open(path)
            if doc.is_encrypted:
                doc.authenticate("")
            pdf_bytes = doc.tobytes(deflate=True)
            doc.close()

        # 创建临时输出目录
        temp_dir = tempfile.mkdtemp()
        file_name = os.path.splitext(os.path.basename(path))[0]

        # 调用 MinerU 解析
        do_parse(
            output_dir=temp_dir,
            pdf_file_names=[file_name],
            pdf_bytes_list=[pdf_bytes],
            p_lang_list=["ch"],
            backend="pipeline",
            parse_method="auto",
            table_enable=True,
            f_dump_md=True,
            f_dump_middle_json=False,
            f_dump_model_output=False,
            f_dump_orig_pdf=False,
            f_dump_content_list=False,
            f_draw_layout_bbox=False,
            f_draw_span_bbox=False,
        )

        # 读取输出的 Markdown 文件
        md_file = os.path.join(temp_dir, file_name, f"{file_name}.md")
        if not os.path.exists(md_file):
            # 尝试其他可能的路径
            for root, dirs, files in os.walk(temp_dir):
                for f in files:
                    if f.endswith(".md"):
                        md_file = os.path.join(root, f)
                        break

        if not os.path.exists(md_file):
            raise ValueError("MinerU 未生成 Markdown 输出")

        with open(md_file, "r", encoding="utf-8") as f:
            md_content = f.read()

        logger.info(f"MinerU 解析完成，Markdown 长度: {len(md_content)}")

        # 从输出中提取表格（MinerU 可能输出 Markdown 表格或 HTML 表格）
        # 先尝试 HTML 表格
        if "<table" in md_content:
            try:
                dfs = pd.read_html(md_content)
                if dfs:
                    # 合并所有表格
                    if len(dfs) == 1:
                        return dfs[0]
                    main_cols = max(dfs, key=lambda d: len(d)).shape[1]
                    same_structure = [df for df in dfs if df.shape[1] == main_cols and len(df) > 0]
                    if same_structure:
                        return pd.concat(same_structure, ignore_index=True)
                    return max(dfs, key=len)
            except Exception as e:
                logger.warning(f"HTML 表格解析失败: {e}")

        # 再尝试 Markdown 表格
        tables = self._extract_tables_from_markdown(md_content)
        if tables:
            all_dfs = []
            for table_lines in tables:
                df = self._parse_markdown_table_lines(table_lines)
                if df is not None and not df.empty:
                    all_dfs.append(df)

            if all_dfs:
                if len(all_dfs) == 1:
                    return all_dfs[0]
                main_cols = max(all_dfs, key=len).shape[1]
                same_structure = [df for df in all_dfs if df.shape[1] == main_cols]
                if same_structure:
                    return pd.concat(same_structure, ignore_index=True)
                return max(all_dfs, key=len)

        # 没有表格，返回文本
        lines = [l.strip() for l in md_content.splitlines() if l.strip() and not l.startswith("#")]
        if lines:
            return pd.DataFrame({"内容": lines})

        raise ValueError("MinerU 未提取到有效数据")

    def _read_pdf_pymupdf4llm(self, path, password=""):
        """PyMuPDF4LLM 快速模式"""
        import pymupdf4llm
        import pymupdf

        logger.info("使用 PyMuPDF4LLM 快速模式解析 PDF...")

        # 提取 Markdown
        if password:
            doc = pymupdf.open(path)
            doc.authenticate(password)
            md_text = pymupdf4llm.to_markdown(doc)
            doc.close()
        else:
            md_text = pymupdf4llm.to_markdown(path)

        # 从 Markdown 中提取表格
        tables = self._extract_tables_from_markdown(md_text)

        if tables:
            # 合并所有表格
            all_dfs = []
            for table_lines in tables:
                df = self._parse_markdown_table_lines(table_lines)
                if df is not None and not df.empty:
                    all_dfs.append(df)

            if all_dfs:
                # 找最大的表格，或合并相同结构的表格
                if len(all_dfs) == 1:
                    return all_dfs[0]

                # 尝试合并列数相同的表格
                main_cols = max(all_dfs, key=len).shape[1]
                same_structure = [df for df in all_dfs if df.shape[1] == main_cols]
                if same_structure:
                    return pd.concat(same_structure, ignore_index=True)
                else:
                    return max(all_dfs, key=len)

        # 没有表格，返回文本行
        lines = [l.strip() for l in md_text.splitlines() if l.strip() and not l.startswith("#")]
        if lines:
            return pd.DataFrame({"内容": lines})

        raise ValueError("PDF 中未找到表格或文本内容")

    def _extract_tables_from_markdown(self, md_text):
        """从 Markdown 文本中提取所有表格"""
        tables = []
        current_table = []
        in_table = False

        for line in md_text.splitlines():
            # Markdown 表格行以 | 开头
            if "|" in line and line.strip().startswith("|"):
                in_table = True
                current_table.append(line)
            else:
                if in_table and current_table:
                    if len(current_table) >= 2:  # 至少表头+分隔行
                        tables.append(current_table)
                    current_table = []
                    in_table = False

        # 最后一个表格
        if current_table and len(current_table) >= 2:
            tables.append(current_table)

        return tables

    def _parse_markdown_table_lines(self, lines):
        """解析 Markdown 表格行为 DataFrame"""
        if len(lines) < 2:
            return None

        # 解析表头
        headers = [c.strip() for c in lines[0].split("|") if c.strip()]

        # 跳过分隔行（---|---）
        data_lines = []
        for line in lines[1:]:
            # 跳过分隔行
            cleaned = line.replace("|", "").replace("-", "").replace(":", "").strip()
            if not cleaned:
                continue
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if cells:
                data_lines.append(cells)

        if not data_lines:
            return None

        # 对齐列数
        n_cols = len(headers)
        clean_rows = []
        for row in data_lines:
            if len(row) > n_cols:
                row = row[:n_cols]
            elif len(row) < n_cols:
                row = row + [""] * (n_cols - len(row))
            clean_rows.append(row)

        return pd.DataFrame(clean_rows, columns=headers)

        return pd.DataFrame(all_rows)

    def _text_lines_to_dataframe(self, lines):
        """将文本行智能分列"""
        import re

        # 检测是否有固定分隔符
        # 尝试制表符分割
        tab_counts = [line.count("\t") for line in lines[:10]]
        if tab_counts and min(tab_counts) > 0 and max(tab_counts) == min(tab_counts):
            rows = [line.split("\t") for line in lines]
            headers = rows[0]
            return pd.DataFrame(rows[1:], columns=headers)

        # 尝试多空格分割（固定宽度格式）
        space_split = [re.split(r'\s{2,}', line) for line in lines]
        col_counts = [len(row) for row in space_split[:10]]

        if col_counts and min(col_counts) > 1 and max(col_counts) == min(col_counts):
            headers = space_split[0]
            data = space_split[1:]
            return pd.DataFrame(data, columns=headers)

        # 无法分列，返回单列
        return pd.DataFrame({"内容": lines})

    def _read_docx(self, path):
        """读取 Word 文档中的表格"""
        from docx import Document

        doc = Document(path)
        all_dfs = []

        for table in doc.tables:
            rows = []
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                rows.append(cells)

            if len(rows) >= 2:
                headers = rows[0]
                data = rows[1:]
                all_dfs.append(pd.DataFrame(data, columns=headers))

        if all_dfs:
            return pd.concat(all_dfs, ignore_index=True)

        # 没有表格，提取段落文本
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        if paragraphs:
            return pd.DataFrame({"内容": paragraphs})

        raise ValueError("Word 文档中未找到表格或文本内容")

    def _use_current_data(self):
        """使用主窗口当前数据"""
        df = self.main_window.current_data
        if df is None:
            self.main_window.log("当前没有加载数据", "WARNING")
            return
        self._source_df = df.copy()
        self.table_model.update_data(df.head(50))
        self.lbl_input_info.setText(f"当前数据 ({len(df)} 行 × {len(df.columns)} 列)")
        self.main_window.log("已使用当前工作数据", "INFO")

    def _convert(self):
        """转换并保存"""
        fmt_key = self.combo_output_format.currentText()
        fmt = OUTPUT_FORMATS[fmt_key]

        # 表格格式需要 DataFrame
        table_formats = ["csv", "xlsx", "tsv", "parquet", "sqlite", "feather"]

        if fmt in table_formats:
            if self._source_df is None or self._source_df.empty:
                self.main_window.log("请先选择输入文件或使用当前数据", "WARNING")
                return
        else:
            # 非表格格式：可以用原文件直接转换
            if self._source_df is None and not hasattr(self, '_source_path'):
                self.main_window.log("请先选择输入文件", "WARNING")
                return

        # 构建保存文件对话框
        ext_map = {
            "csv": "CSV (*.csv)", "xlsx": "Excel (*.xlsx)", "json": "JSON (*.json)",
            "tsv": "TSV (*.tsv)", "parquet": "Parquet (*.parquet)", "html": "HTML (*.html)",
            "sqlite": "SQLite (*.db)", "feather": "Feather (*.feather)",
            "md": "Markdown (*.md)", "latex": "LaTeX (*.tex)", "xml": "XML (*.xml)",
            "docx": "Word (*.docx)", "pdf": "PDF (*.pdf)",
        }
        filter_str = ext_map.get(fmt, "所有文件 (*)")

        path, _ = QFileDialog.getSaveFileName(self, "保存转换文件", "", filter_str)
        if not path:
            return

        # 非表格格式：保留原布局转换
        if fmt not in table_formats and self._source_df is None:
            self._convert_preserve_layout(self._source_path, path, fmt)
            return

        options = {
            "encoding": self.combo_output_encoding.currentText(),
            "orient": self.combo_json_orient.currentText(),
            "table_name": self.input_table_name.text() or "data",
        }

        self.btn_convert.setEnabled(False)
        self._convert_thread = ConvertThread(self._source_df, path, fmt, options)
        self._convert_thread.progress.connect(lambda msg: self.main_window.log(msg, "INFO"))
        self._convert_thread.finished.connect(self._on_convert_done)
        self._convert_thread.start()

    def _convert_preserve_layout(self, source_path, output_path, fmt):
        """保留原文档布局转换（PDF→Word, PDF→HTML 等）"""
        import os

        try:
            ext = os.path.splitext(source_path)[1].lower()
            self.main_window.log(f"保留布局转换: {ext} → {fmt}", "INFO")

            if ext == ".pdf" and fmt == "docx":
                self._pdf_to_word_layout(source_path, output_path)
            elif ext == ".pdf" and fmt == "html":
                self._pdf_to_html_layout(source_path, output_path)
            elif ext == ".pdf" and fmt == "md":
                self._pdf_to_markdown_layout(source_path, output_path)
            elif ext == ".docx" and fmt == "pdf":
                self._word_to_pdf(source_path, output_path)
            elif ext == ".docx" and fmt == "html":
                self._word_to_html(source_path, output_path)
            elif ext == ".docx" and fmt == "md":
                self._word_to_markdown(source_path, output_path)
            else:
                # 通用：先读为文本再输出
                self.main_window.log(f"不支持 {ext} → {fmt} 的布局保留转换，尝试通用转换", "WARNING")
                encoding = self.combo_input_encoding.currentText()
                df = self._read_file(source_path, encoding)
                options = {"encoding": self.combo_output_encoding.currentText(), "orient": "records", "table_name": "data"}
                thread = ConvertThread(df, output_path, fmt, options)
                thread.run()
                return

            size = os.path.getsize(output_path)
            size_str = f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/1024/1024:.1f} MB"
            self.main_window.log(f"✅ 转换完成: {output_path} ({size_str})", "INFO")
        except Exception as e:
            self.main_window.log(f"❌ 转换失败: {e}", "ERROR")

    def _pdf_to_word_layout(self, pdf_path, docx_path):
        """PDF → Word 保留布局"""
        from app.utils.pdf_parser import get_pdf_markdown
        from docx import Document

        password = getattr(self, '_pdf_password', "") or ""
        md_text = get_pdf_markdown(pdf_path, password)

        word_doc = Document()
        for line in md_text.splitlines():
            if not line.strip():
                continue
            if line.startswith("# "):
                word_doc.add_heading(line[2:], level=1)
            elif line.startswith("## "):
                word_doc.add_heading(line[3:], level=2)
            elif line.startswith("### "):
                word_doc.add_heading(line[4:], level=3)
            elif line.startswith("|"):
                word_doc.add_paragraph(line, style="No Spacing")
            else:
                word_doc.add_paragraph(line)

        word_doc.save(docx_path)

    def _pdf_to_html_layout(self, pdf_path, html_path):
        """PDF → HTML 保留布局"""
        from app.utils.pdf_parser import get_pdf_markdown
        import markdown

        password = getattr(self, '_pdf_password', "") or ""
        md_text = get_pdf_markdown(pdf_path, password)

        try:
            html_body = markdown.markdown(md_text, extensions=["tables"])
        except Exception:
            html_body = f"<pre>{md_text}</pre>"

        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>转换文档</title>
<style>body{{font-family:sans-serif;margin:40px;}}table{{border-collapse:collapse;width:100%;}}
th,td{{border:1px solid #ddd;padding:8px;text-align:left;}}th{{background:#4a90d9;color:white;}}</style>
</head><body>{html_body}</body></html>"""

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

    def _pdf_to_markdown_layout(self, pdf_path, md_path):
        """PDF → Markdown 保留布局"""
        from app.utils.pdf_parser import get_pdf_markdown

        password = getattr(self, '_pdf_password', "") or ""
        md_text = get_pdf_markdown(pdf_path, password)

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_text)

    def _word_to_pdf(self, docx_path, pdf_path):
        """Word → PDF"""
        # 简单方案：提取文本写入 PDF
        from docx import Document
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages

        doc = Document(docx_path)
        lines = [p.text for p in doc.paragraphs if p.text.strip()]

        with PdfPages(pdf_path) as pdf:
            page_lines = 45
            for i in range(0, len(lines), page_lines):
                fig, ax = plt.subplots(figsize=(8.5, 11))
                ax.axis("off")
                text = "\n".join(lines[i:i+page_lines])
                ax.text(0.05, 0.95, text, transform=ax.transAxes, fontsize=9,
                        verticalalignment="top", fontfamily="monospace", wrap=True)
                pdf.savefig(fig, bbox_inches="tight")
                plt.close(fig)

    def _word_to_html(self, docx_path, html_path):
        """Word → HTML"""
        import mammoth
        with open(docx_path, "rb") as f:
            result = mammoth.convert_to_html(f)
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>转换文档</title><style>body{{font-family:sans-serif;margin:40px;}}</style>
</head><body>{result.value}</body></html>"""
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

    def _word_to_markdown(self, docx_path, md_path):
        """Word → Markdown"""
        import mammoth
        with open(docx_path, "rb") as f:
            result = mammoth.convert_to_markdown(f)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(result.value)

    def _on_convert_done(self, msg):
        self.btn_convert.setEnabled(True)
        level = "INFO" if msg.startswith("✅") else "ERROR"
        self.main_window.log(msg, level)

    def _batch_convert(self):
        """批量转换：选择多个文件，统一转为目标格式"""
        paths, _ = QFileDialog.getOpenFileNames(self, "选择多个文件", "", FILE_FILTERS)
        if not paths:
            return

        fmt_key = self.combo_output_format.currentText()
        fmt = OUTPUT_FORMATS[fmt_key]
        ext = "." + fmt if fmt != "sqlite" else ".db"

        # 选择输出目录
        out_dir = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if not out_dir:
            return

        encoding = self.combo_input_encoding.currentText()
        options = {
            "encoding": self.combo_output_encoding.currentText(),
            "orient": self.combo_json_orient.currentText(),
            "table_name": self.input_table_name.text() or "data",
        }

        success = 0
        fail = 0
        for path in paths:
            try:
                df = self._read_file(path, encoding)
                base_name = os.path.splitext(os.path.basename(path))[0]
                out_path = os.path.join(out_dir, base_name + ext)

                # 同步转换（批量时不用线程，逐个处理）
                thread = ConvertThread(df, out_path, fmt, options)
                thread.run()  # 直接调用 run，不启动线程
                success += 1
            except Exception as e:
                self.main_window.log(f"❌ {os.path.basename(path)}: {e}", "ERROR")
                fail += 1

        self.main_window.log(
            f"批量转换完成: {success} 成功, {fail} 失败, 输出目录: {out_dir}", "INFO"
        )

    def _clear(self):
        """清空"""
        self._source_df = None
        self.table_model.update_data(pd.DataFrame())
        self.lbl_input_info.setText("未选择文件")
        self.main_window.log("转换器已清空", "INFO")
