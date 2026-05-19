"""数据分析工具 - 入口文件（带启动进度条 + 日志）"""
import sys
import os

# 确保工作目录正确
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 初始化日志
from app.logger import setup_logger, setup_exception_hook
logger = setup_logger()
setup_exception_hook(logger)

logger.info("=" * 50)
logger.info("应用启动")


def main():
    from PyQt6.QtWidgets import QApplication, QSplashScreen
    from PyQt6.QtGui import QPixmap, QColor, QPainter, QFont
    from PyQt6.QtCore import Qt

    # WebEngine 必须在 QApplication 创建前导入或设置此属性
    from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401

    app = QApplication(sys.argv)
    app.setApplicationName("数据分析工具")
    app.setStyle("Fusion")

    # 创建启动画面
    pixmap = QPixmap(480, 260)
    pixmap.fill(QColor("#1a1a2e"))

    painter = QPainter(pixmap)
    painter.setPen(QColor("#e0e0e0"))
    font = QFont("Microsoft YaHei", 18, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect().adjusted(0, 40, 0, -80),
                     Qt.AlignmentFlag.AlignCenter, "📊 数据分析工具")
    font2 = QFont("Microsoft YaHei", 10)
    painter.setFont(font2)
    painter.setPen(QColor("#aaaaaa"))
    painter.drawText(pixmap.rect().adjusted(0, 90, 0, -60),
                     Qt.AlignmentFlag.AlignCenter, "v1.0 - 正在启动...")
    painter.end()

    splash = QSplashScreen(pixmap)
    splash.show()

    from PyQt6.QtWidgets import QProgressBar, QLabel

    # 进度条
    progress = QProgressBar(splash)
    progress.setGeometry(40, 220, 400, 20)
    progress.setStyleSheet("""
        QProgressBar {
            border: 1px solid #333;
            border-radius: 4px;
            background: #2a2a3e;
            text-align: center;
            color: #e0e0e0;
        }
        QProgressBar::chunk {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #4a90d9, stop:1 #67b8f7);
            border-radius: 3px;
        }
    """)
    progress.setMaximum(100)
    progress.setValue(0)
    progress.show()

    status_label = QLabel(splash)
    status_label.setGeometry(40, 195, 400, 20)
    status_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
    status_label.show()

    def update_splash(value, text):
        progress.setValue(value)
        status_label.setText(text)
        app.processEvents()

    try:
        update_splash(10, "加载核心框架...")
        logger.info("加载核心框架")

        update_splash(30, "加载数据处理引擎...")
        import pandas
        logger.info("pandas 加载完成")

        update_splash(50, "加载数值计算库...")
        import numpy
        logger.info("numpy 加载完成")

        update_splash(65, "初始化插件系统...")
        from app.plugins import PluginManager
        logger.info("插件系统加载完成")

        update_splash(75, "构建主窗口...")
        from app.main_window import MainWindow
        logger.info("主窗口模块加载完成")

        update_splash(85, "初始化界面...")
        window = MainWindow(splash_callback=update_splash)
        logger.info("主窗口初始化完成")

        update_splash(100, "启动完成")
        splash.finish(window)
        window.show()
        logger.info("应用窗口已显示")

    except Exception as e:
        logger.critical(f"启动失败: {e}", exc_info=True)
        splash.close()
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(None, "启动失败", f"应用启动失败:\n{e}")
        sys.exit(1)

    exit_code = app.exec()
    logger.info(f"应用退出，退出码: {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
