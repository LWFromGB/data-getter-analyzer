"""数据分析模块 - 统计分析"""
import pandas as pd
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableView, QLabel, QGroupBox, QComboBox,
    QTextEdit, QSplitter
)
from PyQt6.QtCore import Qt

from app.modules.data_loader import PandasModel


class AnalyzerWidget(QWidget):
    """统计分析界面"""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 操作区
        ops_group = QGroupBox("分析操作")
        ops_layout = QHBoxLayout(ops_group)

        self.btn_describe = QPushButton("📊 描述性统计")
        self.btn_describe.clicked.connect(self._describe)
        ops_layout.addWidget(self.btn_describe)

        self.btn_corr = QPushButton("🔗 相关性分析")
        self.btn_corr.clicked.connect(self._correlation)
        ops_layout.addWidget(self.btn_corr)

        self.btn_info = QPushButton("ℹ️ 数据概览")
        self.btn_info.clicked.connect(self._data_info)
        ops_layout.addWidget(self.btn_info)

        self.btn_value_counts = QPushButton("📋 频率统计")
        self.btn_value_counts.clicked.connect(self._value_counts)
        ops_layout.addWidget(self.btn_value_counts)

        self.btn_clear = QPushButton("🗑️ 清空")
        self.btn_clear.clicked.connect(self._clear)
        ops_layout.addWidget(self.btn_clear)

        ops_layout.addStretch()
        layout.addWidget(ops_group)

        # 列选择
        col_layout = QHBoxLayout()
        col_layout.addWidget(QLabel("选择列:"))
        self.combo_column = QComboBox()
        self.combo_column.setMinimumWidth(200)
        col_layout.addWidget(self.combo_column)

        self.btn_refresh = QPushButton("刷新列")
        self.btn_refresh.clicked.connect(self._refresh_columns)
        col_layout.addWidget(self.btn_refresh)
        col_layout.addStretch()
        layout.addLayout(col_layout)

        # 结果展示区（上下分割）
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 表格结果
        self.table_view = QTableView()
        self.table_model = PandasModel()
        self.table_view.setModel(self.table_model)
        splitter.addWidget(self.table_view)

        # 文本结果
        self.text_output = QTextEdit()
        self.text_output.setReadOnly(True)
        splitter.addWidget(self.text_output)

        layout.addWidget(splitter)

    def _refresh_columns(self):
        """刷新列下拉框"""
        self.combo_column.clear()
        df = self.main_window.current_data
        if df is not None:
            self.combo_column.addItems(["(全部)"] + df.columns.tolist())

    def _describe(self):
        """描述性统计"""
        df = self.main_window.current_data
        if df is None:
            self.text_output.setText("请先加载数据")
            return

        col = self.combo_column.currentText()
        if col and col != "(全部)":
            desc = df[[col]].describe()
        else:
            desc = df.describe()

        self.table_model.update_data(desc.reset_index())
        self.text_output.setText(f"描述性统计:\n{desc.to_string()}")

    def _correlation(self):
        """相关性分析"""
        df = self.main_window.current_data
        if df is None:
            self.text_output.setText("请先加载数据")
            return

        numeric_df = df.select_dtypes(include=[np.number])
        if numeric_df.empty:
            self.text_output.setText("没有数值型列，无法计算相关性")
            return

        corr = numeric_df.corr()
        self.table_model.update_data(corr.reset_index())
        self.text_output.setText(f"相关性矩阵:\n{corr.to_string()}")

    def _data_info(self):
        """数据概览"""
        df = self.main_window.current_data
        if df is None:
            self.text_output.setText("请先加载数据")
            return

        info_lines = [
            f"数据形状: {df.shape[0]} 行 × {df.shape[1]} 列",
            f"\n列信息:",
        ]
        for col in df.columns:
            dtype = df[col].dtype
            na_count = df[col].isna().sum()
            unique = df[col].nunique()
            info_lines.append(f"  {col}: 类型={dtype}, 缺失={na_count}, 唯一值={unique}")

        info_lines.append(f"\n内存占用: {df.memory_usage(deep=True).sum() / 1024:.1f} KB")
        self.text_output.setText("\n".join(info_lines))

    def _value_counts(self):
        """频率统计"""
        df = self.main_window.current_data
        if df is None:
            self.text_output.setText("请先加载数据")
            return

        col = self.combo_column.currentText()
        if not col or col == "(全部)":
            self.text_output.setText("请选择一个具体的列进行频率统计")
            return

        vc = df[col].value_counts().reset_index()
        vc.columns = [col, "计数"]
        self.table_model.update_data(vc)
        self.text_output.setText(f"列 '{col}' 的频率统计:\n{vc.to_string(index=False)}")

    def _clear(self):
        """清空分析结果"""
        self.table_model.update_data(pd.DataFrame())
        self.text_output.clear()
        self.combo_column.clear()
        self.main_window.log("分析模块已清空", "INFO")
