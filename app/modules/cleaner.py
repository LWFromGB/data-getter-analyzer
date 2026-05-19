"""数据清洗模块"""
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableView, QLabel, QGroupBox, QCheckBox,
    QComboBox, QListWidget, QAbstractItemView, QMessageBox
)

from app.modules.data_loader import PandasModel


class CleanerWidget(QWidget):
    """数据清洗界面"""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 清洗操作区
        ops_group = QGroupBox("清洗操作")
        ops_layout = QVBoxLayout(ops_group)

        # 缺失值处理
        row1 = QHBoxLayout()
        self.btn_drop_na = QPushButton("删除缺失值行")
        self.btn_drop_na.clicked.connect(self._drop_na)
        row1.addWidget(self.btn_drop_na)

        self.btn_fill_na = QPushButton("填充缺失值")
        self.btn_fill_na.clicked.connect(self._fill_na)
        row1.addWidget(self.btn_fill_na)

        self.combo_fill_method = QComboBox()
        self.combo_fill_method.addItems(["0", "均值", "中位数", "前值填充", "后值填充"])
        row1.addWidget(self.combo_fill_method)
        ops_layout.addLayout(row1)

        # 去重和类型转换
        row2 = QHBoxLayout()
        self.btn_drop_dup = QPushButton("删除重复行")
        self.btn_drop_dup.clicked.connect(self._drop_duplicates)
        row2.addWidget(self.btn_drop_dup)

        self.btn_reset_index = QPushButton("重置索引")
        self.btn_reset_index.clicked.connect(self._reset_index)
        row2.addWidget(self.btn_reset_index)

        self.btn_drop_cols = QPushButton("删除选中列")
        self.btn_drop_cols.clicked.connect(self._drop_columns)
        row2.addWidget(self.btn_drop_cols)

        self.btn_clear = QPushButton("🗑️ 清空")
        self.btn_clear.clicked.connect(self._clear)
        row2.addWidget(self.btn_clear)

        ops_layout.addLayout(row2)

        layout.addWidget(ops_group)

        # 列选择
        col_group = QGroupBox("列选择（用于删除列操作）")
        col_layout = QHBoxLayout(col_group)
        self.col_list = QListWidget()
        self.col_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        col_layout.addWidget(self.col_list)

        self.btn_refresh_cols = QPushButton("刷新列列表")
        self.btn_refresh_cols.clicked.connect(self._refresh_columns)
        col_layout.addWidget(self.btn_refresh_cols)
        layout.addWidget(col_group)

        # 数据信息
        self.lbl_info = QLabel("请先加载数据")
        layout.addWidget(self.lbl_info)

        # 预览表格
        self.table_view = QTableView()
        self.table_model = PandasModel()
        self.table_view.setModel(self.table_model)
        layout.addWidget(self.table_view)

    def _get_data(self):
        """获取当前数据"""
        df = self.main_window.current_data
        if df is None:
            QMessageBox.warning(self, "提示", "请先加载数据")
            return None
        return df.copy()

    def _update_data(self, df):
        """更新数据并刷新显示"""
        self.main_window.set_data(df)
        self.table_model.update_data(df)
        na_count = df.isna().sum().sum()
        # duplicated() 可能因为列中有 list/dict 类型而失败
        try:
            dup_count = df.duplicated().sum()
        except TypeError:
            dup_count = "N/A"
        self.lbl_info.setText(f"行数: {len(df)} | 列数: {len(df.columns)} | 缺失值: {na_count} | 重复行: {dup_count}")

    def _refresh_columns(self):
        """刷新列列表"""
        self.col_list.clear()
        df = self.main_window.current_data
        if df is not None:
            self.col_list.addItems(df.columns.tolist())
            self._update_data(df)

    def _drop_na(self):
        df = self._get_data()
        if df is not None:
            df = df.dropna()
            self._update_data(df)

    def _fill_na(self):
        df = self._get_data()
        if df is None:
            return
        method = self.combo_fill_method.currentText()
        if method == "0":
            df = df.fillna(0)
        elif method == "均值":
            df = df.fillna(df.mean(numeric_only=True))
        elif method == "中位数":
            df = df.fillna(df.median(numeric_only=True))
        elif method == "前值填充":
            df = df.ffill()
        elif method == "后值填充":
            df = df.bfill()
        self._update_data(df)

    def _drop_duplicates(self):
        df = self._get_data()
        if df is not None:
            try:
                df = df.drop_duplicates()
            except TypeError:
                # 列中有 list/dict 等不可哈希类型，转为字符串后去重
                str_df = df.astype(str)
                mask = ~str_df.duplicated()
                df = df[mask].reset_index(drop=True)
            self._update_data(df)

    def _reset_index(self):
        df = self._get_data()
        if df is not None:
            df = df.reset_index(drop=True)
            self._update_data(df)

    def _drop_columns(self):
        df = self._get_data()
        if df is None:
            return
        selected = [item.text() for item in self.col_list.selectedItems()]
        if not selected:
            QMessageBox.warning(self, "提示", "请先选择要删除的列")
            return
        df = df.drop(columns=selected, errors="ignore")
        self._update_data(df)
        self._refresh_columns()

    def _clear(self):
        """清空清洗结果"""
        self.table_model.update_data(pd.DataFrame())
        self.col_list.clear()
        self.lbl_info.setText("请先加载数据")
        self.main_window.log("清洗模块已清空", "INFO")
