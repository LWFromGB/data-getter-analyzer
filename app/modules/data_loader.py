"""数据加载模块 - 异步加载 + 底部进度条"""
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QTableView, QLabel, QComboBox, QGroupBox
)
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QThread, pyqtSignal


class PandasModel(QAbstractTableModel):
    """pandas DataFrame 表格模型（分页显示）"""

    PAGE_SIZE = 500

    def __init__(self, df=None):
        super().__init__()
        self._df = df if df is not None else pd.DataFrame()
        self._display_rows = min(self.PAGE_SIZE, len(self._df))

    def rowCount(self, parent=QModelIndex()):
        return self._display_rows

    def columnCount(self, parent=QModelIndex()):
        return len(self._df.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            value = self._df.iloc[index.row(), index.column()]
            return str(value)
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self._df.columns[section])
            return str(section + 1)
        return None

    def update_data(self, df):
        self.beginResetModel()
        self._df = df
        self._display_rows = min(self.PAGE_SIZE, len(self._df))
        self.endResetModel()

    def can_load_more(self):
        return self._display_rows < len(self._df)

    def load_more(self):
        if not self.can_load_more():
            return
        new_rows = min(self._display_rows + self.PAGE_SIZE, len(self._df))
        self.beginInsertRows(QModelIndex(), self._display_rows, new_rows - 1)
        self._display_rows = new_rows
        self.endInsertRows()


class FileLoaderThread(QThread):
    """异步文件加载线程"""
    finished = pyqtSignal(object)
    progress = pyqtSignal(int, str)  # (百分比, 描述)

    def __init__(self, file_path, encoding="utf-8"):
        super().__init__()
        self.file_path = file_path
        self.encoding = encoding

    def run(self):
        try:
            name = self.file_path.split("/")[-1].split("\\")[-1]
            self.progress.emit(5, f"正在打开 {name}...")

            if self.file_path.endswith(".csv"):
                self.progress.emit(10, "读取CSV文件...")
                chunks = []
                reader = pd.read_csv(
                    self.file_path,
                    encoding=self.encoding,
                    chunksize=10000
                )
                total_chunks = 0
                for chunk in reader:
                    chunks.append(chunk)
                    total_chunks += 1
                    pct = min(10 + total_chunks * 8, 85)
                    self.progress.emit(pct, f"已读取 {total_chunks * 10000} 行...")

                self.progress.emit(88, "合并数据...")
                df = pd.concat(chunks, ignore_index=True)
            else:
                self.progress.emit(20, "读取Excel文件...")
                df = pd.read_excel(self.file_path)

            self.progress.emit(95, "准备显示...")
            self.finished.emit(df)
        except Exception as e:
            self.finished.emit(f"加载失败: {str(e)}")


class DataLoaderWidget(QWidget):
    """数据加载界面"""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._loader_thread = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 操作区
        control_group = QGroupBox("文件操作")
        control_layout = QHBoxLayout(control_group)

        self.btn_open = QPushButton("📂 打开文件")
        self.btn_open.clicked.connect(self.open_file)
        control_layout.addWidget(self.btn_open)

        self.lbl_encoding = QLabel("编码:")
        control_layout.addWidget(self.lbl_encoding)

        self.combo_encoding = QComboBox()
        self.combo_encoding.addItems(["utf-8", "gbk", "gb2312", "latin-1", "utf-16"])
        control_layout.addWidget(self.combo_encoding)

        control_layout.addStretch()

        self.lbl_info = QLabel("未加载数据")
        control_layout.addWidget(self.lbl_info)

        self.btn_clear = QPushButton("🗑️ 清空")
        self.btn_clear.clicked.connect(self._clear)
        control_layout.addWidget(self.btn_clear)

        layout.addWidget(control_group)

        # 数据预览表格
        self.table_view = QTableView()
        self.table_model = PandasModel()
        self.table_view.setModel(self.table_model)
        layout.addWidget(self.table_view)

        # 加载更多按钮
        self.btn_load_more = QPushButton("加载更多行...")
        self.btn_load_more.clicked.connect(self._load_more_rows)
        self.btn_load_more.setVisible(False)
        layout.addWidget(self.btn_load_more)

    def open_file(self):
        """打开文件并异步加载"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择数据文件",
            "",
            "数据文件 (*.csv *.xlsx *.xls);;CSV (*.csv);;Excel (*.xlsx *.xls);;所有文件 (*)"
        )
        if not file_path:
            return

        encoding = self.combo_encoding.currentText()
        self.btn_open.setEnabled(False)
        self.lbl_info.setText("正在加载...")

        # 显示底部进度条
        self.main_window.show_file_progress(True)
        self.main_window.update_file_progress(0, "准备加载文件...")

        # 异步加载
        self._loader_thread = FileLoaderThread(file_path, encoding)
        self._loader_thread.progress.connect(self._on_progress)
        self._loader_thread.finished.connect(
            lambda result: self._on_loaded(result, file_path)
        )
        self._loader_thread.start()

    def _on_progress(self, value, text):
        """更新底部进度条"""
        self.main_window.update_file_progress(value, text)

    def _on_loaded(self, result, file_path):
        self.btn_open.setEnabled(True)

        if isinstance(result, pd.DataFrame):
            self.main_window.update_file_progress(98, "渲染表格...")
            self.table_model.update_data(result)
            self.main_window.set_data(result)
            name = file_path.split("/")[-1].split("\\")[-1]
            self.lbl_info.setText(f"已加载: {name} ({len(result)}行×{len(result.columns)}列)")
            self.btn_load_more.setVisible(self.table_model.can_load_more())
        else:
            self.lbl_info.setText(str(result))
            self.main_window.show_file_progress(False)
            self.main_window.status_label.setText(str(result))

    def _load_more_rows(self):
        self.table_model.load_more()
        self.btn_load_more.setVisible(self.table_model.can_load_more())

    def _clear(self):
        """清空数据"""
        self.table_model.update_data(pd.DataFrame())
        self.main_window.current_data = None
        self.lbl_info.setText("未加载数据")
        self.btn_load_more.setVisible(False)
        self.main_window.log("数据已清空", "INFO")
