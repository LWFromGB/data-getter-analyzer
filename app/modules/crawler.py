"""爬虫模块 - cURL 一键解析发送"""
import json
import logging
import re
import requests
from bs4 import BeautifulSoup
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QTextEdit, QTableView, QLabel,
    QGroupBox, QComboBox, QTabWidget, QPlainTextEdit,
    QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt

from app.modules.data_loader import PandasModel

logger = logging.getLogger("data_analyzer.crawler")


def parse_curl(curl_text):
    """
    解析 cURL 命令（支持 Linux/Mac/Windows CMD 格式）
    返回 dict: {url, method, headers, params, body}
    """
    # 1. 清理 Windows CMD 转义符 ^
    text = curl_text.replace("^\n", "").replace("^\r\n", "")
    # 去掉行首行尾空白
    text = " ".join(text.splitlines())
    # 去掉所有 ^ 转义（CMD格式）
    text = text.replace("^\"", "\"").replace("^&", "&").replace("^%", "%")
    text = text.replace("^", "")

    # 2. 去掉 Linux 续行符
    text = text.replace("\\\n", " ").replace("\\\r\n", " ")

    result = {"method": "GET", "url": "", "headers": {}, "params": {}, "body": None}

    # 3. 提取 URL（第一个 http 开头的字符串）
    url_match = re.search(r'(https?://[^\s"\']+)', text)
    if url_match:
        full_url = url_match.group(1)
        # 分离查询参数
        if "?" in full_url:
            base_url, query = full_url.split("?", 1)
            result["url"] = base_url
            for pair in query.split("&"):
                if "=" in pair:
                    k, _, v = pair.partition("=")
                    result["params"][k] = v
        else:
            result["url"] = full_url

    # 4. 提取 Headers (-H "Key: Value")
    header_pattern = re.findall(r'-H\s+"([^"]+)"', text)
    for h in header_pattern:
        if ":" in h:
            key, _, value = h.partition(":")
            result["headers"][key.strip()] = value.strip()

    # 5. 提取 Cookie (-b "...")
    cookie_match = re.search(r'-b\s+"([^"]+)"', text)
    if cookie_match:
        result["headers"]["Cookie"] = cookie_match.group(1)

    # 6. 提取 Body (--data-raw / --data / -d)
    body_match = re.search(r'(?:--data-raw|--data|--data-binary|-d)\s+"(.+?)"(?:\s|$)', text)
    if body_match:
        body_str = body_match.group(1)
        # 去掉转义的引号
        body_str = body_str.replace('\\"', '"')
        result["body"] = body_str
        if result["method"] == "GET":
            result["method"] = "POST"

    # 7. 提取方法 (-X POST)
    method_match = re.search(r'-X\s+(GET|POST|PUT|DELETE|PATCH)', text, re.IGNORECASE)
    if method_match:
        result["method"] = method_match.group(1).upper()
    elif result["body"]:
        result["method"] = "POST"

    return result


