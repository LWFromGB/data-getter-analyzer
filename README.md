# 数据分析工具

基于 Python + PyQt6 的桌面数据分析应用。

## 功能

- 📂 **数据加载** - 支持 CSV/Excel 文件导入
- 🕷️ **爬虫工具** - 网页数据采集
- 🧹 **数据清洗** - 缺失值处理、去重、列管理
- 📊 **数据分析** - 描述性统计、相关性分析、频率统计
- 📈 **可视化Dashboard** - Plotly 交互式图表，QtWebEngine 渲染
- 📄 **报告导出** - HTML/CSV/Excel 格式（可选）
- 🔌 **插件系统** - 支持扩展新功能

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行

```bash
python main.py
```

## 打包为 .exe

```bash
pyinstaller build.spec
```

生成的 .exe 文件在 `dist/` 目录下。

## 开发插件

在 `app/plugins/extensions/` 目录下创建 .py 文件，继承 `BasePlugin` 即可：

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
