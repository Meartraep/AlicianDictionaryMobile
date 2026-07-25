# 原作者：Meartraep
# 项目仓库：https://github.com/Meartraep/Alician_dictionary
# 协议：CC BY-NC 4.0 | 禁止商用，改编需保留署名
import sqlite3
import os
import sys
import logging
from collections import defaultdict

def _get_db_path():
    env_db = os.environ.get("ALICIAN_DB_PATH")
    if env_db:
        return os.path.abspath(env_db)
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'translated.db')
    return os.path.join(os.path.dirname(__file__), 'translated.db')

# 添加当前目录到sys.path，确保能正确导入模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 配置日志
def setup_logger():
    env_db = os.environ.get("ALICIAN_DB_PATH")
    if env_db:
        log_dir = os.path.dirname(os.path.abspath(env_db))
    elif getattr(sys, 'frozen', False):
        log_dir = os.path.dirname(sys.executable)
    else:
        log_dir = os.path.dirname(__file__)
    log_file = os.path.join(log_dir, 'db_update.log')
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        encoding='utf-8'
    )
    return logging.getLogger()

def count_word_occurrences(lyric_lower, word_lower):
    """高效统计单词出现次数（基于字符串查找，比正则更快）"""
    count = 0
    start = 0
    word_len = len(word_lower)
    lyric_len = len(lyric_lower)
    while start <= lyric_len - word_len:
        # 查找单词位置
        pos = lyric_lower.find(word_lower, start)
        if pos == -1:
            break
        # 检查单词边界（避免部分匹配，如 "apple" 匹配 "applepie"）
        left_ok = pos == 0 or not lyric_lower[pos-1].isalnum()
        right_ok = (pos + word_len) == lyric_len or not lyric_lower[pos + word_len].isalnum()
        if left_ok and right_ok:
            count += 1
        # 跳过当前匹配位置，避免重叠匹配
        start = pos + 1
    return count

