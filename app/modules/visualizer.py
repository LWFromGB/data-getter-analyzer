"""可视化模块 - Dashboard (QtWebEngine + Plotly) - 延迟导入优化"""
import logging
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QComboBox, QLabel, QGroupBox
)
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger("data_analyzer.visualizer")

# plotly 延迟导入（启动时不加载）
px = None
go = None
make_subplots_fn = None


def _ensure_plotly():
    """首次使用时才导入 plotly"""
    global px, go, make_subplots_fn
    if px is None:
        logger.info("首次加载 plotly...")
        import plotly.express as _px
        import plotly.graph_objects as _go
        from plotly.subplots import make_subplots as _ms
        px = _px
        go = _go
        make_subplots_fn = _ms
        logger.info("plotly 加载完成")


class ChartRenderThread(QThread):
    """后台线程生成图表 HTML"""
    finished = pyqtSignal(str)

    def __init__(self, render_func, *args):
        super().__init__()
        self._render_func = render_func
        self._args = args

    def run(self):
        try:
            _ensure_plotly()
            logger.info(f"开始渲染图表: {self._render_func.__name__}")
            html = self._render_func(*self._args)
            logger.info("图表渲染完成")
            self.finished.emit(html)
        except Exception as e:
            self.finished.emit(
                f"<html><body style='color:white;background:#1a1a2e;'>"
                f"<h3>生成失败: {e}</h3></body></html>"
            )


