# 原作者：Meartraep
# 项目仓库：https://github.com/Meartraep/Alician_dictionary
# 协议：CC BY-NC 4.0 | 禁止商用，改编需保留署名
import re


# 词典释义中标注“词义不确定”的记号，例如“闪耀(?)”“(?)”“待定（?）”。
# 写作助手只用它判定蓝色高亮；词频（count）与泛度（variety）不再参与。
UNCERTAIN_MARKER_PATTERN = re.compile(r"[（(]\s*[?？]\s*[）)]")


class HighlightManager:
    """高亮管理器，负责管理高亮单词的映射和状态跟踪。

    写作助手只有两类高亮：
    - 红色 ``unknown``：词典中没有的未知词；
    - 蓝色 ``uncertain``：词典词义带有 ``(?)`` 不确定标注的词或词组。
    """

    def __init__(self, config_manager):
        self.config_manager = config_manager

        # 已知单词集合
        self.known_words = set()

        # 已知词组集合
        self.known_phrases = set()

        # 词义不确定（释义含 (?) 标注）的单词与词组
        self.uncertain_words = set()
        self.uncertain_phrases = set()

        # 当前被高亮的项（按首出现位置记录）
        # key_for_map -> {'display': str, 'pos': int, 'type': 'unknown'/'uncertain'}
        self.highlighted_map = {}

    def clear(self):
        """清除所有高亮信息"""
        self.highlighted_map.clear()
        self.known_words.clear()
        self.known_phrases.clear()
        self.uncertain_words.clear()
        self.uncertain_phrases.clear()

    def clear_highlight_map(self):
        """仅清除高亮映射"""
        self.highlighted_map.clear()

    @staticmethod
    def has_uncertain_marker(explanation) -> bool:
        """判断释义是否带有 ``(?)`` / ``（?）`` 不确定标注。"""
        return bool(UNCERTAIN_MARKER_PATTERN.search(str(explanation or "")))

    def _case_key(self, text) -> str:
        """按当前大小写设置归一化键。"""
        text = str(text or "")
        return text if self.config_manager.get("strict_case") else text.lower()

    def load_known_words_from_db(self, db_manager):
        """从数据库加载已知单词和词组，并标记词义不确定项。"""
        try:
            # 关闭旧连接，强制重新连接以获取最新数据
            db_manager.close_connection()

            # 获取新连接
            conn = db_manager.get_connection()
            cursor = conn.cursor()

            # 词头展示释义是聚合结果；义项表才是每条“词义”的权威来源。
            cursor.execute(
                "SELECT id, words, display_explanation FROM dictionary_headwords"
            )
            word_rows = cursor.fetchall()

            cursor.execute("SELECT headword_id, explanation FROM dictionary")
            sense_rows = cursor.fetchall()

            cursor.execute("SELECT PHRASE, explanation FROM phrase")
            phrase_rows = cursor.fetchall()

            # 清空现有数据
            self.known_words.clear()
            self.known_phrases.clear()
            self.uncertain_words.clear()
            self.uncertain_phrases.clear()

            # 只要任一义项带 (?) 标注，该词就属于“词义不确定”。
            uncertain_headword_ids = set()
            for headword_id, explanation in sense_rows:
                if headword_id is None:
                    continue
                if self.has_uncertain_marker(explanation):
                    uncertain_headword_ids.add(int(headword_id))

            for headword_id, word, display_explanation in word_rows:
                key = self._case_key(word)
                self.known_words.add(key)
                if (
                    self.has_uncertain_marker(display_explanation)
                    or int(headword_id) in uncertain_headword_ids
                ):
                    self.uncertain_words.add(key)

            for phrase, explanation in phrase_rows:
                key = self._case_key(phrase)
                self.known_phrases.add(key)
                if self.has_uncertain_marker(explanation):
                    self.uncertain_phrases.add(key)

            case_status = "严格区分大小写" if self.config_manager.get("strict_case") else "不区分大小写"
            return (
                f"已加载 {len(self.known_words)} 个已知单词和 {len(self.known_phrases)} 个已知词组"
                f"（{case_status}；其中释义标注 (?) 的不确定单词 {len(self.uncertain_words)} 个、"
                f"词组 {len(self.uncertain_phrases)} 个）"
            )
        except Exception as e:
            print(f"数据库错误: {e}")
            raise Exception(f"数据库错误: {str(e)}")

    def check_word_status(self, word):
        """检查单词已知状态"""
        key = self._case_key(word)
        return key in self.known_words, key, key

    def is_uncertain_word(self, key) -> bool:
        return key in self.uncertain_words

    def is_uncertain_phrase(self, key) -> bool:
        return key in self.uncertain_phrases

    def handle_unknown_word(self, word, start, map_key):
        """处理未知单词"""
        if map_key not in self.highlighted_map:
            self.highlighted_map[map_key] = {
                'display': word,
                'pos': start,
                'type': 'unknown',
            }

    def _record_uncertain(self, map_key, word, start):
        """记录词义不确定项，保留首出现位置；未知词优先（红）。"""
        existing = self.highlighted_map.get(map_key)
        if existing is None or existing['pos'] > start:
            self.highlighted_map[map_key] = {
                'display': word,
                'pos': start,
                'type': 'uncertain',
            }
        elif existing['type'] != 'unknown':
            existing['type'] = 'uncertain'

    def handle_known_word(self, word, start, key, map_key) -> bool:
        """处理已知单词；返回是否需要标蓝（词义不确定）。"""
        if not self.is_uncertain_word(key):
            return False
        self._record_uncertain(map_key, word, start)
        return True

    def handle_known_phrase(self, phrase, start, key) -> bool:
        """处理已知词组；返回是否需要标蓝（词义不确定）。"""
        if not self.is_uncertain_phrase(key):
            return False
        self._record_uncertain(key, phrase, start)
        return True

    def update_highlight_map_unknown(self, map_key, word, global_start):
        """更新未知单词的高亮映射（增量检查路径）。"""
        should_update = (
            map_key not in self.highlighted_map or
            self.highlighted_map[map_key]['pos'] > global_start
        )

        if should_update:
            self.highlighted_map[map_key] = {
                'display': word,
                'pos': global_start,
                'type': 'unknown',
            }

    def get_highlighted_words(self):
        """获取所有高亮单词的信息"""
        return self.highlighted_map

    def get_highlight_info(self, key):
        """获取特定单词的高亮信息"""
        return self.highlighted_map.get(key)

    def categorize_sidebar_items(self):
        """分类整理侧边栏项：未知词与词义不确定词。"""
        unknowns = []
        uncertains = []

        for key, info in self.highlighted_map.items():
            if info['type'] == 'unknown':
                unknowns.append((info['pos'], key, info))
            else:
                uncertains.append((info['pos'], key, info))

        return unknowns, uncertains

    def sort_sidebar_items(self, unknowns, uncertains):
        """排序侧边栏项：未知词优先，其次按首出现位置。"""
        unknowns.sort(key=lambda x: x[0])
        uncertains.sort(key=lambda x: x[0])

        return unknowns + uncertains