def main(verbose=False):
    # 初始化日志
    logger = setup_logger()
    logger.info("开始执行单词词频更新")
    
    # 数据库文件路径
    db_path = _get_db_path()
    
    # 检查数据库文件是否存在
    if not os.path.exists(db_path):
        error_msg = f"错误：数据库文件 '{db_path}' 不存在！"
        print(error_msg)
        logger.error(error_msg)
        return
    
    conn = None
    try:
        # 连接数据库并优化参数（针对低配电脑，减少磁盘IO）
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # 关闭磁盘同步（牺牲部分安全性，换取写入速度）
        cursor.execute("PRAGMA synchronous = OFF")
        # 日志模式改为内存（减少磁盘操作）
        cursor.execute("PRAGMA journal_mode = MEMORY")
        # 限制缓存大小（避免占用过多内存，单位：页，1页=4KB）
        cursor.execute("PRAGMA cache_size = -5000")  # 缓存20MB（可根据内存调整）
        
        print("成功连接到数据库")
        logger.info("成功连接到数据库")
        
        # 检查必要表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dictionary'")
        if not cursor.fetchone():
            error_msg = "错误：dictionary表不存在！"
            print(error_msg)
            logger.error(error_msg)
            return
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='raw'")
        if not cursor.fetchone():
            error_msg = "错误：raw表不存在！"
            print(error_msg)
            logger.error(error_msg)
            return
        
        # 词头表保存每个单词唯一的词频；dictionary 是一行一个释义。
        stats_table = "dictionary_headwords" if cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='dictionary_headwords'"
        ).fetchone() else "dictionary"
        cursor.execute(f"PRAGMA table_info({stats_table})")
        dict_columns = [col[1] for col in cursor.fetchall()]
        required_cols = ['words', 'count']
        for col in required_cols:
            if col not in dict_columns:
                error_msg = f"错误：dictionary表中没有'{col}'字段！"
                print(error_msg)
                logger.error(error_msg)
                return
        
        # 新增/检查variety字段（INTEGER类型，更高效）
        if 'variety' not in dict_columns:
            try:
                cursor.execute(f"ALTER TABLE {stats_table} ADD COLUMN variety INTEGER DEFAULT 0")
                msg = "提示：已自动添加 variety 字段（INTEGER类型）"
                print(msg)
                logger.info(msg)
            except sqlite3.Error as e:
                error_msg = f"添加variety字段失败: {e}"
                print(error_msg)
                logger.error(error_msg)
                return
        
        # 1. 加载所有有效单词（过滤空值，建立ID映射）
        cursor.execute("""
            SELECT id, words, count, variety FROM dictionary_headwords
            WHERE words IS NOT NULL AND words != ''
        """)
        words = cursor.fetchall()
        if not words:
            msg = "dictionary表中没有有效单词数据"
            print(msg)
            logger.info(msg)
            return
        
        # 构建单词映射：word_id → (原始单词, 小写单词, 当前count, 当前variety)
        word_map = {}
        for word_id, word, current_count, current_variety in words:
            word_map[word_id] = (word, word.lower(), current_count, current_variety)
        print(f"找到 {len(word_map)} 个有效单词")
        logger.info(f"找到 {len(word_map)} 个有效单词")
        
        # 2. 初始化统计容器（内存占用低）
        total_counts = defaultdict(int)  # 单词总出现次数
        variety_counts = defaultdict(int)  # 单词出现的歌词记录数
        
        # 3. 分批读取歌词（避免一次性加载大量数据）
        batch_size = 50  # 每批处理50条（低配电脑可再减小至20-30）
        cursor.execute("""
            SELECT id, lyric_raw FROM raw 
            WHERE lyric_raw IS NOT NULL AND lyric_raw != ''
        """)
        
        processed_lyrics = 0
        while True:
            # 分批获取歌词
            lyric_batch = cursor.fetchmany(batch_size)
            if not lyric_batch:
                break
            
            # 处理当前批次歌词
            for lyric_id, lyric in lyric_batch:
                processed_lyrics += 1
                lyric_lower = lyric.lower()  # 只转一次小写，避免重复计算
                
                # 遍历所有单词，统计当前歌词中的出现情况
                for word_id, (word, word_lower, _, _) in word_map.items():
                    count = count_word_occurrences(lyric_lower, word_lower)
                    if count > 0:
                        total_counts[word_id] += count
                        variety_counts[word_id] += 1  # 同一歌词只计数一次
                        
                        #  verbose模式才打印详细信息（默认关闭）
                        if verbose:
                            print(f"\n歌词{lyric_id}: {lyric[:100]}..."  # 截断长歌词，减少IO
                                  f"\n  包含 {count} 个 '{word}'")
            
            # 每处理100条打印一次进度（减少IO操作）
            if processed_lyrics % 100 == 0:
                msg = f"已处理 {processed_lyrics} 条歌词..."
                print(msg)
                logger.info(msg)
        
        print(f"\n歌词处理完成，共处理 {processed_lyrics} 条有效歌词")
        logger.info(f"歌词处理完成，共处理 {processed_lyrics} 条有效歌词")
        
        # 4. 比较式更新数据库（只更新有变化的记录）
        update_data = []
        updated_count = 0
        
        for word_id, (word, _, current_count, current_variety) in word_map.items():
            new_count = total_counts.get(word_id, 0)
            new_variety = variety_counts.get(word_id, 0)
            
            # 只有当值发生变化时才更新
            if new_count != current_count or new_variety != current_variety:
                update_data.append((new_count, new_variety, word_id))
                updated_count += 1
                
                # 记录更新操作到日志
                change_details = []
                if new_count != current_count:
                    change_details.append(f"count: {current_count} -> {new_count}")
                if new_variety != current_variety:
                    change_details.append(f"variety: {current_variety} -> {new_variety}")
                
                log_msg = f"更新单词 '{word}'（ID: {word_id}）: {'; '.join(change_details)}"
                logger.info(log_msg)
            
            # 简化输出，只打印关键统计
            print(f"单词 '{word}'：总计 {new_count} 次，出现于 {new_variety} 条记录")
        
        # 执行批量更新
        if update_data:
            cursor.executemany("""
                UPDATE dictionary_headwords
                SET count = ?, variety = ? 
                WHERE id = ?
            """, update_data)
            cursor.execute("""
                UPDATE dictionary
                SET count = (SELECT h.count FROM dictionary_headwords h WHERE h.id = dictionary.headword_id),
                    variety = (SELECT h.variety FROM dictionary_headwords h WHERE h.id = dictionary.headword_id)
            """)
            conn.commit()
            msg = f"\n批量更新 {len(update_data)} 个单词的统计结果"
            print(msg)
            logger.info(msg)
        else:
            msg = "\n没有需要更新的统计数据"
            print(msg)
            logger.info(msg)
        
    except sqlite3.Error as e:
        error_msg = f"\n数据库错误: {e}"
        print(error_msg)
        logger.error(error_msg)
        if conn:
            conn.rollback()
    except Exception as e:
        error_msg = f"\n程序错误: {e}"
        print(error_msg)
        logger.error(error_msg)
    finally:
        if conn:
            conn.close()
            msg = "\n数据库连接已关闭"
            print(msg)
            logger.info(msg)

if __name__ == "__main__":
    # 默认关闭verbose模式（减少IO），需要详细输出可改为 main(verbose=True)
    main(verbose=False)
