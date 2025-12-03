from collections import namedtuple
from tokenizer import Lexer

Token = namedtuple("Token", ["type", "value", "pos"])


class Parser:
    """
    改为一遍扫描：语法分析驱动词法分析
    - 使用 tokenizer.Lexer 按需取 token
    - 保持原有语法与错误信息风格
    """
    def __init__(self, code: str):
        self.lexer = Lexer(code)

    def _to_token(self, tok_dict):
        return Token(tok_dict['type'], tok_dict['value'], tok_dict['pos'])

    def peek(self, step=0):
        tok = self.lexer.peek(step)
        return self._to_token(tok)

    def match(self, *token_types, values=None):
        tok = self.peek()
        if tok.type in token_types and (values is None or tok.value in values):
            consumed = self._to_token(self.lexer.next_token())
            return consumed
        return None

    def expect(self, *token_types, values=None):
        tok = self.match(*token_types, values=values)
        if not tok:
            cur = self.peek()
            msg = (f"语法错误: 期望 {'/'.join(token_types)}，"
                   f"但遇到 {cur.type} ('{cur.value}')，"
                   f"在代码第{cur.pos}字符处")
            raise SyntaxError(msg)
        return tok

    def parse_program(self):
        decls = []
        while self.peek().type != 'EOF':
            decls.append(self.parse_function())
        return {"type": "Program", "decls": decls}

    def parse_function(self):
        self.expect('FN')
        name = self.expect('ID')
        self.expect('DELIM', values=['('])
        params = self.parse_params()
        self.expect('DELIM', values=[')'])
        ret_type = None
        if self.match('ARROW'):
            ret_type = self.parse_type()
        block = self.parse_func_body()
        return {"type": "Function", "name": name.value, "params": params, "ret_type": ret_type, "body": block}

    def parse_params(self):
        params = []
        if self.peek().type == 'DELIM' and self.peek().value == ')':
            return params
        while True:
            mut = self.match('MUT')
            pname = self.expect('ID')
            self.expect('SEP', values=[':'])
            ptype = self.parse_type()
            params.append({"mut": bool(mut), "name": pname.value, "type": ptype})
            if self.match('SEP', values=[',']):
                continue
            else:
                break
        return params

    def parse_type(self):
        if self.match('ANDMUT'):
            return {'ref': 'mut', 'to': self.parse_type()}
        elif self.match('AND'):
            return {'ref': 'imm', 'to': self.parse_type()}
        elif self.match('DELIM', values=['[']):
            ty = self.parse_type()
            self.expect('SEP', values=[';'])
            num = self.expect('NUMBER')
            self.expect('DELIM', values=[']'])
            return {'array': ty, 'size': int(num.value)}
        elif self.match('DELIM', values=['(']):
            inner = []
            if self.peek().type == 'DELIM' and self.peek().value == ')':
                self.match('DELIM', values=[')'])
                return {'tuple': []}
            while True:
                inner.append(self.parse_type())
                if self.match('SEP', values=[',']):
                    continue
                break
            self.expect('DELIM', values=[')'])
            return {'tuple': inner}
        else:
            idt = self.match('I32')
            if not idt:
                cur = self.peek()
                raise SyntaxError(f"期望类型关键字i32，但遇到{cur.type}('{cur.value}')，在{cur.pos}处")
            return {'id': idt.value}

    def parse_func_body(self):
        if self.peek().type == 'DELIM' and self.peek().value == '{':
            return self.parse_block()
        else:
            return self.parse_expr()

    def parse_block(self):
        self.expect('DELIM', values=['{'])
        stmts = []
        while True:
            if self.peek().type == 'DELIM' and self.peek().value == '}':
                self.match('DELIM', values=['}'])
                return {"type": "Block", "stmts": stmts}
            mark = self.lexer.mark()
            try:
                stmt = self.parse_stmt()
                stmts.append(stmt)
                continue
            except SyntaxError:
                # 回溯后作为表达式处理
                self.lexer.reset(mark)
                expr = self.parse_expr()
                if self.peek().type == 'DELIM' and self.peek().value == '}':
                    self.match('DELIM', values=['}'])
                    stmts.append({"type": "ExprStmt", "expr": expr, "tail": True})
                    return {"type": "Block", "stmts": stmts}
                else:
                    self.expect('SEP', values=[';'])
                    stmts.append({"type": "ExprStmt", "expr": expr})
                    continue

    def parse_stmt(self):
        tok = self.peek()
        if tok.type == 'LET':
            return self.parse_let_stmt()
        elif tok.type == 'RETURN':
            return self.parse_return_stmt()
        elif tok.type == 'IF':
            return self.parse_if_stmt()
        elif tok.type == 'WHILE':
            return self.parse_while_stmt()
        elif tok.type == 'FOR':
            return self.parse_for_stmt()
        elif tok.type == 'LOOP':
            return self.parse_loop_stmt()
        elif tok.type == 'BREAK':
            return self.parse_break_stmt()
        elif tok.type == 'CONTINUE':
            return self.parse_continue_stmt()
        elif tok.type == 'SEP' and tok.value == ';':
            self.match('SEP')
            return {"type": "Empty"}
        else:
            return self.parse_assign_or_expr_stmt()

    def parse_let_stmt(self):
        self.expect('LET')
        mut = self.match('MUT')
        name = self.expect('ID')
        ty = None
        if self.match('SEP', values=[':']):
            ty = self.parse_type()
        val = None
        if self.match('ASSIGN'):
            val = self.parse_expr()
        self.expect('SEP', values=[';'])
        return {"type": "Let", "mut": bool(mut), "name": name.value, "ty": ty, "val": val}

    def parse_return_stmt(self):
        self.expect('RETURN')
        if not (self.peek().type == 'SEP' and self.peek().value == ';'):
            expr = self.parse_expr()
        else:
            expr = None
        self.expect('SEP', values=[';'])
        return {"type": "Return", "expr": expr}

    def parse_if_stmt(self):
        self.expect('IF')
        cond = self.parse_expr()
        then_block = self.parse_block_or_expr()
        else_block = None
        if self.match('ELSE'):
            if self.peek().type == 'IF':
                else_block = self.parse_if_stmt()
            else:
                else_block = self.parse_block_or_expr()
        return {"type": "If", "cond": cond, "then": then_block, "else": else_block}

    def parse_while_stmt(self):
        self.expect('WHILE')
        cond = self.parse_expr()
        block = self.parse_block_or_expr()
        return {"type": "While", "cond": cond, "body": block}

    def parse_for_stmt(self):
        self.expect('FOR')
        mut = self.match('MUT')
        name = self.expect('ID')
        self.expect('IN')
        iterobj = self.parse_iterable()
        block = self.parse_block_or_expr()
        return {"type": "For", "iter": {"mut": bool(mut), "name": name.value, "iter": iterobj}, "body": block}

    def parse_iterable(self):
        left = self.parse_expr()
        if self.match('DOTDOT'):
            right = self.parse_expr()
            return {'range': (left, right)}
        return left

    def parse_loop_stmt(self):
        self.expect('LOOP')
        block = self.parse_block_or_expr()
        return {"type": "Loop", "body": block}

    def parse_break_stmt(self):
        self.expect('BREAK')
        expr = None
        if not (self.peek().type == 'SEP' and self.peek().value == ';'):
            expr = self.parse_expr()
        self.expect('SEP', values=[';'])
        return {"type": "Break", "expr": expr}

    def parse_continue_stmt(self):
        self.expect('CONTINUE')
        self.expect('SEP', values=[';'])
        return {"type": "Continue"}

    def parse_assign_or_expr_stmt(self):
        mark = self.lexer.mark()
        try:
            expr = self.parse_expr()
            if self.match('ASSIGN'):
                val = self.parse_expr()
                self.expect('SEP', values=[';'])
                return {"type": "Assign", "target": expr, "val": val}
            else:
                self.expect('SEP', values=[';'])
                return {"type": "ExprStmt", "expr": expr}
        except SyntaxError as e:
            self.lexer.reset(mark)
            raise SyntaxError(f"解析表达式或赋值语句时出错: {e}")

    def parse_block_or_expr(self):
        if self.peek().type == 'DELIM' and self.peek().value == '{':
            return self.parse_block()
        else:
            return self.parse_expr()

    def parse_expr(self):
        return self.parse_if_expr()

    def parse_if_expr(self):
        if self.peek().type == 'IF':
            self.match('IF')
            cond = self.parse_expr()
            then_block = self.parse_block_or_expr()
            self.expect('ELSE')
            else_block = self.parse_block_or_expr()
            return {"type": "IfExpr", "cond": cond, "then": then_block, "else": else_block}
        return self.parse_loop_expr()

    def parse_loop_expr(self):
        if self.peek().type == 'LOOP':
            self.match('LOOP')
            block = self.parse_block_or_expr()
            return {"type": "LoopExpr", "body": block}
        return self.parse_cmp_expr()

    def parse_cmp_expr(self):
        left = self.parse_add_expr()
        while self.peek().type == 'OP' and self.peek().value in ['==', '!=', '<', '>', '<=', '>=']:
            op = self.match('OP').value
            right = self.parse_add_expr()
            left = {"type": "BinaryOp", "op": op, "left": left, "right": right}
        return left

    def parse_add_expr(self):
        left = self.parse_mul_expr()
        while self.peek().type == 'OP' and self.peek().value in ['+', '-']:
            op = self.match('OP').value
            right = self.parse_mul_expr()
            left = {"type": "BinaryOp", "op": op, "left": left, "right": right}
        return left

    def parse_mul_expr(self):
        left = self.parse_unary_expr()
        while self.peek().type == 'OP' and self.peek().value in ['*', '/']:
            op = self.match('OP').value
            right = self.parse_unary_expr()
            left = {"type": "BinaryOp", "op": op, "left": left, "right": right}
        return left

    def parse_unary_expr(self):
        if self.match('OP', values=['-']):
            expr = self.parse_unary_expr()
            return {'type': 'UnaryOp', 'op': '-', 'expr': expr}
        elif self.match('OP', values=['*']):
            expr = self.parse_unary_expr()
            return {'type': 'Deref', 'expr': expr}
        elif self.match('ANDMUT'):
            expr = self.parse_unary_expr()
            return {'type': 'AddrOfMut', 'expr': expr}
        elif self.match('AND'):
            expr = self.parse_unary_expr()
            return {'type': 'AddrOf', 'expr': expr}
        else:
            return self.parse_postfix_expr()

    def parse_postfix_expr(self):
        expr = self.parse_primary()
        while True:
            if self.peek().type == 'DELIM' and self.peek().value == '(':
                self.match('DELIM', values=['('])
                args = []
                if not (self.peek().type == 'DELIM' and self.peek().value == ')'):
                    while True:
                        args.append(self.parse_expr())
                        if self.match('SEP', values=[',']):
                            continue
                        break
                self.expect('DELIM', values=[')'])
                expr = {'type': 'Call', 'func': expr, 'args': args}
            elif self.peek().type == 'DELIM' and self.peek().value == '[':
                self.match('DELIM', values=['['])
                index = self.parse_expr()
                self.expect('DELIM', values=[']'])
                expr = {'type': 'Index', 'array': expr, 'index': index}
            elif self.peek().type == 'DOT' and self.peek(1).type == 'NUMBER':
                self.match('DOT')
                num = self.expect('NUMBER')
                expr = {'type': 'TupleGet', 'tuple': expr, 'index': int(num.value)}
            else:
                break
        return expr

    def parse_primary(self):
        tok = self.peek()
        if tok.type == 'NUMBER':
            self.match('NUMBER')
            return {'type': 'Number', 'value': int(tok.value)}
        elif tok.type == 'ID':
            self.match('ID')
            return {'type': 'Variable', 'name': tok.value}
        elif tok.type == 'DELIM' and tok.value == '(':
            self.match('DELIM', values=['('])
            exprs = []
            if self.peek().type == 'DELIM' and self.peek().value == ')':
                self.match('DELIM', values=[')'])
                return {'type': 'Tuple', 'elems': []}
            while True:
                exprs.append(self.parse_expr())
                if self.match('SEP', values=[',']):
                    continue
                break
            self.expect('DELIM', values=[')'])
            if len(exprs) == 1:
                return exprs[0]
            else:
                return {'type': 'Tuple', 'elems': exprs}
        elif tok.type == 'DELIM' and tok.value == '{':
            return self.parse_block()
        elif tok.type == 'DELIM' and tok.value == '[':
            self.match('DELIM', values=['['])
            elems = []

            # 处理空数组情况
            if self.peek().type == 'DELIM' and self.peek().value == ']':
                self.match('DELIM', values=[']'])
                return {'type': 'Array', 'elems': []}

            # 处理非空数组
            try:
                while True:
                    elem = self.parse_expr()
                    elems.append(elem)
                    if not self.match('SEP', values=[',']):
                        break
                    # 处理尾部逗号情况
                    if self.peek().type == 'DELIM' and self.peek().value == ']':
                        break
            except SyntaxError as e:
                raise SyntaxError(f"解析数组元素时出错: {e}")

            self.expect('DELIM', values=[']'])
            return {'type': 'Array', 'elems': elems}
        else:
            raise SyntaxError(f"未知表达式: {tok}")