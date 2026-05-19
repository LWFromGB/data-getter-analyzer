"""主窗口 - 带底部Terminal日志区"""
import logging
import pandas as pd
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QMessageBox, QProgressBar,
    QLabel, QWidget, QVBoxLayout, QSplitter, QTextEdit,
    QHBoxLayout, QPushButton
)
from PyQt6.QtGui import QAction, QTextCursor, QColor
from PyQt6.QtCore import Qt, QObject, pyqtSignal

from app.plugins import PluginManager


TUTORIAL_HTML = """
<h2>📊 数据分析工具 - 使用教程</h2>
<hr>

<h3>🔀 工具切换</h3>
<p>通过菜单栏 <b>工具(T)</b> 切换不同功能模块。</p>

<h3>📂 数据加载</h3>
<ol>
<li>点击「打开文件」选择 CSV 或 Excel 文件</li>
<li>选择正确的编码（中文文件通常用 utf-8 或 gbk）</li>
<li>数据加载后会显示在表格中，底部状态栏显示行列数</li>
</ol>

<h3>🕷️ 爬虫工具</h3>
<p><b>cURL 请求模式：</b></p>
<ol>
<li>在浏览器 F12 → Network → 右键请求 → Copy as cURL</li>
<li>粘贴到 cURL 输入框</li>
<li>点击「解析并发送」，数据自动展示为表格</li>
<li>点击「➕ 追加到数据池」保存结果</li>
</ol>
<p><b>连续爬取：</b>适合分页 API，设置次数、间隔、偏移字段后点「连续爬取」自动翻页采集。</p>
<p><b>CSS 网页爬取：</b>输入 URL 和 CSS 选择器，提取网页中的表格或文本。</p>

<h3>🧹 数据清洗</h3>
<ul>
<li><b>删除缺失值行</b> — 去掉含空值的行</li>
<li><b>填充缺失值</b> — 用 0、均值、中位数等填充</li>
<li><b>删除重复行</b> — 去重</li>
<li><b>删除选中列</b> — 先在列列表中选择，再点删除</li>
</ul>
<p>提示：先点「刷新列列表」加载当前数据的列。</p>

<h3>📊 数据分析</h3>
<ul>
<li><b>描述性统计</b> — 均值、标准差、最大最小值等</li>
<li><b>相关性分析</b> — 数值列之间的相关系数矩阵</li>
<li><b>数据概览</b> — 列类型、缺失值、唯一值统计</li>
<li><b>频率统计</b> — 选择一列查看值的出现次数</li>
</ul>

<h3>📈 可视化 Dashboard</h3>
<ol>
<li>先加载数据</li>
<li>点「刷新列」加载列名到 X/Y 轴选择器</li>
<li>选择图表类型和 X/Y 轴 → 点「生成图表」</li>
<li>或直接点「生成 Dashboard」自动生成综合仪表盘</li>
</ol>
<p>图表支持悬浮交互，可缩放、平移、导出图片。</p>

<h3>📄 报告导出</h3>
<p>勾选需要包含的内容（统计、相关性、原始数据），点击导出 HTML 报告。</p>

<h3>🔄 格式转换</h3>
<ol>
<li>先选择「输出格式」</li>
<li>再选择输入文件</li>
<li>表格格式（CSV/Excel）会解析为数据表预览</li>
<li>文档格式（Word/PDF/Markdown）保留原布局转换</li>
<li>点「转换并保存」完成</li>
</ol>
<p><b>PDF 引擎选择：</b></p>
<ul>
<li>PyMuPDF4LLM（快速）— 适合有边框线的表格</li>
<li>MinerU（AI 高精度）— 适合复杂排版，速度较慢</li>
</ul>

<h3>🔗 文件合并</h3>
<ol>
<li>点「添加文件」选择多个文件</li>
<li>选择合并方式（纵向/横向/关联）</li>
<li>点「执行合并」</li>
<li>预览结果后点「导出」保存</li>
</ol>
<p>支持表格文件合并（CSV/Excel）和文档合并（PDF/Word 保留原格式）。</p>

<h3>💡 通用操作</h3>
<ul>
<li><b>导出数据</b> — 菜单栏 文件 → 导出 → 选择格式</li>
<li><b>Terminal 日志</b> — 底部显示所有操作日志和错误信息</li>
<li><b>发送到主数据</b> — 将当前模块的数据共享给其他模块使用</li>
<li><b>清空</b> — 每个模块都有清空按钮重置状态</li>
</ul>

<h3>⌨️ 快捷提示</h3>
<ul>
<li>菜单栏 视图 → 显示/隐藏 Terminal</li>
<li>所有错误信息都记录在 logs/ 目录下</li>
<li>爬虫数据池的数据不会被「清空」按钮删除</li>
</ul>
"""


