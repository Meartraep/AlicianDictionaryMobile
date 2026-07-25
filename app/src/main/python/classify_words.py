import sqlite3
import os
import sys
import logging

def _get_db_path():
    env_db = os.environ.get("ALICIAN_DB_PATH")
    if env_db:
        return os.path.abspath(env_db)
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'translated.db')
    return os.path.join(os.path.dirname(__file__), 'translated.db')

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

def classify_words():
    # 初始化日志
    logger = setup_logger()
    logger.info("开始执行单词分类更新")
    
    # 数据库文件路径
    db_path = _get_db_path()
    
    # 检查数据库文件是否存在
    if not os.path.exists(db_path):
        error_msg = f"错误：数据库文件 '{db_path}' 不存在！"
        print(error_msg)
        logger.error(error_msg)
        return
    
    # 连接到数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 获取所有表名
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        table_names = [table[0] for table in tables]
        logger.info(f"数据库中的表: {table_names}")
        print("数据库中的表:")
        print(table_names)
        
        # 1. 处理有词性的单词
        print("\n=== 处理有词性的单词 ===")
        logger.info("开始处理有词性的单词")
        
        # 获取主词典表中的所有有词性的单词
        cursor.execute("SELECT words, explanation, count, variety, class FROM dictionary WHERE class IS NOT NULL AND class != '';")
        words = cursor.fetchall()
        
        # 统计变量
        total_processed = 0
        table_created = 0
        updated_count = 0
        inserted_count = 0
        
        # 遍历每个单词，根据class字段插入到对应的词性表中
        for word in words:
            word_name = word[0]
            explanation = word[1]
            count = word[2]
            variety = word[3]
            pos = word[4]
            
            # 检查表是否存在，如果不存在则创建
            if pos not in table_names:
                cursor.execute(f"CREATE TABLE '{pos}' (words TEXT, translation TEXT, count INTEGER, variety INTEGER);")
                table_names.append(pos)
                table_created += 1
                msg = f"已创建表 '{pos}'"
                print(msg)
                logger.info(msg)
            
            # 检查单词是否已存在于对应表中
            cursor.execute(f"SELECT translation, count, variety FROM '{pos}' WHERE words = ?;", (word_name,))
            existing = cursor.fetchone()
            
            if existing:
                existing_translation, existing_count, existing_variety = existing
                
                # 检查是否有变化
                changes = []
                if existing_translation != explanation:
                    changes.append(f"translation: {existing_translation} -> {explanation}")
                if existing_count != count:
                    changes.append(f"count: {existing_count} -> {count}")
                if existing_variety != variety:
                    changes.append(f"variety: {existing_variety} -> {variety}")
                
                if changes:
                    # 有变化，执行更新
                    try:
                        # 检查表结构，特别是variety列的名称
                        cursor.execute(f"PRAGMA table_info('{pos}');")
                        columns = cursor.fetchall()
                        column_names = [column[1] for column in columns]
                        
                        if 'vartety' in column_names:
                            # 处理conj.表的特殊情况
                            cursor.execute(f"UPDATE '{pos}' SET translation = ?, count = ?, vartety = ? WHERE words = ?;", 
                                          (explanation, count, variety, word_name))
                        else:
                            # 正常情况
                            cursor.execute(f"UPDATE '{pos}' SET translation = ?, count = ?, variety = ? WHERE words = ?;", 
                                          (explanation, count, variety, word_name))
                        updated_count += 1
                        
                        # 记录日志
                        change_details = "; ".join(changes)
                        log_msg = f"更新表 '{pos}' 中的单词 '{word_name}': {change_details}"
                        logger.info(log_msg)
                        print(f"已更新单词 '{word_name}' 到表 '{pos}'")
                    except Exception as e:
                        error_msg = f"更新单词 '{word_name}' 到表 '{pos}' 时出错: {e}"
                        print(error_msg)
                        logger.error(error_msg)
            else:
                # 单词不存在，执行插入
                try:
                    # 检查表结构，特别是variety列的名称
                    cursor.execute(f"PRAGMA table_info('{pos}');")
                    columns = cursor.fetchall()
                    column_names = [column[1] for column in columns]
                    
                    if 'vartety' in column_names:
                        # 处理conj.表的特殊情况
                        cursor.execute(f"INSERT INTO '{pos}' (words, translation, count, vartety) VALUES (?, ?, ?, ?);", 
                                      (word_name, explanation, count, variety))
                    else:
                        # 正常情况
                        cursor.execute(f"INSERT INTO '{pos}' (words, translation, count, variety) VALUES (?, ?, ?, ?);", 
                                      (word_name, explanation, count, variety))
                    inserted_count += 1
                    
                    # 记录日志
                    log_msg = f"插入单词 '{word_name}' 到表 '{pos}'"
                    logger.info(log_msg)
                    print(f"已插入单词 '{word_name}' 到表 '{pos}'")
                except Exception as e:
                    error_msg = f"插入单词 '{word_name}' 到表 '{pos}' 时出错: {e}"
                    print(error_msg)
                    logger.error(error_msg)
            
            total_processed += 1
        
        summary_msg = f"\n有词性单词处理完成！\n  - 处理单词数量: {total_processed}\n  - 创建表数量: {table_created}\n  - 插入: {inserted_count} 个\n  - 更新: {updated_count} 个"
        print(summary_msg)
        logger.info(summary_msg)
        
        # 2. 处理没有词性的单词
        print("\n=== 处理没有词性的单词 ===")
        logger.info("开始处理没有词性的单词")
        
        # 创建no_class表（如果不存在）
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='no_class';")
        if not cursor.fetchone():
            cursor.execute("CREATE TABLE no_class (words TEXT, translation TEXT, count INTEGER, variety INTEGER);")
            msg = "已创建no_class表"
            print(msg)
            logger.info(msg)
        
        # 获取主词典表中没有词性的单词
        cursor.execute("SELECT words, explanation, count, variety FROM dictionary WHERE class IS NULL OR class = '';")
        no_class_words = cursor.fetchall()
        
        print(f"找到 {len(no_class_words)} 个没有词性的单词")
        logger.info(f"找到 {len(no_class_words)} 个没有词性的单词")
        
        no_class_inserted = 0
        no_class_updated = 0
        
        for word in no_class_words:
            word_name = word[0]
            explanation = word[1]
            count = word[2]
            variety = word[3]
            
            # 检查单词是否已存在于no_class表中
            cursor.execute("SELECT translation, count, variety FROM no_class WHERE words = ?;", (word_name,))
            existing = cursor.fetchone()
            
            if existing:
                existing_translation, existing_count, existing_variety = existing
                
                # 检查是否有变化
                changes = []
                if existing_translation != explanation:
                    changes.append(f"translation: {existing_translation} -> {explanation}")
                if existing_count != count:
                    changes.append(f"count: {existing_count} -> {count}")
                if existing_variety != variety:
                    changes.append(f"variety: {existing_variety} -> {variety}")
                
                if changes:
                    # 有变化，执行更新
                    try:
                        cursor.execute("UPDATE no_class SET translation = ?, count = ?, variety = ? WHERE words = ?;", 
                                      (explanation, count, variety, word_name))
                        no_class_updated += 1
                        
                        # 记录日志
                        change_details = "; ".join(changes)
                        log_msg = f"更新表 'no_class' 中的单词 '{word_name}': {change_details}"
                        logger.info(log_msg)
                        print(f"已更新单词 '{word_name}' 到表 'no_class'")
                    except Exception as e:
                        error_msg = f"更新单词 '{word_name}' 到表 'no_class' 时出错: {e}"
                        print(error_msg)
                        logger.error(error_msg)
            else:
                # 单词不存在，执行插入
                try:
                    cursor.execute("INSERT INTO no_class (words, translation, count, variety) VALUES (?, ?, ?, ?);", 
                                  (word_name, explanation, count, variety))
                    no_class_inserted += 1
                    
                    # 记录日志
                    log_msg = f"插入单词 '{word_name}' 到表 'no_class'"
                    logger.info(log_msg)
                    print(f"已插入单词 '{word_name}' 到表 'no_class'")
                except Exception as e:
                    error_msg = f"插入单词 '{word_name}' 到表 'no_class' 时出错: {e}"
                    print(error_msg)
                    logger.error(error_msg)
        
        no_class_summary = f"\n无词性单词处理完成！\n  - 插入: {no_class_inserted} 个\n  - 更新: {no_class_updated} 个"
        print(no_class_summary)
        logger.info(no_class_summary)
        
        # 提交更改
        conn.commit()
        completion_msg = "\n数据分类完成!"
        print(completion_msg)
        logger.info(completion_msg)
        
    except Exception as e:
        error_msg = f"处理过程中出错: {e}"
        print(error_msg)
        logger.error(error_msg)
        conn.rollback()
    finally:
        # 关闭连接
        conn.close()
        logger.info("数据库连接已关闭")

if __name__ == "__main__":
    classify_words()
