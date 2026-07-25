# 原作者：Meartraep
# 项目仓库：https://github.com/Meartraep/Alician_dictionary
# 协议：CC BY-NC 4.0 | 禁止商用，改编需保留署名
class HighlightManager:
    """高亮管理器，负责管理高亮单词的映射和状态跟踪"""
    def __init__(self, config_manager):
        self.config_manager = config_manager
        
        # 已知单词集合
        self.known_words = set()
        
        # 已知词组集合
        self.known_phrases = set()
        
        # 缓存单词的 count 和 variety 字段（用于蓝色高亮判断）
        # key -> (count:int, variety:int)
        self.word_stats = {}
        
        # 缓存词组的 count 和 variety 字段
        self.phrase_stats = {}
        
        # 存放当前被高亮的单词信息（按首出现位置记录）
        # key_for_map -> {'display': str, 'pos': int, 'type': 'unknown'/'lowstat', 'reasons': set(...) }
        self.highlighted_map = {}
    
    def clear(self):
        """清除所有高亮信息"""
        self.highlighted_map.clear()
        self.known_words.clear()
        self.known_phrases.clear()
        self.word_stats.clear()
        self.phrase_stats.clear()
    
    def clear_highlight_map(self):
        """仅清除高亮映射"""
        self.highlighted_map.clear()
    
    def load_known_words_from_db(self, db_manager):
        """从数据库加载已知单词和词组"""
        try:
            # 关闭旧连接，强制重新连接以获取最新数据
            db_manager.close_connection()
            
            # 获取新连接
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            # 加载单词
            cursor.execute("SELECT words, count, variety FROM dictionary_headwords")
            word_rows = cursor.fetchall()
            
            # 加载词组
            cursor.execute("SELECT PHRASE, count, variety FROM phrase")
            phrase_rows = cursor.fetchall()
            
            # 清空现有数据
            self.known_words.clear()
            self.known_phrases.clear()
            self.word_stats.clear()
            self.phrase_stats.clear()
            
            # 处理单词
            for row in word_rows:
                w = row[0]
                try:
                    c = int(row[1]) if row[1] is not None else 0
                except Exception:
                    c = 0
                try:
                    v = int(row[2]) if row[2] is not None else 0
                except Exception:
                    v = 0
                
                if self.config_manager.get("strict_case"):
                    self.known_words.add(w)
                    self.word_stats[w] = (c, v)
                else:
                    lw = w.lower()
                    self.known_words.add(lw)
                    self.word_stats[lw] = (c, v)
            
            # 处理词组
            for row in phrase_rows:
                p = row[0]
                try:
                    c = int(row[1]) if row[1] is not None else 0
                except Exception:
                    c = 0
                try:
                    v = int(row[2]) if row[2] is not None else 0
                except Exception:
                    v = 0
                
                if self.config_manager.get("strict_case"):
                    self.known_phrases.add(p)
                    self.phrase_stats[p] = (c, v)
                else:
                    lp = p.lower()
                    self.known_phrases.add(lp)
                    self.phrase_stats[lp] = (c, v)
            
            case_status = "严格区分大小写" if self.config_manager.get("strict_case") else "不区分大小写"
            return f"已加载 {len(self.known_words)} 个已知单词和 {len(self.known_phrases)} 个已知词组（{case_status}）"
        except Exception as e:
            print(f"数据库错误: {e}")
            raise Exception(f"数据库错误: {str(e)}")
    
    def check_word_status(self, word):
        """检查单词已知状态"""
        if self.config_manager.get("strict_case"):
            is_known = word in self.known_words
            key_for_stats = word
            map_key = word  # 用于唯一标识侧栏项（与大小写设置一致）
        else:
            lw = word.lower()
            is_known = lw in self.known_words
            key_for_stats = lw
            map_key = lw
        return is_known, key_for_stats, map_key
    
    def get_low_stat_reasons(self, count, variety):
        """获取低统计原因"""
        reasons = set()
        try:
            if count < 3:
                reasons.add('count')
            if variety < 3:
                reasons.add('variety')
        except Exception:
            pass
        return reasons
    
    def handle_unknown_word(self, word, start, map_key):
        """处理未知单词"""
        # 若尚未记录该词，记录其首出现位置与显示文本
        if map_key not in self.highlighted_map:
            self.highlighted_map[map_key] = {
                'display': word,
                'pos': start,
                'type': 'unknown',
                'reasons': set()
            }
    
    def handle_known_word(self, word, start, key_for_stats, map_key):
        """处理已知单词"""
        # 已知但需检查统计信息
        stats = self.word_stats.get(key_for_stats)
        if stats:
            c, v = stats
            low_reasons = self.get_low_stat_reasons(c, v)
            
            if low_reasons:
                # 若尚未记录该词，记录首出现位置与显示文本
                if map_key not in self.highlighted_map:
                    self.highlighted_map[map_key] = {
                        'display': word,
                        'pos': start,
                        'type': 'lowstat',
                        'reasons': low_reasons
                    }
                else:
                    # 如果已经记录（应为已知或其它），确保类型与原因合并
                    existing = self.highlighted_map[map_key]
                    # 若之前是 unknown，保持 unknown（红优先）
                    if existing['type'] != 'unknown':
                        existing['type'] = 'lowstat'
                        existing['reasons'].update(low_reasons)
    
    def update_highlight_map_unknown(self, map_key, word, global_start):
        """更新未知单词的高亮映射"""
        should_update = (
            map_key not in self.highlighted_map or 
            self.highlighted_map[map_key]['pos'] > global_start
        )
        
        if should_update:
            self.highlighted_map[map_key] = {
                'display': word,
                'pos': global_start,
                'type': 'unknown',
                'reasons': set()
            }
    
    def update_highlight_map_lowstat(self, map_key, word, global_start, low_reasons):
        """更新低统计单词的高亮映射"""
        if map_key not in self.highlighted_map:
            self.highlighted_map[map_key] = {
                'display': word,
                'pos': global_start,
                'type': 'lowstat',
                'reasons': low_reasons
            }
        else:
            existing = self.highlighted_map[map_key]
            if existing['type'] != 'unknown':
                existing['type'] = 'lowstat'
                existing['reasons'].update(low_reasons)
    
    def get_highlighted_words(self):
        """获取所有高亮单词的信息"""
        return self.highlighted_map
    
    def get_highlight_info(self, key):
        """获取特定单词的高亮信息"""
        return self.highlighted_map.get(key)
    
    def categorize_sidebar_items(self):
        """分类整理侧边栏项"""
        unknowns = []
        lowstats = []
        
        for key, info in self.highlighted_map.items():
            if info['type'] == 'unknown':
                unknowns.append((info['pos'], key, info))
            else:
                lowstats.append((info['pos'], key, info))
        
        return unknowns, lowstats
    
    def sort_sidebar_items(self, unknowns, lowstats):
        """排序侧边栏项"""
        unknowns.sort(key=lambda x: x[0])
        lowstats.sort(key=lambda x: x[0])
        
        # 合并排序后的列表，unknowns 优先
        return unknowns + lowstats
