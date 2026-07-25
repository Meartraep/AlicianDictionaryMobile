# 原作者：Meartraep
# 项目仓库：https://github.com/Meartraep/Alician_dictionary
# 协议：CC BY-NC 4.0 | 禁止商用，改编需保留署名
import sqlite3
import logging
import os
import sys

def _get_default_db_path():
    env_db = os.environ.get("ALICIAN_DB_PATH")
    if env_db:
        return os.path.abspath(env_db)
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'translated.db')
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../translated.db"))

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DatabaseManager:
    """数据库连接管理器 - 单例模式"""
    _instance = None
    _connection = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance
    
    def get_connection(self):
        """获取数据库连接，如果连接不存在则创建新连接"""
        if self._connection is None:
            try:
                # 使用绝对路径，确保从任何目录运行都能找到数据库文件
                db_path = _get_default_db_path()
                self._connection = sqlite3.connect(db_path)
                # 启用外键约束
                self._connection.execute("PRAGMA foreign_keys = ON")
            except sqlite3.Error as e:
                logger.error(f"创建数据库连接时出错: {e}")
                raise
        return self._connection
    
    def close_connection(self):
        """关闭数据库连接"""
        if self._connection is not None:
            try:
                self._connection.close()
                self._connection = None
            except sqlite3.Error as e:
                logger.error(f"关闭数据库连接时出错: {e}")
