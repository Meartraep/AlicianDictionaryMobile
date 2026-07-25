# 原作者：Meartraep
# 项目仓库：https://github.com/Meartraep/Alician_dictionary
# 协议：CC BY-NC 4.0 | 禁止商用，改编需保留署名
import re
import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

class WordChecker:
    """单词检查器，负责单词的检查、高亮逻辑和统计分析"""
    
    # 预编译正则表达式
    WORD_PATTERN = re.compile(r"\b[a-zA-Z]+\b")  # 匹配单词的正则表达式
    PHRASE_PATTERN = re.compile(r"\b[a-zA-Z]+(?:\s+[a-zA-Z]+)+\b")  # 匹配词组的正则表达式
    CONTEXT_RADIUS = 96
    MIN_CONTEXT_WORDS_FOR_ALICIAN = 4
    DEFAULT_DEFINITION_SEPARATORS = (":", "：")
    COMMON_FOREIGN_WORDS = {
        "a", "able", "about", "above", "after", "again", "against", "all", "almost",
        "along", "already", "also", "although", "always", "am", "among", "an", "and",
        "another", "any", "are", "around", "as", "ask", "at", "away", "back", "be",
        "because", "been", "before", "being", "between", "both", "but", "by", "can",
        "cannot", "could", "day", "did", "do", "does", "done", "down", "during", "each",
        "either", "else", "even", "ever", "every", "few", "find", "first", "for", "from",
        "get", "give", "go", "good", "got", "had", "has", "have", "he", "her", "here",
        "hers", "him", "his", "how", "however", "i", "if", "in", "into", "is", "it",
        "its", "just", "know", "last", "let", "like", "long", "look", "made", "make",
        "many", "may", "me", "might", "more", "most", "much", "must", "my", "never",
        "new", "no", "nor", "not", "now", "of", "off", "on", "once", "one", "only",
        "or", "other", "our", "out", "over", "own", "people", "put", "said", "same",
        "say", "see", "she", "should", "since", "so", "some", "still", "such", "take",
        "than", "that", "the", "their", "them", "then", "there", "these", "they",
        "thing", "this", "those", "through", "time", "to", "too", "under", "until",
        "up", "us", "use", "very", "want", "was", "way", "we", "well", "were", "what",
        "when", "where", "which", "while", "who", "why", "will", "with", "would", "you",
        "your"
    }
    
    def __init__(self, root, text_area, highlight_manager, config_manager):
        self.root = root
        self.text_area = text_area
        self.highlight_manager = highlight_manager
        self.config_manager = config_manager
        
        # 检查延迟（用于防抖）
        self.check_delay = None
        
        # 用于增量检查
        self.last_text_hash = None  # 上次检查的文本哈希值
        self.last_checked_text = ""  # 上次检查的完整文本
        
        # 优化文本更新：设置延迟更新标志
        self._updating_highlight = False
        self._pending_highlight_update = False
        
        # 存储匹配到的词组位置，用于避免重复检查
        self._matched_phrases = set()
        self._alician_shape_cache = None
        self._close_alician_neighbor_cache = {}
    
    def schedule_check(self, event=None):
        """触发单词检查，带防抖机制"""
        if self.check_delay:
            self.root.after_cancel(self.check_delay)
        # 增加延迟时间以减少检查频率，特别是对大文件
        delay_ms = 200 if len(self.text_area.get("1.0", "end")) > 10000 else 100
        self.check_delay = self.root.after(delay_ms, self.check_words)
    
    def check_words(self):
        """检查文本中的单词并高亮显示未知单词；同时对低统计单词标蓝；并更新侧边栏"""
        text = self.text_area.get("1.0", "end")
        current_hash = hash(text)
        
        # 文本为空时的处理
        if not text.strip():
            self._handle_empty_text()
            return
        
        # 如果文本没有变化，直接返回
        if self._is_text_unchanged(current_hash):
            return
        
        # 对于小文件或者首次检查，使用全量扫描
        if len(text) < 10000 or self.last_text_hash is None:
            return self._full_text_check(text)
        
        # 对于大文件，尝试增量检查
        return self._perform_incremental_check(text, current_hash)
    
    def _handle_empty_text(self):
        """处理空文本情况"""
        # 清除所有高亮
        self._clear_all_highlights()
        
        # 清除高亮映射
        self.highlight_manager.clear_highlight_map()
        
        # 更新状态
        self.last_text_hash = None
        self.last_checked_text = ""
    
    def _is_text_unchanged(self, current_hash):
        """检查文本是否未变化"""
        return self.last_text_hash is not None and current_hash == self.last_text_hash
    
    def _perform_incremental_check(self, text, current_hash):
        """执行增量检查"""
        try:
            # 获取变化的行范围
            changed_lines = self._get_changed_lines(self.last_checked_text, text)
            if not changed_lines:
                self._update_text_state(current_hash, text)
                return
                
            # 清除变化行的高亮
            self._clear_changed_lines_highlight(changed_lines)
            
            # 重新检查变化的行
            unknown_count = self._check_changed_lines(text, changed_lines)
            
            # 更新文本状态
            self._update_text_state(current_hash, text)
            
            return unknown_count
        except Exception as e:
            logger.error(f"增量检查出错: {e}")
            # 出错时回退到全量检查
            return self._full_text_check(text)
    
    def _update_text_state(self, current_hash, text):
        """更新文本状态"""
        self.last_text_hash = current_hash
        self.last_checked_text = text
    
    def _clear_all_highlights(self):
        """清除所有高亮"""
        self.text_area.tag_remove("unknown", "1.0", "end")
        self.text_area.tag_remove("lowstat", "1.0", "end")
    
    def _clear_changed_lines_highlight(self, changed_lines):
        """清除变化行的高亮"""
        for line_num in changed_lines:
            start_pos = f"{line_num}.0"
            end_pos = f"{line_num}.end"
            self.text_area.tag_remove("unknown", start_pos, end_pos)
            self.text_area.tag_remove("lowstat", start_pos, end_pos)
    
    def _full_text_check(self, text):
        """全量检查文本中的所有单词和词组"""
        # 移除所有高亮
        self._clear_all_highlights()
        
        # 清空高亮映射
        self.highlight_manager.clear_highlight_map()
        
        unknown_count = 0
        
        # 批量处理：先收集所有需要添加的标签
        tags_to_add = {"unknown": [], "lowstat": []}
        
        # 1. 先检查并标记所有词组
        matched_phrases = self._check_phrases(text, tags_to_add)
        
        # 2. 然后检查所有独立单词（不在词组中的单词）
        unknown_count = self._check_independent_words(text, matched_phrases, tags_to_add)
        
        # 3. 批量应用标签，减少UI更新次数
        self._apply_collected_tags(tags_to_add)
        
        # 保存当前文本状态
        self.last_text_hash = hash(text)
        self.last_checked_text = text
        
        return unknown_count
    
    def _check_phrases(self, text, tags_to_add):
        """检查文本中的词组并返回匹配到的词组位置"""
        matched_phrases = set()
        
        # 获取所有已知词组，并按长度降序排序
        known_phrases = list(self.highlight_manager.known_phrases)
        known_phrases.sort(key=lambda x: len(x), reverse=True)
        
        # 遍历所有可能的词组位置
        for match in self.PHRASE_PATTERN.finditer(text):
            phrase_candidate = match.group()
            start = match.start()
            end = match.end()

            if self._is_definition_region(text, start):
                continue
            
            # 检查候选词组是否在已知词组中
            if self.config_manager.get("strict_case"):
                is_known = phrase_candidate in self.highlight_manager.known_phrases
                key_for_stats = phrase_candidate
            else:
                phrase_lower = phrase_candidate.lower()
                is_known = phrase_lower in self.highlight_manager.known_phrases
                key_for_stats = phrase_lower
            
            if is_known:
                # 标记词组位置
                matched_phrases.add((start, end))
                
                # 词组被视为已知，无需高亮
                # 记录词组统计信息
                stats = self.highlight_manager.phrase_stats.get(key_for_stats)
                if stats:
                    c, v = stats
                    low_reasons = self.highlight_manager.get_low_stat_reasons(c, v)
                    if low_reasons:
                        # 低统计词组，添加蓝色高亮
                        start_pos = self.get_text_index(text, start)
                        end_pos = self.get_text_index(text, end)
                        tags_to_add["lowstat"].append((start_pos, end_pos))
        
        return matched_phrases
    
    def _check_independent_words(self, text, matched_phrases, tags_to_add):
        """检查不在词组中的独立单词"""
        unknown_count = 0
        
        # 获取排除项列表
        excluded_words = self.config_manager.get("excluded_words", [])
        
        # 遍历所有单词
        for match in self.WORD_PATTERN.finditer(text):
            word = match.group()
            start = match.start()
            end = match.end()

            if self._is_definition_region(text, start):
                continue
            
            # 检查单词是否在已知词组中
            if self._is_word_in_phrase(start, end, matched_phrases):
                continue  # 跳过词组中的单词
            
            # 检查单词是否在排除项中
            if word in excluded_words:
                continue  # 跳过排除项中的单词
            
            start_pos = self.get_text_index(text, start)
            end_pos = self.get_text_index(text, end)
            
            # 检查单词状态
            is_known, key_for_stats, map_key = self.highlight_manager.check_word_status(word)
            
            if not is_known:
                if self._should_ignore_foreign_word(word, text, start, end):
                    continue
                # 未知单词
                tags_to_add["unknown"].append((start_pos, end_pos))
                self.highlight_manager.handle_unknown_word(word, start, map_key)
                unknown_count += 1
            else:
                # 已知单词，检查统计信息
                self.highlight_manager.handle_known_word(word, start, key_for_stats, map_key)
                
                # 检查是否需要低统计高亮
                stats = self.highlight_manager.word_stats.get(key_for_stats)
                if stats:
                    c, v = stats
                    low_reasons = self.highlight_manager.get_low_stat_reasons(c, v)
                    if low_reasons:
                        tags_to_add["lowstat"].append((start_pos, end_pos))
        
        return unknown_count
    
    def _is_word_in_phrase(self, word_start, word_end, matched_phrases):
        """检查单词是否在匹配到的词组中"""
        for phrase_start, phrase_end in matched_phrases:
            if word_start >= phrase_start and word_end <= phrase_end:
                return True
        return False
    
    def _apply_collected_tags(self, tags_to_add):
        """批量应用收集的标签"""
        # 先应用unknown标签（红色）
        for start_idx, end_idx in tags_to_add["unknown"]:
            self.text_area.tag_add("unknown", start_idx, end_idx)
        
        # 再应用lowstat标签（蓝色）
        for start_idx, end_idx in tags_to_add["lowstat"]:
            self.text_area.tag_add("lowstat", start_idx, end_idx)
            
        # 强制进行一次批量UI更新
        self.text_area.update_idletasks()
    
    def _get_changed_lines(self, old_text, new_text):
        """获取文本中发生变化的行号列表"""
        old_lines = old_text.split('\n')
        new_lines = new_text.split('\n')
        
        # 简单实现：找到第一个不同的行，然后假设之后的所有行都可能受影响
        changed_lines = set()
        max_lines = max(len(old_lines), len(new_lines))
        
        for i in range(max_lines):
            old_line = old_lines[i] if i < len(old_lines) else ""
            new_line = new_lines[i] if i < len(new_lines) else ""
            
            if old_line != new_line:
                # 记录变化的行，以及前后各一行（可能受单词分割影响）
                for j in range(max(0, i-1), min(max_lines, i+2)):
                    changed_lines.add(j+1)  # tkinter行号从1开始
        
        return sorted(changed_lines)
    
    def _check_changed_lines(self, text, changed_lines):
        """优化的变更行检查逻辑"""
        # 如果没有变更行，直接返回
        if not changed_lines:
            return 0
            
        unknown_count = 0
        text_lines = text.split('\n')
        
        # 建立位置映射，用于快速找到行号对应的字符位置
        line_positions = self._build_line_positions(text_lines)
        
        # 批量操作：先收集所有需要添加的标签
        tags_to_add = {"unknown": [], "lowstat": []}
        
        # 检查每一行
        for line_num in changed_lines:
            if not self._is_valid_line(line_num, text_lines):
                continue
                
            line_index = line_num - 1
            line_text = text_lines[line_index]
            line_start_pos = line_positions[line_index]
            
            # 处理当前行中的所有单词
            line_unknown_count = self._process_line_words(
                line_text, line_start_pos, text, tags_to_add
            )
            unknown_count += line_unknown_count
        
        # 批量清除和应用标签
        self._apply_tags_batch(changed_lines, tags_to_add)
        
        return unknown_count
    
    def _build_line_positions(self, text_lines):
        """建立行位置映射"""
        line_positions = [0]  # 行开始的字符位置
        for line in text_lines:
            line_positions.append(line_positions[-1] + len(line) + 1)  # +1 for newline
        return line_positions
    
    def _is_valid_line(self, line_num, text_lines):
        """验证行号是否有效"""
        return 1 <= line_num <= len(text_lines)
    
    def _process_line_words(self, line_text, line_start_pos, full_text, tags_to_add):
        """处理单行中的所有单词和词组"""
        unknown_count = 0
        
        # 1. 先检查并标记当前行中的词组
        matched_phrases = self._check_line_phrases(line_text, line_start_pos, full_text, tags_to_add)
        
        # 2. 然后检查当前行中的独立单词（不在词组中的单词）
        unknown_count = self._check_line_independent_words(
            line_text, line_start_pos, full_text, matched_phrases, tags_to_add
        )
        
        return unknown_count
    
    def _check_line_phrases(self, line_text, line_start_pos, full_text, tags_to_add):
        """检查当前行中的词组"""
        matched_phrases = set()
        
        # 遍历当前行中所有可能的词组位置
        for match in self.PHRASE_PATTERN.finditer(line_text):
            phrase_candidate = match.group()
            word_start = match.start()
            word_end = match.end()
            
            # 计算全局位置
            global_start = line_start_pos + word_start
            global_end = line_start_pos + word_end

            if self._is_definition_region(full_text, global_start):
                continue
            
            # 检查候选词组是否在已知词组中
            if self.config_manager.get("strict_case"):
                is_known = phrase_candidate in self.highlight_manager.known_phrases
                key_for_stats = phrase_candidate
            else:
                phrase_lower = phrase_candidate.lower()
                is_known = phrase_lower in self.highlight_manager.known_phrases
                key_for_stats = phrase_lower
            
            if is_known:
                # 标记词组位置
                matched_phrases.add((global_start, global_end))
                
                # 检查是否需要低统计高亮
                stats = self.highlight_manager.phrase_stats.get(key_for_stats)
                if stats:
                    c, v = stats
                    low_reasons = self.highlight_manager.get_low_stat_reasons(c, v)
                    if low_reasons:
                        # 低统计词组，添加蓝色高亮
                        start_pos = self.get_text_index(full_text, global_start)
                        end_pos = self.get_text_index(full_text, global_end)
                        tags_to_add["lowstat"].append((start_pos, end_pos))
        
        return matched_phrases
    
    def _check_line_independent_words(self, line_text, line_start_pos, full_text, matched_phrases, tags_to_add):
        """检查当前行中不在词组中的独立单词"""
        unknown_count = 0
        
        # 遍历当前行中的所有单词
        for match in self.WORD_PATTERN.finditer(line_text):
            word = match.group()
            word_start = match.start()
            word_end = match.end()
            
            # 计算全局位置
            global_start = line_start_pos + word_start
            global_end = line_start_pos + word_end
            
            # 检查单词是否在已知词组中
            if self._is_word_in_phrase(global_start, global_end, matched_phrases):
                continue  # 跳过词组中的单词
            
            # 转换为tkinter索引
            start_pos = self.get_text_index(full_text, global_start)
            end_pos = self.get_text_index(full_text, global_end)
            
            # 处理单个单词
            if self._process_single_word(word, start_pos, end_pos, global_start, tags_to_add):
                unknown_count += 1
                
        return unknown_count
    
    def _process_single_word(self, word, start_pos, end_pos, global_start, tags_to_add):
        """处理单个单词，返回是否为未知单词"""
        full_text = self.text_area.get("1.0", "end")
        if self._is_definition_region(full_text, global_start):
            return False

        # 检查单词是否在排除项中
        excluded_words = self.config_manager.get("excluded_words", [])
        if word in excluded_words:
            return False  # 排除项中的单词视为已知，不返回未知计数
        
        is_known, key_for_stats, map_key = self.highlight_manager.check_word_status(word)
        
        if not is_known:
            if self._should_ignore_foreign_word(word, full_text, global_start, global_start + len(word)):
                return False
            # 未知单词
            tags_to_add["unknown"].append((start_pos, end_pos))
            self.highlight_manager.update_highlight_map_unknown(map_key, word, global_start)
            return True
        else:
            # 已知单词，检查统计信息
            self._process_known_word(word, key_for_stats, map_key, start_pos, end_pos, global_start, tags_to_add)
            return False
    
    def _process_known_word(self, word, key_for_stats, map_key, start_pos, end_pos, global_start, tags_to_add):
        """处理已知单词"""
        # 检查是否需要低统计高亮
        stats = self.highlight_manager.word_stats.get(key_for_stats)
        if stats:
            c, v = stats
            low_reasons = self.highlight_manager.get_low_stat_reasons(c, v)
            if low_reasons:
                tags_to_add["lowstat"].append((start_pos, end_pos))
                self.highlight_manager.update_highlight_map_lowstat(map_key, word, global_start, low_reasons)

    def _normalize_word(self, word):
        return str(word or "").lower()

    def _is_definition_region(self, text, start):
        """Treat the right side of a word-list separator as explanatory text."""
        if not self.config_manager.get("dictionary_format_enabled", False):
            return False
        separators = self.config_manager.get(
            "dictionary_format_separators",
            list(self.DEFAULT_DEFINITION_SEPARATORS)
        )
        if isinstance(separators, str):
            separators = [separators]
        separators = [str(separator) for separator in (separators or []) if str(separator)]
        if not separators:
            return False
        line_start = text.rfind("\n", 0, start) + 1
        prefix = text[line_start:start]
        return any(separator in prefix for separator in separators)

    def _get_alician_shape_data(self):
        """Build lightweight orthography hints from the loaded Alician dictionary."""
        if self._alician_shape_cache is not None:
            return self._alician_shape_cache

        words = [self._normalize_word(w) for w in self.highlight_manager.known_words if w]
        words = [w for w in words if self.WORD_PATTERN.fullmatch(w)]
        bigrams = set()
        trigrams = set()
        suffixes = set()
        prefixes = set()
        for word in words:
            for i in range(max(0, len(word) - 1)):
                bigrams.add(word[i:i + 2])
            for i in range(max(0, len(word) - 2)):
                trigrams.add(word[i:i + 3])
            if len(word) >= 3:
                prefixes.add(word[:3])
                suffixes.add(word[-3:])
            elif word:
                prefixes.add(word)
                suffixes.add(word)

        self._alician_shape_cache = {
            "bigrams": bigrams,
            "trigrams": trigrams,
            "prefixes": prefixes,
            "suffixes": suffixes,
        }
        return self._alician_shape_cache

    def _is_known_alician_word(self, word):
        is_known, _, _ = self.highlight_manager.check_word_status(word)
        return bool(is_known)

    def _alician_context_score(self, text, start, end):
        left = max(0, start - self.CONTEXT_RADIUS)
        right = min(len(text), end + self.CONTEXT_RADIUS)
        context = text[left:right]
        total = 0
        known = 0
        for match in self.WORD_PATTERN.finditer(context):
            token = match.group()
            token_start = left + match.start()
            token_end = left + match.end()
            if token_start == start and token_end == end:
                continue
            if self._normalize_word(token) in self.COMMON_FOREIGN_WORDS:
                continue
            total += 1
            if self._is_known_alician_word(token):
                known += 1
        if total == 0:
            return 0.0, 0, 0
        return known / total, known, total

    def _alician_shape_score(self, word):
        normalized = self._normalize_word(word)
        if len(normalized) <= 2:
            return 0.0

        data = self._get_alician_shape_data()
        score = 0.0
        bigrams = [normalized[i:i + 2] for i in range(len(normalized) - 1)]
        trigrams = [normalized[i:i + 3] for i in range(len(normalized) - 2)]

        if bigrams:
            score += sum(1 for bg in bigrams if bg in data["bigrams"]) / len(bigrams)
        if trigrams:
            score += sum(1 for tg in trigrams if tg in data["trigrams"]) / len(trigrams) * 1.4
        if normalized[:3] in data["prefixes"]:
            score += 0.45
        if normalized[-3:] in data["suffixes"]:
            score += 0.45

        if any(ch in normalized for ch in "jqxz"):
            score += 0.25
        if re.search(r"(ai|ei|ia|ie|ll|ss|ql|sy|ty|iy)", normalized):
            score += 0.25
        return score

    def _has_close_alician_neighbor(self, word):
        normalized = self._normalize_word(word)
        if len(normalized) < 4:
            return False
        if normalized in self._close_alician_neighbor_cache:
            return self._close_alician_neighbor_cache[normalized]
        threshold = 0.86 if len(normalized) <= 5 else 0.78
        best = 0.0
        for known in self.highlight_manager.known_words:
            candidate = self._normalize_word(known)
            if not candidate or candidate in self.COMMON_FOREIGN_WORDS:
                continue
            if abs(len(candidate) - len(normalized)) > 2:
                continue
            ratio = SequenceMatcher(None, normalized, candidate).ratio()
            if ratio > best:
                best = ratio
                if best >= threshold:
                    self._close_alician_neighbor_cache[normalized] = True
                    return True
        self._close_alician_neighbor_cache[normalized] = False
        return False

    def _should_ignore_foreign_word(self, word, text, start, end):
        """Skip obvious non-Alician prose while keeping typos in Alician context visible."""
        normalized = self._normalize_word(word)
        if not normalized:
            return True

        if normalized in self.COMMON_FOREIGN_WORDS:
            return True

        context_ratio, known_context, total_context = self._alician_context_score(text, start, end)
        if total_context == 0:
            return False
        if known_context > 0:
            return False
        shape_score = self._alician_shape_score(word)
        if total_context < self.MIN_CONTEXT_WORDS_FOR_ALICIAN and known_context == 0:
            return shape_score < 1.8
        if total_context >= self.MIN_CONTEXT_WORDS_FOR_ALICIAN and known_context == 0:
            return True

        if self._has_close_alician_neighbor(word):
            return False

        if known_context >= 2 and context_ratio >= 0.2 and shape_score >= 2.8:
            return False
        if known_context >= 1 and total_context < self.MIN_CONTEXT_WORDS_FOR_ALICIAN and shape_score >= 3.0:
            return False

        return True
    
    def _apply_tags_batch(self, changed_lines, tags_to_add):
        """批量应用标签"""
        # 批量清除标签
        for line_num in changed_lines:
            start_pos = f"{line_num}.0"
            end_pos = f"{line_num}.end"
            self.text_area.tag_remove("unknown", start_pos, end_pos)
            self.text_area.tag_remove("lowstat", start_pos, end_pos)
        
        # 批量应用标签
        for start_idx, end_idx in tags_to_add["unknown"]:
            self.text_area.tag_add("unknown", start_idx, end_idx)
        
        for start_idx, end_idx in tags_to_add["lowstat"]:
            self.text_area.tag_add("lowstat", start_idx, end_idx)
            
        # 强制进行一次批量UI更新
        self.text_area.update_idletasks()
    
    def get_text_index(self, text, char_pos):
        """将字符位置转换为tkinter文本索引"""
        line = text.count('\n', 0, char_pos) + 1
        if line == 1:
            col = char_pos
        else:
            last_newline = text.rfind('\n', 0, char_pos)
            col = char_pos - last_newline - 1
        return f"{line}.{col}"
    
    def reset_state(self):
        """重置检查器状态，当配置更改时调用"""
        self.last_text_hash = None
        self.last_checked_text = ""
        self._close_alician_neighbor_cache.clear()
        # 清除高亮映射
        self.highlight_manager.clear_highlight_map()