class LogSignalHandler(QObject, logging.Handler):
    """将 logging 日志转发到 Qt 信号（线程安全）"""
    log_signal = pyqtSignal(str, str)  # (级别, 消息)

    def __init__(self):
        QObject.__init__(self)
        logging.Handler.__init__(self)
        self.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))

    def emit(self, record):
        msg = self.format(record)
        self.log_signal.emit(record.levelname, msg)


class MainWindow(QMainWindow):
    """应用主窗口"""

    def __init__(self, splash_callback=None):
        super().__init__()
        self.setWindowTitle("数据分析工具 - 数据加载")
        self.setMinimumSize(1200, 800)

        self.current_data = None
        self.plugin_manager = PluginManager()
        self._splash_callback = splash_callback

        self._init_statusbar()
        self._init_ui()
        self._init_menu()
        self._setup_log_handler()
        self._load_plugins()

    def _init_statusbar(self):
        """初始化底部状态栏（含进度条）"""
        statusbar = self.statusBar()

        self.status_label = QLabel("就绪")
        statusbar.addWidget(self.status_label, 1)

        self.file_progress = QProgressBar()
        self.file_progress.setFixedWidth(300)
        self.file_progress.setFixedHeight(16)
        self.file_progress.setVisible(False)
        self.file_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555;
                border-radius: 3px;
                background: #2a2a3e;
                text-align: center;
                color: #e0e0e0;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a90d9, stop:1 #67b8f7);
                border-radius: 2px;
            }
        """)
        statusbar.addPermanentWidget(self.file_progress)

    def _init_ui(self):
        """初始化界面 - 菜单栏切换工具 + 下方Terminal日志区"""
        from app.modules.data_loader import DataLoaderWidget
        from app.modules.crawler import CrawlerWidget
        from app.modules.cleaner import CleanerWidget
        from app.modules.analyzer import AnalyzerWidget
        from app.modules.visualizer import VisualizerWidget
        from app.modules.exporter import ExporterWidget
        from app.modules.converter import ConverterWidget
        from app.modules.merger import MergerWidget
        from PyQt6.QtWidgets import QStackedWidget

        # 主布局
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 上下分割区域
        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)

        # 工具页面堆栈
        self.stack = QStackedWidget()
        splitter.addWidget(self.stack)

        if self._splash_callback:
            self._splash_callback(88, "创建数据加载模块...")
        self.data_loader = DataLoaderWidget(self)
        self.stack.addWidget(self.data_loader)

        if self._splash_callback:
            self._splash_callback(90, "创建爬虫模块...")
        self.crawler = CrawlerWidget(self)
        self.stack.addWidget(self.crawler)

        if self._splash_callback:
            self._splash_callback(92, "创建清洗模块...")
        self.cleaner = CleanerWidget(self)
        self.stack.addWidget(self.cleaner)

        if self._splash_callback:
            self._splash_callback(94, "创建分析模块...")
        self.analyzer = AnalyzerWidget(self)
        self.stack.addWidget(self.analyzer)

        if self._splash_callback:
            self._splash_callback(96, "创建可视化模块...")
        self.visualizer = VisualizerWidget(self)
        self.stack.addWidget(self.visualizer)

        if self._splash_callback:
            self._splash_callback(98, "创建导出模块...")
        self.exporter = ExporterWidget(self)
        self.stack.addWidget(self.exporter)

        if self._splash_callback:
            self._splash_callback(99, "创建转换器模块...")
        self.converter = ConverterWidget(self)
        self.stack.addWidget(self.converter)

        self.merger = MergerWidget(self)
        self.stack.addWidget(self.merger)

        # 下方：Terminal 日志区
        terminal_widget = QWidget()
        terminal_layout = QVBoxLayout(terminal_widget)
        terminal_layout.setContentsMargins(4, 2, 4, 2)
        terminal_layout.setSpacing(2)

        # Terminal 标题栏
        header = QHBoxLayout()
        header_label = QLabel("📋 Terminal")
        header_label.setStyleSheet("font-weight: bold; color: #ccc; font-size: 12px;")
        header.addWidget(header_label)
        header.addStretch()

        self.btn_clear_log = QPushButton("清空")
        self.btn_clear_log.setFixedSize(50, 20)
        self.btn_clear_log.setStyleSheet("font-size: 11px;")
        self.btn_clear_log.clicked.connect(self._clear_terminal)
        header.addWidget(self.btn_clear_log)

        terminal_layout.addLayout(header)

        # 日志文本区
        self.terminal_output = QTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e2e;
                color: #c0c0c0;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 12px;
                border: 1px solid #333;
                border-radius: 4px;
            }
        """)
        terminal_layout.addWidget(self.terminal_output)
        splitter.addWidget(terminal_widget)

        # 设置分割比例（上方占 75%，下方占 25%）
        splitter.setSizes([600, 200])

        self.log("应用启动完成", "INFO")

    def _setup_log_handler(self):
        """将 logging 系统接入 Terminal 显示"""
        self._log_handler = LogSignalHandler()
        self._log_handler.log_signal.connect(self._on_log_message)
        logging.getLogger("data_analyzer").addHandler(self._log_handler)

    def _on_log_message(self, level, message):
        """接收日志信号并显示到 Terminal"""
        self.log(message, level)

    def log(self, message, level="INFO"):
        """向 Terminal 区写入一条日志"""
        color_map = {
            "DEBUG": "#888888",
            "INFO": "#c0c0c0",
            "WARNING": "#f0ad4e",
            "ERROR": "#d9534f",
            "CRITICAL": "#ff4444",
        }
        color = color_map.get(level, "#c0c0c0")
        html = f'<span style="color:{color};">{message}</span>'
        self.terminal_output.append(html)
        # 自动滚动到底部
        self.terminal_output.moveCursor(QTextCursor.MoveOperation.End)

    def _clear_terminal(self):
        self.terminal_output.clear()
        self.log("Terminal 已清空", "INFO")

    def _init_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("文件(&F)")
        open_action = QAction("打开文件", self)
        open_action.triggered.connect(self._open_file)
        file_menu.addAction(open_action)

        # 导出子菜单
        export_menu = file_menu.addMenu("导出")

        export_csv = QAction("CSV (.csv)", self)
        export_csv.triggered.connect(lambda: self._export_data("csv"))
        export_menu.addAction(export_csv)

        export_excel = QAction("Excel (.xlsx)", self)
        export_excel.triggered.connect(lambda: self._export_data("xlsx"))
        export_menu.addAction(export_excel)

        export_json = QAction("JSON (.json)", self)
        export_json.triggered.connect(lambda: self._export_data("json"))
        export_menu.addAction(export_json)

        export_menu.addSeparator()

        export_pdf = QAction("PDF (.pdf)", self)
        export_pdf.triggered.connect(lambda: self._export_data("pdf"))
        export_menu.addAction(export_pdf)

        export_word = QAction("Word (.docx)", self)
        export_word.triggered.connect(lambda: self._export_data("docx"))
        export_menu.addAction(export_word)

        export_html = QAction("HTML (.html)", self)
        export_html.triggered.connect(lambda: self._export_data("html"))
        export_menu.addAction(export_html)

        export_menu.addSeparator()

        export_tsv = QAction("TSV (.tsv)", self)
        export_tsv.triggered.connect(lambda: self._export_data("tsv"))
        export_menu.addAction(export_tsv)

        export_parquet = QAction("Parquet (.parquet)", self)
        export_parquet.triggered.connect(lambda: self._export_data("parquet"))
        export_menu.addAction(export_parquet)

        export_md = QAction("Markdown (.md)", self)
        export_md.triggered.connect(lambda: self._export_data("md"))
        export_menu.addAction(export_md)

        export_xml = QAction("XML (.xml)", self)
        export_xml.triggered.connect(lambda: self._export_data("xml"))
        export_menu.addAction(export_xml)

        file_menu.addSeparator()

        exit_action = QAction("退出(&Q)", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 视图菜单
        view_menu = menubar.addMenu("视图(&V)")
        toggle_terminal = QAction("显示/隐藏 Terminal", self)
        toggle_terminal.triggered.connect(self._toggle_terminal)
        view_menu.addAction(toggle_terminal)

        tools_menu = menubar.addMenu("工具(&T)")
        self.plugin_menu = tools_menu

        tool_items = [
            ("📂 数据加载", 0),
            ("🕷️ 爬虫工具", 1),
            ("🧹 数据清洗", 2),
            ("📊 数据分析", 3),
            ("📈 可视化Dashboard", 4),
            ("📄 报告导出", 5),
            ("🔄 格式转换", 6),
            ("🔗 文件合并", 7),
        ]
        for name, idx in tool_items:
            action = QAction(name, self)
            action.triggered.connect(lambda checked, i=idx: self._on_tool_changed(i))
            tools_menu.addAction(action)

        help_menu = menubar.addMenu("帮助(&H)")

        tutorial_action = QAction("使用教程", self)
        tutorial_action.triggered.connect(self._show_tutorial)
        help_menu.addAction(tutorial_action)

        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _toggle_terminal(self):
        """切换 Terminal 显示/隐藏"""
        terminal = self.terminal_output.parent()
        terminal.setVisible(not terminal.isVisible())

    def _on_tool_changed(self, index):
        """菜单切换工具页面"""
        self.stack.setCurrentIndex(index)
        tool_names = [
            "数据加载", "爬虫工具", "数据清洗", "数据分析",
            "可视化Dashboard", "报告导出", "格式转换", "文件合并"
        ]
        if 0 <= index < len(tool_names):
            self.setWindowTitle(f"数据分析工具 - {tool_names[index]}")

    def _open_file(self):
        self.stack.setCurrentIndex(0)
        self.data_loader.open_file()

    def _export_data(self, fmt):
        """统一导出当前工作数据"""
        from PyQt6.QtWidgets import QFileDialog
        from app.utils.exporter import export_dataframe, EXT_FILTERS, get_file_size_str

        df = self.current_data
        if df is None or df.empty:
            self.log("没有可导出的数据，请先加载数据", "WARNING")
            return

        filter_str = EXT_FILTERS.get(fmt, "所有文件 (*)")
        path, _ = QFileDialog.getSaveFileName(self, "导出数据", "", filter_str)
        if not path:
            return

        try:
            export_dataframe(df, path, fmt)
            size_str = get_file_size_str(path)
            self.log(f"✅ 已导出 {fmt.upper()}: {path} ({len(df)} 行, {size_str})", "INFO")
        except Exception as e:
            self.log(f"❌ 导出失败: {e}", "ERROR")

    def _load_plugins(self):
        plugins = self.plugin_manager.discover_plugins()
        for plugin in plugins:
            if hasattr(plugin, "get_widget"):
                widget = plugin.get_widget(self)
                self.stack.addWidget(widget)

    # === 底部进度条控制接口 ===

    def show_file_progress(self, visible=True):
        self.file_progress.setVisible(visible)
        if visible:
            self.file_progress.setValue(0)

    def update_file_progress(self, value, text=None):
        self.file_progress.setValue(value)
        if text:
            self.status_label.setText(text)
            self.log(text, "INFO")

    def set_data(self, df):
        self.current_data = df
        row_count = len(df) if df is not None else 0
        col_count = len(df.columns) if df is not None else 0
        msg = f"数据已加载: {row_count} 行 × {col_count} 列"
        self.status_label.setText(msg)
        self.log(msg, "INFO")
        self.show_file_progress(False)

    def _show_about(self):
        QMessageBox.about(
            self,
            "关于",
            "数据分析工具 v1.0\n\n"
            "功能：数据加载、爬虫采集、数据清洗、\n"
            "统计分析、可视化Dashboard、报告导出\n\n"
            "基于 Python + PyQt6 构建"
        )

    def _show_tutorial(self):
        """显示使用教程"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox

        dialog = QDialog(self)
        dialog.setWindowTitle("使用教程")
        dialog.setMinimumSize(700, 500)
        layout = QVBoxLayout(dialog)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(TUTORIAL_HTML)
        layout.addWidget(browser)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)

        dialog.exec()
