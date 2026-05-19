"""插件系统"""
import os
import importlib
from app.plugins.base_plugin import BasePlugin


class PluginManager:
    """插件管理器 - 自动发现和加载插件"""

    def __init__(self, plugin_dir=None):
        if plugin_dir is None:
            plugin_dir = os.path.join(os.path.dirname(__file__), "extensions")
        self.plugin_dir = plugin_dir
        self.plugins: list[BasePlugin] = []

    def discover_plugins(self) -> list[BasePlugin]:
        """扫描插件目录，加载所有插件"""
        if not os.path.exists(self.plugin_dir):
            os.makedirs(self.plugin_dir, exist_ok=True)
            return []

        self.plugins = []
        for filename in os.listdir(self.plugin_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                module_name = filename[:-3]
                try:
                    spec = importlib.util.spec_from_file_location(
                        module_name,
                        os.path.join(self.plugin_dir, filename)
                    )
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # 查找继承 BasePlugin 的类
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type)
                                and issubclass(attr, BasePlugin)
                                and attr is not BasePlugin):
                            plugin_instance = attr()
                            self.plugins.append(plugin_instance)
                except Exception as e:
                    print(f"[插件加载失败] {filename}: {e}")

        return self.plugins
