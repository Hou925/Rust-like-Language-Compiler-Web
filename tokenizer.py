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

def tokenize(code):
    token_regex = '|'.join(f'(?P<{name}>{pattern})' for name, pattern in TOKEN_SPECIFICATION)
    scanner = re.compile(token_regex)
    tokens = []
    for match in scanner.finditer(code):
        kind = match.lastgroup
        value = match.group()
        start = match.start()
        if kind == 'ID':
            if value in KEYWORDS:
                kind = value.upper()
        elif kind == 'WS' or kind == 'COMMENT':
            continue
        tokens.append({'type': kind, 'value': value, 'pos': start})
    tokens.append({'type': 'EOF', 'value': '', 'pos': len(code)})
    return tokens