class CrawlerThread(QThread):
    """爬虫工作线程"""
    finished = pyqtSignal(object)
    progress = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config

    def run(self):
        try:
            url = self.config["url"]
            method = self.config.get("method", "GET")
            headers = self.config.get("headers", {})
            params = self.config.get("params", {})
            body_str = self.config.get("body", None)

            self.progress.emit(f"[{method}] {url}")
            logger.info(f"请求: [{method}] {url}")
            if params:
                logger.info(f"Params: {params}")

            # 构建请求
            kwargs = {"headers": headers, "params": params, "timeout": 30}

            if body_str:
                try:
                    kwargs["json"] = json.loads(body_str)
                except json.JSONDecodeError:
                    kwargs["data"] = body_str

            resp = requests.request(method, url, **kwargs)
            resp.raise_for_status()

            self.progress.emit(f"响应: {resp.status_code} | {len(resp.content)} bytes")
            logger.info(f"响应: {resp.status_code}, {len(resp.content)} bytes")

            # 解析响应
            content_type = resp.headers.get("content-type", "")
            mode = self.config.get("mode", "api")

            if mode == "css":
                self._parse_css(resp)
            elif "json" in content_type or resp.text.strip().startswith(("{", "[")):
                self._parse_json(resp)
            else:
                self._parse_html(resp)

        except requests.exceptions.Timeout:
            self.finished.emit("❌ 请求超时（30秒）")
        except requests.exceptions.ConnectionError as e:
            self.finished.emit(f"❌ 连接失败: {e}")
        except requests.exceptions.HTTPError as e:
            self.finished.emit(f"❌ HTTP错误 {resp.status_code}: {resp.text[:500]}")
        except Exception as e:
            logger.error(f"请求失败: {e}", exc_info=True)
            self.finished.emit(f"❌ 请求失败: {str(e)}")

    def _parse_json(self, resp):
        """解析 JSON 响应"""
        try:
            data = resp.json()
            self.progress.emit("解析 JSON...")

            df = self._json_to_dataframe(data)
            if df is not None and not df.empty:
                df = self._convert_timestamps(df)
                self.finished.emit(df)
            else:
                raw = json.dumps(data, ensure_ascii=False, indent=2)
                self.finished.emit(f"JSON_RAW:{raw}")
        except Exception as e:
            self.finished.emit(f"❌ JSON解析失败: {e}")

    def _convert_timestamps(self, df):
        """自动检测并转换时间戳列为可读日期"""
        import numpy as np
        for col in df.columns:
            # 跳过非数值列
            if not pd.api.types.is_numeric_dtype(df[col]):
                continue

            # 列名包含时间相关关键词
            col_lower = col.lower()
            time_keywords = ["time", "date", "created", "updated", "timestamp",
                             "modified", "expired", "start", "end", "at"]
            is_time_col = any(kw in col_lower for kw in time_keywords)

            if not is_time_col:
                # 检查数值范围是否像时间戳
                sample = df[col].dropna()
                if sample.empty:
                    continue
                val = sample.iloc[0]
                # 毫秒级时间戳范围（2000-2030年）
                if 946684800000 <= val <= 1893456000000:
                    is_time_col = True
                # 秒级时间戳范围
                elif 946684800 <= val <= 1893456000:
                    is_time_col = True

            if is_time_col:
                try:
                    sample_val = df[col].dropna().iloc[0]
                    if sample_val > 9999999999:
                        # 毫秒级
                        df[col] = pd.to_datetime(df[col], unit="ms", errors="coerce", utc=True)
                    else:
                        # 秒级
                        df[col] = pd.to_datetime(df[col], unit="s", errors="coerce", utc=True)
                    # 转为本地时区
                    df[col] = df[col].dt.tz_convert("Asia/Shanghai").dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass

        return df

    def _json_to_dataframe(self, data):
        """智能 JSON → DataFrame"""
        # 直接是列表
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return pd.json_normalize(data)

        if isinstance(data, dict):
            # 常见包裹字段
            for key in ["data", "results", "items", "records", "list",
                        "rows", "content", "entries", "transactions",
                        "trades", "orders", "hits"]:
                if key in data:
                    val = data[key]
                    if isinstance(val, list) and val and isinstance(val[0], dict):
                        return pd.json_normalize(val)

            # 递归查找第一个列表
            for key, val in data.items():
                if isinstance(val, list) and val and isinstance(val[0], dict):
                    return pd.json_normalize(val)
                elif isinstance(val, dict):
                    # 一层嵌套
                    for k2, v2 in val.items():
                        if isinstance(v2, list) and v2 and isinstance(v2[0], dict):
                            return pd.json_normalize(v2)

            # 单对象
            flat = {k: v for k, v in data.items() if not isinstance(v, (dict, list))}
            if flat:
                return pd.DataFrame([flat])

        return None

    def _parse_html(self, resp):
        """解析 HTML"""
        soup = BeautifulSoup(resp.text, "lxml")
        tables = soup.find_all("table")
        if tables:
            dfs = pd.read_html(str(tables[0]))
            if dfs:
                self.finished.emit(dfs[0])
                return
        self.finished.emit(f"JSON_RAW:{resp.text[:5000]}")

    def _parse_css(self, resp):
        """用 CSS 选择器提取数据"""
        soup = BeautifulSoup(resp.text, "lxml")
        selector = self.config.get("selector", "")
        extract_mode = self.config.get("extract_mode", "自动（表格优先）")
        attr_name = self.config.get("attr_name", "")

        self.progress.emit("解析页面...")

        # 如果没有选择器，自动模式
        if not selector:
            # 尝试找表格
            tables = soup.find_all("table")
            if tables:
                dfs = pd.read_html(str(tables[0]))
                if dfs:
                    self.finished.emit(dfs[0])
                    return
            self.finished.emit("未指定 CSS 选择器，且页面中未找到表格")
            return

        elements = soup.select(selector)
        if not elements:
            self.finished.emit(f"CSS 选择器 '{selector}' 未匹配到任何元素")
            return

        self.progress.emit(f"匹配到 {len(elements)} 个元素")

        if extract_mode == "自动（表格优先）":
            # 如果选中的是表格，用 pandas 解析
            if elements[0].name == "table":
                dfs = pd.read_html(str(elements[0]))
                if dfs:
                    self.finished.emit(dfs[0])
                    return

            # 如果选中的元素有子结构（如 li、tr），尝试提取结构化数据
            rows = []
            for el in elements:
                # 提取子元素文本
                children = el.find_all(recursive=False)
                if children:
                    row = {f"col_{i}": child.get_text(strip=True) for i, child in enumerate(children)}
                else:
                    row = {"内容": el.get_text(strip=True)}
                # 同时提取常用属性
                if el.get("href"):
                    row["href"] = el.get("href")
                if el.get("src"):
                    row["src"] = el.get("src")
                rows.append(row)

            if rows:
                self.finished.emit(pd.DataFrame(rows))
            else:
                self.finished.emit("匹配到元素但无法提取数据")

        elif extract_mode == "文本内容":
            data = [{"内容": el.get_text(strip=True)} for el in elements if el.get_text(strip=True)]
            if data:
                self.finished.emit(pd.DataFrame(data))
            else:
                self.finished.emit("匹配到元素但文本内容为空")

        elif extract_mode == "属性值":
            if not attr_name:
                attr_name = "href"
            data = []
            for el in elements:
                val = el.get(attr_name, "")
                text = el.get_text(strip=True)
                if val or text:
                    data.append({"文本": text, attr_name: val})
            if data:
                self.finished.emit(pd.DataFrame(data))
            else:
                self.finished.emit(f"匹配到元素但未找到属性 '{attr_name}'")

        elif extract_mode == "HTML源码":
            data = [{"HTML": str(el)} for el in elements]
            self.finished.emit(pd.DataFrame(data))


