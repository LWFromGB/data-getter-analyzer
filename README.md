# 📊 数据分析工具 (Data Getter & Analyzer)

一款面向产品、结算、运营人员的桌面端智能数据工具，集数据采集、清洗、分析、可视化、格式转换、文件合并于一体。

## 功能概览

| 模块 | 功能 |
|------|------|
| 📂 数据加载 | CSV/Excel 导入，异步加载，分页显示 |
| 🕷️ 爬虫工具 | cURL 一键解析、连续翻页采集、CSS 网页爬取、数据池 |
| 🧹 数据清洗 | 缺失值处理、去重、列管理 |
| 📊 数据分析 | 描述统计、相关性分析、频率统计 |
| 📈 可视化 Dashboard | 交互式图表、指标卡片、趋势分析 |
| 📄 报告导出 | HTML 报告生成 |
| 🔄 格式转换 | 13 种格式互转，PDF 双引擎（PyMuPDF4LLM + MinerU） |
| 🔗 文件合并 | 表格合并 + 文档合并 + PDF 页面合并 |

## 技术栈

- **UI 框架**: PyQt6 + QtWebEngine
- **数据处理**: pandas + numpy
- **可视化**: Plotly（交互式图表）
- **爬虫**: requests + BeautifulSoup
- **PDF 解析**: PyMuPDF4LLM（快速）/ MinerU（AI 高精度）
- **打包**: PyInstaller

## 安装与运行

### 环境要求

- Python 3.10+
- Windows / macOS / Linux

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行

```bash
python main.py
```

### 打包为可执行文件

```bash
pyinstaller build.spec --noconfirm
```

输出目录: `dist/数据分析工具/`

## 核心特性

### 🕷️ 智能爬虫

- 粘贴浏览器复制的 cURL 命令，自动解析并发送请求
- 支持 Windows CMD / Linux / Mac 三种 cURL 格式
- 连续爬取：自动翻页采集分页 API（设置次数、间隔、偏移字段）
- CSS 选择器爬取：提取网页表格、文本、属性值
- 数据池：多次采集结果自动累积
- 时间戳智能转换：自动识别毫秒/秒级时间戳转为可读日期

### 📈 交互式 Dashboard

- 指标卡片：趋势箭头 + SVG 迷你折线图
- 6 种图表：面积图、柱状图、环形饼图、直方图、散点图、箱线图
- 悬浮交互、缩放、数据联动
- 白色商务风格，响应式布局

### 🔄 格式转换

支持 13 种格式互转：

| 输入 | 输出 |
|------|------|
| CSV, Excel, JSON, TSV, Parquet | ✅ |
| HTML, SQLite, Feather, Markdown | ✅ |
| PDF（双引擎）, Word | ✅ |
| LaTeX, XML | 仅输出 |

PDF 引擎选择：
- **PyMuPDF4LLM**（快速）— 适合有边框线的表格
- **MinerU**（AI 高精度）— 适合复杂排版，需要 PyTorch

### 🔗 文件合并

- 表格文件：纵向拼接 / 横向拼接 / 关联 JOIN
- 文档文件：PDF 页面级合并（保留原始排版）
- 合并预览：PDF 渲染为图片缩略图

## 项目结构

```
data_analyzer/
├── main.py                  # 入口
├── requirements.txt         # 依赖
├── build.spec               # PyInstaller 打包配置
├── app/
│   ├── main_window.py       # 主窗口
│   ├── logger.py            # 日志系统
│   ├── modules/
│   │   ├── data_loader.py   # 数据加载
│   │   ├── crawler.py       # 爬虫工具
│   │   ├── cleaner.py       # 数据清洗
│   │   ├── analyzer.py      # 数据分析
│   │   ├── visualizer.py    # 可视化 Dashboard
│   │   ├── exporter.py      # 报告导出
│   │   ├── converter.py     # 格式转换
│   │   └── merger.py        # 文件合并
│   ├── plugins/             # 插件系统
│   │   ├── base_plugin.py   # 插件基类
│   │   └── extensions/      # 自定义插件目录
│   └── utils/               # 公共工具
│       ├── file_reader.py   # 统一文件读取
│       ├── exporter.py      # 统一导出
│       └── pdf_parser.py    # PDF 解析引擎
└── docs/                    # 文档
```

## 插件开发

在 `app/plugins/extensions/` 目录下创建 `.py` 文件，继承 `BasePlugin` 即可自动加载：

```python
from app.plugins.base_plugin import BasePlugin
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout

class MyPlugin(BasePlugin):
    @property
    def name(self):
        return "我的插件"

    @property
    def description(self):
        return "插件描述"

    def get_widget(self, main_window):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Hello Plugin!"))
        return w
```

## 许可证

MIT License