class VisualizerWidget(QWidget):
    """可视化 Dashboard 界面"""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._web_view = None  # 延迟创建 WebEngine
        self._render_thread = None
        self._init_ui()

    def _init_ui(self):
        self._layout = QVBoxLayout(self)

        # 控制区
        ctrl_group = QGroupBox("图表配置")
        ctrl_layout = QVBoxLayout(ctrl_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("图表类型:"))
        self.combo_chart = QComboBox()
        self.combo_chart.addItems([
            "综合Dashboard", "柱状图", "折线图",
            "散点图", "饼图", "直方图", "箱线图", "热力图"
        ])
        row1.addWidget(self.combo_chart)

        row1.addWidget(QLabel("X轴:"))
        self.combo_x = QComboBox()
        row1.addWidget(self.combo_x)

        row1.addWidget(QLabel("Y轴:"))
        self.combo_y = QComboBox()
        row1.addWidget(self.combo_y)
        ctrl_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄 刷新列")
        self.btn_refresh.clicked.connect(self._refresh_columns)
        row2.addWidget(self.btn_refresh)

        self.btn_render = QPushButton("📈 生成图表")
        self.btn_render.clicked.connect(self._render_chart)
        row2.addWidget(self.btn_render)

        self.btn_dashboard = QPushButton("🖥️ 生成Dashboard")
        self.btn_dashboard.clicked.connect(self._render_dashboard)
        row2.addWidget(self.btn_dashboard)

        self.btn_clear = QPushButton("🗑️ 清空")
        self.btn_clear.clicked.connect(self._clear)
        row2.addWidget(self.btn_clear)

        row2.addStretch()
        ctrl_layout.addLayout(row2)
        self._layout.addWidget(ctrl_group)

        # 状态标签
        self.lbl_status = QLabel("")
        self._layout.addWidget(self.lbl_status)

    def _get_web_view(self):
        """延迟创建 WebEngineView（首次使用时才加载）"""
        if self._web_view is None:
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            self._web_view = QWebEngineView()
            self._web_view.setHtml(self._placeholder_html())
            self._layout.addWidget(self._web_view)
        return self._web_view

    def _placeholder_html(self):
        return """
        <html><body style="display:flex;align-items:center;justify-content:center;
        height:100vh;margin:0;background:#1a1a2e;color:#e0e0e0;font-family:sans-serif;">
        <div style="text-align:center;">
            <h2>📈 可视化 Dashboard</h2>
            <p>请加载数据后点击"生成图表"或"生成Dashboard"</p>
        </div>
        </body></html>
        """

    def _refresh_columns(self):
        self.combo_x.clear()
        self.combo_y.clear()
        df = self.main_window.current_data
        if df is not None:
            cols = df.columns.tolist()
            self.combo_x.addItems(cols)
            self.combo_y.addItems(cols)

    def _render_chart(self):
        """后台生成单个图表"""
        df = self.main_window.current_data
        if df is None:
            return

        chart_type = self.combo_chart.currentText()
        x_col = self.combo_x.currentText()
        y_col = self.combo_y.currentText()

        self.lbl_status.setText("正在生成图表...")
        self.btn_render.setEnabled(False)

        self._render_thread = ChartRenderThread(
            self._build_single_chart, df, chart_type, x_col, y_col
        )
        self._render_thread.finished.connect(self._on_render_done)
        self._render_thread.start()

    def _render_dashboard(self):
        """后台生成 Dashboard"""
        df = self.main_window.current_data
        if df is None:
            return

        self.lbl_status.setText("正在生成 Dashboard...")
        self.btn_dashboard.setEnabled(False)

        self._render_thread = ChartRenderThread(self._build_dashboard, df)
        self._render_thread.finished.connect(self._on_render_done)
        self._render_thread.start()

    def _on_render_done(self, html):
        """渲染完成回调"""
        self.btn_render.setEnabled(True)
        self.btn_dashboard.setEnabled(True)
        self.lbl_status.setText("")
        self._get_web_view().setHtml(html)

    @staticmethod
    def _build_single_chart(df, chart_type, x_col, y_col):
        """构建单个图表 HTML（在工作线程中执行）"""
        if chart_type == "柱状图":
            fig = px.bar(df, x=x_col, y=y_col, title=f"{y_col} by {x_col}")
        elif chart_type == "折线图":
            fig = px.line(df, x=x_col, y=y_col, title=f"{y_col} 趋势")
        elif chart_type == "散点图":
            fig = px.scatter(df, x=x_col, y=y_col, title=f"{x_col} vs {y_col}")
        elif chart_type == "饼图":
            fig = px.pie(df, names=x_col, values=y_col, title=f"{x_col} 分布")
        elif chart_type == "直方图":
            fig = px.histogram(df, x=x_col, title=f"{x_col} 分布")
        elif chart_type == "箱线图":
            fig = px.box(df, x=x_col, y=y_col, title=f"{y_col} 箱线图")
        elif chart_type == "热力图":
            numeric_df = df.select_dtypes(include=[np.number])
            corr = numeric_df.corr()
            fig = px.imshow(corr, text_auto=True, title="相关性热力图")
        else:
            fig = px.bar(df, x=x_col, y=y_col)

        fig.update_layout(font=dict(family="Microsoft YaHei, SimHei, sans-serif"))
        return fig.to_html(include_plotlyjs="cdn")

    @staticmethod
    def _build_dashboard(df):
        """构建综合 Dashboard HTML（在工作线程中执行）"""
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        all_cols = df.columns.tolist()
        cat_cols = df.select_dtypes(include=["object"]).columns.tolist()

        # === 指标卡片（带迷你图和趋势箭头） ===
        cards_html = ""
        for i, col in enumerate(numeric_cols[:4]):
            total = df[col].sum()
            mean = df[col].mean()
            last_val = df[col].iloc[-1] if len(df) > 0 else 0
            first_val = df[col].iloc[0] if len(df) > 0 else 0

            # 格式化数字
            if abs(total) >= 1_000_000:
                total_str = f"{total/1_000_000:.2f}M"
            elif abs(total) >= 1_000:
                total_str = f"{total/1_000:.1f}K"
            else:
                total_str = f"{total:.2f}"

            # 趋势计算
            if first_val != 0:
                change_pct = ((last_val - first_val) / abs(first_val)) * 100
            else:
                change_pct = 0

            if change_pct > 0:
                arrow = "↑"
                arrow_color = "#27ae60"
                trend_text = f"+{change_pct:.1f}%"
            elif change_pct < 0:
                arrow = "↓"
                arrow_color = "#e74c3c"
                trend_text = f"{change_pct:.1f}%"
            else:
                arrow = "→"
                arrow_color = "#95a5a6"
                trend_text = "0%"

            # 迷你折线图（SVG sparkline）
            values = df[col].dropna().tail(20).tolist()
            if len(values) > 1:
                min_v, max_v = min(values), max(values)
                range_v = max_v - min_v if max_v != min_v else 1
                points = []
                for j, v in enumerate(values):
                    x = j * (100 / (len(values) - 1))
                    y = 30 - ((v - min_v) / range_v) * 28
                    points.append(f"{x:.1f},{y:.1f}")
                sparkline_path = " ".join(points)
                sparkline_color = "#27ae60" if change_pct >= 0 else "#e74c3c"
                sparkline = f'<svg width="100" height="32" style="margin-top:4px;"><polyline points="{sparkline_path}" fill="none" stroke="{sparkline_color}" stroke-width="2" stroke-linecap="round"/></svg>'
            else:
                sparkline = ""

            colors = ["#4a90d9", "#27ae60", "#f39c12", "#9b59b6"]
            border_color = colors[i % 4]

            cards_html += f"""
            <div class="card" style="border-left-color:{border_color};">
                <div class="card-header">
                    <span class="card-title">{col}</span>
                    <span class="card-trend" style="color:{arrow_color};">{arrow} {trend_text}</span>
                </div>
                <div class="card-value">{total_str}</div>
                <div class="card-footer">
                    <span>均值: {mean:.2f}</span>
                    {sparkline}
                </div>
            </div>"""

        # === 图表 ===
        # 图1: 面积折线图（多系列）
        fig_line = go.Figure()
        for i, col in enumerate(numeric_cols[:3]):
            fig_line.add_trace(go.Scatter(
                y=df[col], mode="lines",
                name=col, fill="tozeroy",
                line=dict(width=2),
                hovertemplate=f"{col}: %{{y:.2f}}<extra></extra>"
            ))
        fig_line.update_layout(
            title=dict(text="📈 数据趋势", font=dict(size=14)),
            height=250, margin=dict(l=40, r=20, t=45, b=30),
            template="plotly_white",
            font=dict(family="Microsoft YaHei, SimHei, sans-serif", size=11),
            legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
            hovermode="x unified"
        )
        line_html = fig_line.to_html(include_plotlyjs=False, full_html=False)

        # 图2: 横向柱状图（渐变色）
        bar_html = ""
        if numeric_cols and len(all_cols) >= 2:
            sample = df.nlargest(10, numeric_cols[0]) if len(df) > 10 else df
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(
                y=sample[all_cols[0]].astype(str),
                x=sample[numeric_cols[0]],
                orientation="h",
                marker=dict(
                    color=sample[numeric_cols[0]],
                    colorscale="Blues",
                    line=dict(width=0)
                ),
                hovertemplate="%{y}: %{x:.2f}<extra></extra>"
            ))
            fig_bar.update_layout(
                title=dict(text=f"🏆 Top {col} 排名", font=dict(size=13)),
                height=250, margin=dict(l=100, r=20, t=40, b=30),
                template="plotly_white",
                font=dict(family="Microsoft YaHei, SimHei, sans-serif", size=11)
            )
            bar_html = fig_bar.to_html(include_plotlyjs=False, full_html=False)

        # 图3: 环形饼图
        pie_html = ""
        if cat_cols:
            vc = df[cat_cols[0]].value_counts().head(6)
            colors_pie = ["#4a90d9", "#27ae60", "#f39c12", "#e74c3c", "#9b59b6", "#1abc9c"]
            fig_pie = go.Figure(data=[go.Pie(
                labels=vc.index.tolist(),
                values=vc.values.tolist(),
                hole=0.5,
                marker=dict(colors=colors_pie[:len(vc)]),
                textinfo="percent+label",
                hovertemplate="%{label}: %{value} (%{percent})<extra></extra>"
            )])
            fig_pie.update_layout(
                title=dict(text=f"🎯 {cat_cols[0]} 占比", font=dict(size=13)),
                height=250, margin=dict(l=20, r=20, t=40, b=20),
                font=dict(family="Microsoft YaHei, SimHei, sans-serif", size=11),
                showlegend=False
            )
            pie_html = fig_pie.to_html(include_plotlyjs=False, full_html=False)

        # 图4: 直方图 + 密度线
        hist_html = ""
        if numeric_cols:
            fig_hist = go.Figure()
            fig_hist.add_trace(go.Histogram(
                x=df[numeric_cols[0]],
                marker=dict(color="#5bb5e0", line=dict(color="#3498db", width=1)),
                opacity=0.8,
                hovertemplate="区间: %{x}<br>数量: %{y}<extra></extra>"
            ))
            fig_hist.update_layout(
                title=dict(text=f"📊 {numeric_cols[0]} 分布", font=dict(size=13)),
                height=250, margin=dict(l=40, r=20, t=40, b=30),
                template="plotly_white",
                font=dict(family="Microsoft YaHei, SimHei, sans-serif", size=11),
                bargap=0.05
            )
            hist_html = fig_hist.to_html(include_plotlyjs=False, full_html=False)

        # 图5: 散点图（如果有多个数值列）
        scatter_html = ""
        if len(numeric_cols) >= 2:
            fig_scatter = go.Figure()
            fig_scatter.add_trace(go.Scatter(
                x=df[numeric_cols[0]], y=df[numeric_cols[1]],
                mode="markers",
                marker=dict(
                    size=8, color=df[numeric_cols[0]],
                    colorscale="Viridis", opacity=0.7,
                    line=dict(width=1, color="white")
                ),
                hovertemplate=f"{numeric_cols[0]}: %{{x:.2f}}<br>{numeric_cols[1]}: %{{y:.2f}}<extra></extra>"
            ))
            fig_scatter.update_layout(
                title=dict(text=f"🔍 {numeric_cols[0]} vs {numeric_cols[1]}", font=dict(size=13)),
                height=250, margin=dict(l=40, r=20, t=40, b=30),
                template="plotly_white",
                font=dict(family="Microsoft YaHei, SimHei, sans-serif", size=11)
            )
            scatter_html = fig_scatter.to_html(include_plotlyjs=False, full_html=False)

        # 图6: 箱线图
        box_html = ""
        if numeric_cols:
            fig_box = go.Figure()
            for col in numeric_cols[:4]:
                fig_box.add_trace(go.Box(y=df[col], name=col, boxmean=True))
            fig_box.update_layout(
                title=dict(text="📦 数值分布对比", font=dict(size=13)),
                height=250, margin=dict(l=40, r=20, t=40, b=30),
                template="plotly_white",
                font=dict(family="Microsoft YaHei, SimHei, sans-serif", size=11),
                showlegend=False
            )
            box_html = fig_box.to_html(include_plotlyjs=False, full_html=False)

        # === 组装 HTML ===
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif; background: #f0f4f8; padding: 16px; }}
.header {{ text-align: center; margin-bottom: 16px; }}
.header h1 {{ color: #2c3e50; font-size: 20px; font-weight: 600; }}
.header p {{ color: #7f8c8d; font-size: 12px; margin-top: 4px; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 16px; }}
.card {{
    background: white; border-radius: 10px; padding: 14px 16px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    border-left: 4px solid #4a90d9;
    transition: transform 0.2s, box-shadow 0.2s;
}}
.card:hover {{ transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,0.1); }}
.card-header {{ display: flex; justify-content: space-between; align-items: center; }}
.card-title {{ font-size: 11px; color: #7f8c8d; text-transform: uppercase; letter-spacing: 0.5px; }}
.card-trend {{ font-size: 12px; font-weight: 600; }}
.card-value {{ font-size: 26px; font-weight: 700; color: #2c3e50; margin: 4px 0; }}
.card-footer {{ display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: #95a5a6; }}
.grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }}
.grid-3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-bottom: 12px; }}
.chart-box {{
    background: white; border-radius: 10px; padding: 10px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    transition: box-shadow 0.2s;
}}
.chart-box:hover {{ box-shadow: 0 4px 16px rgba(0,0,0,0.1); }}
.chart-full {{ grid-column: 1 / -1; }}
@media (max-width: 900px) {{
    .grid-3 {{ grid-template-columns: 1fr; }}
    .grid-2 {{ grid-template-columns: 1fr; }}
}}
</style></head><body>
<div class="header">
    <h1>📊 数据分析 Dashboard</h1>
    <p>{len(df)} 行 × {len(df.columns)} 列 | 数值列: {len(numeric_cols)} | 分类列: {len(cat_cols)}</p>
</div>
<div class="cards">{cards_html}</div>
<div class="grid-2">
    <div class="chart-box chart-full">{line_html}</div>
</div>
<div class="grid-3">
    <div class="chart-box">{bar_html}</div>
    <div class="chart-box">{pie_html}</div>
    <div class="chart-box">{hist_html}</div>
</div>
<div class="grid-2">
    <div class="chart-box">{scatter_html}</div>
    <div class="chart-box">{box_html}</div>
</div>
</body></html>"""

        return html

        return fig.to_html(include_plotlyjs="cdn")

    def _clear(self):
        """清空可视化"""
        self.combo_x.clear()
        self.combo_y.clear()
        self.lbl_status.setText("")
        if self._web_view is not None:
            self._web_view.setHtml(self._placeholder_html())
        self.main_window.log("可视化模块已清空", "INFO")
