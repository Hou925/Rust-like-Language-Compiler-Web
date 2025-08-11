import re

# 关键字（包括i32等类型）
KEYWORDS = {
    "i32", "let", "if", "else", "while", "return", "mut", "fn", "for",
    "in", "loop", "break", "continue"
}

TOKEN_SPECIFICATION = [
    ('COMMENT',  r'//.*|/\*[\s\S]*?\*/'),
    ('WS',       r'\s+'),
    ('ARROW',    r'->'),
    ('DOTDOT',   r'\.\.'),
    ('DOT',      r'\.'),
    ('NUMBER',   r'\d+'),
    ('ID',       r'[a-zA-Z_][a-zA-Z0-9_]*'),
    ('OP',       r'==|>=|<=|!=|>|<|\+|\-|\*|/'),
    ('ASSIGN',   r'='),
    ('DELIM',    r'\(|\)|\{|\}|\[|\]'),
    ('SEP',      r';|:|,'),
    ('ANDMUT',   r'&mut'),
    ('AND',      r'&'),
]


class Lexer:
    """
    一遍扫描的增量词法分析器：
    - 支持按需生成 Token（peek/k-步前瞻、next 消费）
    - 支持回溯（mark/reset），便于语法分析中的尝试-回退
    - 保持与原 tokenize() 完全一致的 Token 结构与分类命名
    """
    def __init__(self, code: str):
        self.code = code
        self._scanner = re.compile('|'.join(f'(?P<{name}>{pattern})' for name, pattern in TOKEN_SPECIFICATION))
        self._pos = 0                   # 源码当前位置（字符索引）
        self._buffer = []               # 前瞻缓冲（未被消费的 token）
        self._emitted = []              # 已被消费（next）的 token，用于前端展示
        self._eof_emitted = False       # 是否已发出 EOF（被消费）
        self._eof_buffered = False      # 是否已缓冲 EOF（用于前瞻）

    def _scan_next(self):
        """从源码当前位置向后搜索下一个 token，填充到缓冲区。跳过空白与注释。"""
        if self._eof_buffered:
            return

        while True:
            if self._pos >= len(self.code):
                # 缓冲 EOF
                self._buffer.append({'type': 'EOF', 'value': '', 'pos': len(self.code)})
                self._eof_buffered = True
                return

            m = self._scanner.search(self.code, self._pos)
            if not m:
                # 源码中剩余部分没有任何可匹配的 token，直接缓冲 EOF
                self._buffer.append({'type': 'EOF', 'value': '', 'pos': len(self.code)})
                self._pos = len(self.code)
                self._eof_buffered = True
                return

            kind = m.lastgroup
            value = m.group()
            start = m.start()
            end = m.end()
            self._pos = end

            if kind in ('WS', 'COMMENT'):
                # 跳过空白/注释，继续扫描
                continue

            if kind == 'ID' and value in KEYWORDS:
                kind = value.upper()

            self._buffer.append({'type': kind, 'value': value, 'pos': start})
            return

    def peek(self, k: int = 0):
        """前瞻第 k 个 token（k 从 0 开始）。不消费。"""
        while len(self._buffer) <= k:
            self._scan_next()
            # _scan_next 会在到达 EOF 时把 EOF 放入缓冲区然后返回
            # 循环在此处会自然终止

        return self._buffer[k]

    def next_token(self):
        """消费一个 token，并把它加入已发出序列。"""
        if not self._buffer:
            self._scan_next()

        tok = self._buffer.pop(0)
        # 记录被语法分析“真正消费”的 token
        self._emitted.append(tok)
        if tok['type'] == 'EOF':
            self._eof_emitted = True
        return tok

    def mark(self):
        """保存当前词法状态用于回溯。"""
        # 拷贝缓冲区的浅拷贝即可（token 字典是只读使用）
        return (self._pos, list(self._buffer), self._eof_buffered, list(self._emitted), self._eof_emitted)

    def reset(self, state):
        """回溯到 mark() 保存的状态。"""
        self._pos, self._buffer, self._eof_buffered, self._emitted, self._eof_emitted = state

    def drain_to_eof(self):
        """将剩余 token 全部消费至 EOF，便于前端展示完整词法结果。"""
        while True:
            tok = self.peek(0)
            self.next_token()
            if tok['type'] == 'EOF':
                break

    def get_tokens(self):
        """返回已消费的 token 列表（包含 EOF，若已 drain_to_eof）。"""
        return list(self._emitted)


# 兼容性：保留原先的 tokenize 函数，实现上改为使用增量 Lexer 一次性排空
def tokenize(code: str):
    lex = Lexer(code)
    lex.drain_to_eof()
    return lex.get_tokens()