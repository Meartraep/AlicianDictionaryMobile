# 原作者：Meartraep
# 项目仓库：https://github.com/Meartraep/Alician_dictionary
# 协议：CC BY-NC 4.0 | 禁止商用，改编需保留署名
import os
import json

class ConfigManager:
    """配置管理器，负责加载和保存配置"""
    def __init__(self, config_file="word_checker_config.json"):
        self.config_file = config_file
        self.default_config = {
            "strict_case": True, 
            "max_undo_steps": 100, 
            "text_width": 500, 
            "sidebar_width": 260,
            "excluded_words": [],
            "dictionary_format_enabled": False,
            "dictionary_format_separators": [":", "："]
        }
        self.config = self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                
                # 合并默认配置和加载的配置，确保所有配置项都存在
                config = self.default_config.copy()
                config.update(loaded_config)
                return config
            except (json.JSONDecodeError, Exception) as e:
                print(f"加载配置失败: {e}，使用默认配置")
                return self.default_config.copy()
        else:
            return self.default_config.copy()
    
    def save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False
    
    def get(self, key, default=None):
        """获取配置值"""
        return self.config.get(key, default)
    
    def set(self, key, value):
        """设置配置值"""
        self.config[key] = value
    
    def update(self, new_config):
        """更新多个配置值"""
        self.config.update(new_config)
