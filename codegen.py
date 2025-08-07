class CodeGen:
    def __init__(self, ir):
        self.ir = ir
        self.asm = []
        self.var_set = set()
        self.temp_set = set()
        self.label_set = set()
        self.funcs = set()
        self.data_section = []
        self.text_section = []

    def collect_symbols(self):
        for quad in self.ir:
            op = quad['op']
            for v in [quad.get('arg1'), quad.get('arg2'), quad.get('res')]:
                if isinstance(v, str) and v:
                    if v.startswith('t'):
                        self.temp_set.add(v)
                    elif v.isidentifier() and not v.startswith('L'):
                        self.var_set.add(v)
            if op == 'LABEL':
                self.label_set.add(quad['arg1'])
            if op == 'FUNC':
                self.funcs.add(quad['arg1'])

    def gen(self):
        self.collect_symbols()
        self.data_section.append('section .data')
        for v in self.var_set:
            self.data_section.append(f'{v} dd 0')
        for t in self.temp_set:
            self.data_section.append(f'{t} dd 0')
        self.text_section.append('section .text')
        self.text_section.append('global _start')
        self.text_section.append('_start:')

        for quad in self.ir:
            op = quad['op']
            a1 = quad.get('arg1')
            a2 = quad.get('arg2')
            res = quad.get('res')
            # 变量赋值
            if op == '=':
                self.text_section.append(f'    mov eax, [{a2}]' if a2 in self.var_set or a2 in self.temp_set else f'    mov eax, {a2}')
                self.text_section.append(f'    mov [{a1}], eax')
            # 四则运算
            elif op == '+':
                self.text_section.append(f'    mov eax, [{a1}]')
                self.text_section.append(f'    add eax, [{a2}]')
                self.text_section.append(f'    mov [{res}], eax')
            elif op == '-':
                self.text_section.append(f'    mov eax, [{a1}]')
                self.text_section.append(f'    sub eax, [{a2}]')
                self.text_section.append(f'    mov [{res}], eax')
            elif op == '*':
                self.text_section.append(f'    mov eax, [{a1}]')
                self.text_section.append(f'    imul eax, [{a2}]')
                self.text_section.append(f'    mov [{res}], eax')
            elif op == '/':
                self.text_section.append(f'    mov eax, [{a1}]')
                self.text_section.append('    cdq')
                self.text_section.append(f'    idiv dword [{a2}]')
                self.text_section.append(f'    mov [{res}], eax')
            # 比较
            elif op in ('==', '!=', '<', '>', '<=', '>='):
                self.text_section.append(f'    mov eax, [{a1}]')
                self.text_section.append(f'    cmp eax, [{a2}]')
                set_instr = {
                    '==': 'sete',
                    '!=': 'setne',
                    '<': 'setl',
                    '>': 'setg',
                    '<=': 'setle',
                    '>=': 'setge'
                }[op]
                self.text_section.append(f'    {set_instr} al')
                self.text_section.append(f'    movzx eax, al')
                self.text_section.append(f'    mov [{res}], eax')
            # 一元负号
            elif op == '-u':
                self.text_section.append(f'    mov eax, [{a1}]')
                self.text_section.append(f'    neg eax')
                self.text_section.append(f'    mov [{res}], eax')
            # 取地址/解引用
            elif op == 'ADDR':
                # 这里只做演示，实际需要指针支持
                self.text_section.append(f'    lea eax, [{a1}]')
                self.text_section.append(f'    mov [{res}], eax')
            elif op == 'LOAD':
                self.text_section.append(f'    mov eax, [{a1}]')
                self.text_section.append(f'    mov eax, [eax]')
                self.text_section.append(f'    mov [{res}], eax')
            elif op == 'PSTORE':
                self.text_section.append(f'    mov eax, [{a2}]')
                self.text_section.append(f'    mov ebx, [{a1}]')
                self.text_section.append(f'    mov [ebx], eax')
            # 数组/元组
            elif op == 'ALOAD':
                # 假设每元素4字节
                self.text_section.append(f'    mov ebx, [{a1}]')
                self.text_section.append(f'    mov ecx, [{a2}]')
                self.text_section.append(f'    mov eax, [ebx + ecx*4]')
                self.text_section.append(f'    mov [{res}], eax')
            elif op == 'ASTORE':
                self.text_section.append(f'    mov ebx, [{a1}]')
                self.text_section.append(f'    mov ecx, [{a2}]')
                self.text_section.append(f'    mov eax, [{res}]')
                self.text_section.append(f'    mov [ebx + ecx*4], eax')
            # 跳转与标签
            elif op == 'LABEL':
                self.text_section.append(f'{a1}:')
            elif op == 'GOTO':
                self.text_section.append(f'    jmp {a1}')
            elif op == 'IFZ':
                self.text_section.append(f'    mov eax, [{a1}]')
                self.text_section.append(f'    cmp eax, 0')
                self.text_section.append(f'    je {res}')
            elif op == 'IFNZ':
                self.text_section.append(f'    mov eax, [{a1}]')
                self.text_section.append(f'    cmp eax, 0')
                self.text_section.append(f'    jne {res}')
            # 函数
            elif op == 'FUNC':
                self.text_section.append(f'{a1}:')
            elif op == 'ENDFUNC':
                self.text_section.append(f'    ret')
            elif op == 'CALL':
                # 只支持无参数调用
                self.text_section.append(f'    call {a1}')
                self.text_section.append(f'    mov [{res}], eax')
            elif op == 'RET':
                if a1:
                    self.text_section.append(f'    mov eax, [{a1}]')
                self.text_section.append(f'    ret')
            # 变量声明
            elif op == 'LET':
                pass  # 已在data段声明
            # 参数
            elif op == 'PARAM':
                pass  # 简化处理
        self.text_section.append('    mov eax, 1')
        self.text_section.append('    int 0x80')
        return '\n'.join(self.data_section + self.text_section)