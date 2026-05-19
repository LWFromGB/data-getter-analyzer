"""插件基类 - 所有扩展插件需继承此类"""
from abc import ABC, abstractmethod


class BasePlugin(ABC):
    """
    插件基类

    开发新插件步骤：
    1. 在 app/plugins/extensions/ 目录下创建 .py 文件
    2. 创建一个类继承 BasePlugin
    3. 实现 name、description 属性和 get_widget 方法
    4. 重启应用即可自动加载
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """插件名称（显示在标签页上）"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """插件描述"""
        ...

    @abstractmethod
    def get_widget(self, main_window):
        """
        返回插件的 Qt Widget，将被添加为主窗口的标签页

        Args:
            main_window: 主窗口实例，可通过它访问 current_data 等共享数据

        Returns:
            QWidget 实例
        """
        ...

    def on_data_changed(self, df):
        """当主窗口数据更新时调用（可选重写）"""
        pass