class CrawlerWidget(QWidget):
    """爬虫工具 - 粘贴 cURL → 一键发送 → 展示数据"""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.crawler_thread = None
        self._crawled_data = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 切换标签：cURL / CSS
        self.mode_tabs = QTabWidget()
        layout.addWidget(self.mode_tabs)

        # === cURL 爬取 ===
        curl_widget = QWidget()
        curl_group = QGroupBox("粘贴 cURL 命令（从浏览器 F12 → Network → Copy as cURL）")
        curl_layout = QVBoxLayout(curl_group)
        curl_widget_layout = QVBoxLayout(curl_widget)
        curl_widget_layout.setContentsMargins(0, 0, 0, 0)

        self.input_curl = QPlainTextEdit()
        self.input_curl.setPlaceholderText(
            "直接粘贴完整的 cURL 命令，支持 Windows CMD / Linux / Mac 格式\n\n"
            "示例:\n"
            'curl "https://api.example.com/data" -H "Authorization: Bearer xxx" --data-raw "{}"'
        )
        self.input_curl.setStyleSheet("""
            QPlainTextEdit {
                font-family: Consolas, 'Courier New', monospace;
                font-size: 12px;
                background: #1e1e2e;
                color: #c0c0c0;
                border: 1px solid #444;
                border-radius: 4px;
            }
        """)
        curl_layout.addWidget(self.input_curl)

        # 按钮行
        btn_layout = QHBoxLayout()

        self.btn_send = QPushButton("🚀 解析并发送")
        self.btn_send.setStyleSheet("font-size: 13px; padding: 6px 16px;")
        self.btn_send.clicked.connect(self._send_curl)
        btn_layout.addWidget(self.btn_send)

        self.btn_parse_only = QPushButton("🔍 仅解析（预览）")
        self.btn_parse_only.clicked.connect(self._parse_only)
        btn_layout.addWidget(self.btn_parse_only)

        self.btn_use_data = QPushButton("📥 使用此数据")
        self.btn_use_data.clicked.connect(self._use_data)
        self.btn_use_data.setEnabled(False)
        btn_layout.addWidget(self.btn_use_data)

        self.btn_clear = QPushButton("🗑️ 清空")
        self.btn_clear.clicked.connect(self._clear)
        btn_layout.addWidget(self.btn_clear)

        btn_layout.addStretch()
        curl_layout.addLayout(btn_layout)

        # 连续爬取设置
        batch_layout = QHBoxLayout()

        batch_layout.addWidget(QLabel("连续爬取:"))

        batch_layout.addWidget(QLabel("次数"))
        self.spin_batch_count = QSpinBox()
        self.spin_batch_count.setRange(2, 100)
        self.spin_batch_count.setValue(5)
        self.spin_batch_count.setFixedWidth(60)
        batch_layout.addWidget(self.spin_batch_count)

        batch_layout.addWidget(QLabel("间隔(秒)"))
        self.spin_batch_interval = QDoubleSpinBox()
        self.spin_batch_interval.setRange(0.5, 60.0)
        self.spin_batch_interval.setValue(1.0)
        self.spin_batch_interval.setSingleStep(0.5)
        self.spin_batch_interval.setFixedWidth(70)
        batch_layout.addWidget(self.spin_batch_interval)

        batch_layout.addWidget(QLabel("偏移字段"))
        self.input_offset_field = QLineEdit()
        self.input_offset_field.setPlaceholderText("start")
        self.input_offset_field.setFixedWidth(80)
        self.input_offset_field.setToolTip("Body中的分页字段名，每次自动递增limit值")
        batch_layout.addWidget(self.input_offset_field)

        batch_layout.addWidget(QLabel("每页条数"))
        self.spin_page_size = QSpinBox()
        self.spin_page_size.setRange(1, 1000)
        self.spin_page_size.setValue(20)
        self.spin_page_size.setFixedWidth(60)
        batch_layout.addWidget(self.spin_page_size)

        self.btn_batch_crawl = QPushButton("🔄 连续爬取")
        self.btn_batch_crawl.clicked.connect(self._start_batch_crawl)
        batch_layout.addWidget(self.btn_batch_crawl)

        self.btn_stop_batch = QPushButton("⏹️ 停止")
        self.btn_stop_batch.clicked.connect(self._stop_batch)
        self.btn_stop_batch.setEnabled(False)
        batch_layout.addWidget(self.btn_stop_batch)

        batch_layout.addStretch()
        curl_layout.addLayout(batch_layout)

        curl_widget_layout.addWidget(curl_group)
        self.mode_tabs.addTab(curl_widget, "🔌 cURL 请求")

        # === CSS 网页爬取 ===
        css_widget = QWidget()
        css_widget_layout = QVBoxLayout(css_widget)
        css_widget_layout.setContentsMargins(0, 0, 0, 0)
        css_group = QGroupBox("网页爬取（CSS 选择器）")
        css_layout = QVBoxLayout(css_group)

        row_url = QHBoxLayout()
        row_url.addWidget(QLabel("URL:"))
        self.input_web_url = QLineEdit()
        self.input_web_url.setPlaceholderText("输入网页地址，例如: https://example.com/page")
        row_url.addWidget(self.input_web_url)
        css_layout.addLayout(row_url)

        row_css = QHBoxLayout()
        row_css.addWidget(QLabel("CSS选择器:"))
        self.input_css_selector = QLineEdit()
        self.input_css_selector.setPlaceholderText("例如: table.data 或 div.list > ul > li 或 #content p")
        row_css.addWidget(self.input_css_selector)

        self.btn_css_crawl = QPushButton("🕷️ 爬取网页")
        self.btn_css_crawl.clicked.connect(self._send_css_crawl)
        row_css.addWidget(self.btn_css_crawl)

        self.btn_css_clear = QPushButton("🗑️ 清空")
        self.btn_css_clear.clicked.connect(self._clear_css)
        row_css.addWidget(self.btn_css_clear)
        css_layout.addLayout(row_css)

        # 提取模式
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("提取模式:"))
        self.combo_extract_mode = QComboBox()
        self.combo_extract_mode.addItems(["自动（表格优先）", "文本内容", "属性值", "HTML源码"])
        mode_layout.addWidget(self.combo_extract_mode)

        mode_layout.addWidget(QLabel("属性名:"))
        self.input_attr_name = QLineEdit()
        self.input_attr_name.setPlaceholderText("href / src / data-id")
        self.input_attr_name.setFixedWidth(120)
        mode_layout.addWidget(self.input_attr_name)

        mode_layout.addStretch()
        css_layout.addLayout(mode_layout)

        css_widget_layout.addWidget(css_group)
        self.mode_tabs.addTab(css_widget, "🕷️ CSS 网页爬取")

        # 结果区（标签页：表格 / 原始响应 / 解析详情）
        self.result_tabs = QTabWidget()

        self.table_view = QTableView()
        self.table_model = PandasModel()
        self.table_view.setModel(self.table_model)
        self.result_tabs.addTab(self.table_view, "📊 数据表格")

        self.raw_output = QTextEdit()
        self.raw_output.setReadOnly(True)
        self.raw_output.setStyleSheet("font-family: Consolas, monospace; font-size: 12px;")
        self.result_tabs.addTab(self.raw_output, "📝 原始响应")

        self.parse_output = QTextEdit()
        self.parse_output.setReadOnly(True)
        self.parse_output.setStyleSheet("font-family: Consolas, monospace; font-size: 12px;")
        self.result_tabs.addTab(self.parse_output, "🔍 解析详情")

        # === 临时数据池 ===
        pool_widget = QWidget()
        pool_layout = QVBoxLayout(pool_widget)

        pool_btn_layout = QHBoxLayout()

        self.btn_add_to_pool = QPushButton("➕ 追加当前结果到数据池")
        self.btn_add_to_pool.clicked.connect(self._add_to_pool)
        pool_btn_layout.addWidget(self.btn_add_to_pool)

        self.btn_export_pool_csv = QPushButton("📊 导出 CSV")
        self.btn_export_pool_csv.clicked.connect(self._export_pool_csv)
        pool_btn_layout.addWidget(self.btn_export_pool_csv)

        self.btn_export_pool_excel = QPushButton("📗 导出 Excel")
        self.btn_export_pool_excel.clicked.connect(self._export_pool_excel)
        pool_btn_layout.addWidget(self.btn_export_pool_excel)

        self.btn_pool_to_main = QPushButton("📥 发送到主数据")
        self.btn_pool_to_main.clicked.connect(self._pool_to_main)
        pool_btn_layout.addWidget(self.btn_pool_to_main)

        self.btn_clear_pool = QPushButton("🗑️ 清空数据池")
        self.btn_clear_pool.clicked.connect(self._clear_pool)
        pool_btn_layout.addWidget(self.btn_clear_pool)

        pool_btn_layout.addStretch()
        pool_layout.addLayout(pool_btn_layout)

        self.pool_info_label = QLabel("数据池: 0 行 × 0 列（共 0 次追加）")
        pool_layout.addWidget(self.pool_info_label)

        self.pool_table_view = QTableView()
        self.pool_table_model = PandasModel()
        self.pool_table_view.setModel(self.pool_table_model)
        pool_layout.addWidget(self.pool_table_view)

        self.result_tabs.addTab(pool_widget, "🗃️ 数据池")

        layout.addWidget(self.result_tabs)

        # 数据池存储
        self._pool_data = pd.DataFrame()
        self._pool_count = 0

    def _get_curl_text(self):
        text = self.input_curl.toPlainText().strip()
        if not text:
            self.main_window.log("请先粘贴 cURL 命令", "WARNING")
            return None
        return text

    def _parse_only(self):
        """仅解析 cURL，显示解析结果"""
        text = self._get_curl_text()
        if not text:
            return

        try:
            parsed = parse_curl(text)
            info_lines = [
                f"Method:  {parsed['method']}",
                f"URL:     {parsed['url']}",
                f"",
                f"Params ({len(parsed['params'])}):",
            ]
            for k, v in parsed["params"].items():
                info_lines.append(f"  {k} = {v}")

            info_lines.append(f"")
            info_lines.append(f"Headers ({len(parsed['headers'])}):")
            for k, v in parsed["headers"].items():
                # Cookie 太长，截断显示
                display_v = v[:80] + "..." if len(v) > 80 else v
                info_lines.append(f"  {k}: {display_v}")

            if parsed["body"]:
                info_lines.append(f"")
                info_lines.append(f"Body:")
                try:
                    body_obj = json.loads(parsed["body"])
                    info_lines.append(f"  {json.dumps(body_obj, ensure_ascii=False, indent=2)}")
                except Exception:
                    info_lines.append(f"  {parsed['body'][:500]}")

            self.parse_output.setText("\n".join(info_lines))
            self.result_tabs.setCurrentIndex(2)
            self.main_window.log("✅ cURL 解析完成，查看「解析详情」标签", "INFO")
        except Exception as e:
            self.main_window.log(f"解析失败: {e}", "ERROR")

    def _send_curl(self):
        """解析 cURL 并发送请求"""
        text = self._get_curl_text()
        if not text:
            return

        try:
            parsed = parse_curl(text)
            self.main_window.log(f"解析完成: [{parsed['method']}] {parsed['url']}", "INFO")

            self.btn_send.setEnabled(False)
            self.crawler_thread = CrawlerThread(parsed)
            self.crawler_thread.progress.connect(self._on_progress)
            self.crawler_thread.finished.connect(self._on_finished)
            self.crawler_thread.start()
        except Exception as e:
            self.main_window.log(f"cURL 解析失败: {e}", "ERROR")

    def _on_progress(self, msg):
        self.main_window.log(msg, "INFO")

    def _send_css_crawl(self):
        """CSS 选择器爬取网页"""
        url = self.input_web_url.text().strip()
        if not url:
            self.main_window.log("请输入网页 URL", "WARNING")
            return

        selector = self.input_css_selector.text().strip()
        mode = self.combo_extract_mode.currentText()
        attr_name = self.input_attr_name.text().strip()

        config = {
            "url": url,
            "method": "GET",
            "headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"},
            "params": {},
            "body": None,
            "mode": "css",
            "selector": selector,
            "extract_mode": mode,
            "attr_name": attr_name,
        }

        self.btn_css_crawl.setEnabled(False)
        self.main_window.log(f"爬取网页: {url} | 选择器: {selector or '(自动)'}", "INFO")

        self.crawler_thread = CrawlerThread(config)
        self.crawler_thread.progress.connect(self._on_progress)
        self.crawler_thread.finished.connect(self._on_css_finished)
        self.crawler_thread.start()

    def _on_css_finished(self, result):
        """CSS 爬取完成"""
        self.btn_css_crawl.setEnabled(True)
        self._on_finished(result)

    def _clear_css(self):
        """清空 CSS 爬取输入"""
        self.input_web_url.clear()
        self.input_css_selector.clear()
        self.input_attr_name.clear()
        self.main_window.log("CSS 爬取已清空", "INFO")

    def _on_finished(self, result):
        self.btn_send.setEnabled(True)

        if isinstance(result, pd.DataFrame):
            self._crawled_data = result
            self.table_model.update_data(result)
            self.btn_use_data.setEnabled(True)
            self.result_tabs.setCurrentIndex(0)
            self.raw_output.setText(result.to_string())
            self.main_window.log(
                f"✅ 数据获取成功: {len(result)} 行 × {len(result.columns)} 列", "INFO"
            )
        elif isinstance(result, str) and result.startswith("JSON_RAW:"):
            raw = result[9:]
            self.raw_output.setText(raw)
            self.result_tabs.setCurrentIndex(1)
            self.main_window.log("⚠️ 返回数据无法自动转为表格，已显示原始响应", "WARNING")
        else:
            self.raw_output.setText(str(result))
            self.result_tabs.setCurrentIndex(1)
            self.main_window.log(str(result), "ERROR")

    def _use_data(self):
        if self._crawled_data is not None:
            self.main_window.set_data(self._crawled_data)
            self.main_window.log("✅ 数据已设置为当前工作数据", "INFO")

    # === 连续爬取 ===

    def _start_batch_crawl(self):
        """开始连续爬取"""
        text = self._get_curl_text()
        if not text:
            return

        try:
            self._batch_parsed = parse_curl(text)
        except Exception as e:
            self.main_window.log(f"cURL 解析失败: {e}", "ERROR")
            return

        self._batch_count = self.spin_batch_count.value()
        self._batch_interval = self.spin_batch_interval.value()
        self._batch_offset_field = self.input_offset_field.text().strip() or "start"
        self._batch_page_size = self.spin_page_size.value()
        self._batch_current = 0
        self._batch_running = True

        self.btn_batch_crawl.setEnabled(False)
        self.btn_stop_batch.setEnabled(True)
        self.btn_send.setEnabled(False)

        self.main_window.log(
            f"开始连续爬取: {self._batch_count} 次, 间隔 {self._batch_interval}s, "
            f"偏移字段={self._batch_offset_field}, 每页={self._batch_page_size}",
            "INFO"
        )

        self._run_next_batch()

    def _run_next_batch(self):
        """执行下一次爬取"""
        if not self._batch_running or self._batch_current >= self._batch_count:
            self._finish_batch()
            return

        # 修改 body 中的偏移字段
        import copy
        config = copy.deepcopy(self._batch_parsed)
        offset_value = self._batch_current * self._batch_page_size

        if config.get("body"):
            try:
                body_obj = json.loads(config["body"])
                body_obj[self._batch_offset_field] = offset_value
                config["body"] = json.dumps(body_obj)
            except (json.JSONDecodeError, TypeError):
                pass
        else:
            # GET 请求，修改 params
            config["params"][self._batch_offset_field] = str(offset_value)

        self.main_window.log(
            f"[{self._batch_current + 1}/{self._batch_count}] "
            f"{self._batch_offset_field}={offset_value}",
            "INFO"
        )

        self.crawler_thread = CrawlerThread(config)
        self.crawler_thread.progress.connect(self._on_progress)
        self.crawler_thread.finished.connect(self._on_batch_finished)
        self.crawler_thread.start()

    def _on_batch_finished(self, result):
        """单次爬取完成"""
        if isinstance(result, pd.DataFrame) and not result.empty:
            self._crawled_data = result
            self.table_model.update_data(result)
            self.btn_use_data.setEnabled(True)

            # 自动追加到数据池
            if self._pool_data.empty:
                self._pool_data = result.copy()
            else:
                self._pool_data = pd.concat([self._pool_data, result], ignore_index=True)
            self._pool_count += 1
            self._update_pool_display()

            self.main_window.log(
                f"  ✅ 第 {self._batch_current + 1} 次: {len(result)} 行 "
                f"(数据池累计 {len(self._pool_data)} 行)",
                "INFO"
            )
        elif isinstance(result, str) and result.startswith("JSON_RAW:"):
            self.main_window.log(f"  ⚠️ 第 {self._batch_current + 1} 次: 无表格数据", "WARNING")
        else:
            self.main_window.log(f"  ❌ 第 {self._batch_current + 1} 次: {result}", "ERROR")

        self._batch_current += 1

        if self._batch_running and self._batch_current < self._batch_count:
            # 延迟后执行下一次
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(int(self._batch_interval * 1000), self._run_next_batch)
        else:
            self._finish_batch()

    def _finish_batch(self):
        """连续爬取结束"""
        self._batch_running = False
        self.btn_batch_crawl.setEnabled(True)
        self.btn_stop_batch.setEnabled(False)
        self.btn_send.setEnabled(True)
        self.result_tabs.setCurrentIndex(3)  # 切到数据池
        self.main_window.log(
            f"连续爬取完成: 共 {self._batch_current} 次, 数据池 {len(self._pool_data)} 行",
            "INFO"
        )

    def _stop_batch(self):
        """停止连续爬取"""
        self._batch_running = False
        self.main_window.log("连续爬取已手动停止", "WARNING")

    def _clear(self):
        self.input_curl.clear()
        self.table_model.update_data(pd.DataFrame())
        self.raw_output.clear()
        self.parse_output.clear()
        self._crawled_data = None
        self.btn_use_data.setEnabled(False)
        self.main_window.log("爬虫模块已清空（数据池保留）", "INFO")

    # === 数据池功能 ===

    def _add_to_pool(self):
        """将当前爬取结果追加到数据池"""
        if self._crawled_data is None or self._crawled_data.empty:
            self.main_window.log("没有可追加的数据，请先发送请求", "WARNING")
            return

        if self._pool_data.empty:
            self._pool_data = self._crawled_data.copy()
        else:
            self._pool_data = pd.concat(
                [self._pool_data, self._crawled_data],
                ignore_index=True
            )

        self._pool_count += 1
        self._update_pool_display()
        self.main_window.log(
            f"✅ 已追加 {len(self._crawled_data)} 行到数据池"
            f"（第 {self._pool_count} 次，累计 {len(self._pool_data)} 行）",
            "INFO"
        )
        # 自动切换到数据池标签
        self.result_tabs.setCurrentIndex(3)

    def _update_pool_display(self):
        """刷新数据池显示"""
        rows = len(self._pool_data)
        cols = len(self._pool_data.columns) if rows > 0 else 0
        self.pool_info_label.setText(
            f"数据池: {rows} 行 × {cols} 列（共 {self._pool_count} 次追加）"
        )
        self.pool_table_model.update_data(self._pool_data)

    def _export_pool_csv(self):
        """导出数据池为 CSV"""
        if self._pool_data.empty:
            self.main_window.log("数据池为空，无法导出", "WARNING")
            return

        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "导出数据池为 CSV", "", "CSV文件 (*.csv)")
        if path:
            self._pool_data.to_csv(path, index=False, encoding="utf-8-sig")
            self.main_window.log(f"✅ 数据池已导出: {path}（{len(self._pool_data)} 行）", "INFO")

    def _export_pool_excel(self):
        """导出数据池为 Excel"""
        if self._pool_data.empty:
            self.main_window.log("数据池为空，无法导出", "WARNING")
            return

        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "导出数据池为 Excel", "", "Excel文件 (*.xlsx)")
        if path:
            self._pool_data.to_excel(path, index=False)
            self.main_window.log(f"✅ 数据池已导出: {path}（{len(self._pool_data)} 行）", "INFO")

    def _pool_to_main(self):
        """将数据池数据发送到主数据"""
        if self._pool_data.empty:
            self.main_window.log("数据池为空", "WARNING")
            return
        self.main_window.set_data(self._pool_data.copy())
        self.main_window.log(f"✅ 数据池 {len(self._pool_data)} 行已设置为当前工作数据", "INFO")

    def _clear_pool(self):
        """清空数据池"""
        self._pool_data = pd.DataFrame()
        self._pool_count = 0
        self._update_pool_display()
        self.main_window.log("数据池已清空", "INFO")
