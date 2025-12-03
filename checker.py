# checker.py

class Symbol:
    def __init__(self, name, typ=None, mut=False, inited=False):
        self.name = name
        self.typ = typ
        self.mut = mut
        self.inited = inited  # 是否已初始化
        self.refs = []  # 记录所有指向此变量的引用

class Checker:
    def __init__(self, ast):
        self.ast = ast
        self.scopes = [{}]         # 作用域链，每层是字典 name->Symbol
        self.functions = {}        # 函数名->(参数类型,返回类型)
        self.in_loop = 0           # 当前是否在循环体内

    def check(self):
        if not self.ast or self.ast.get('type') != 'Program':
            return
        for decl in self.ast.get('decls', []):
            if decl['type'] == 'Function':
                self.register_function(decl)
        for decl in self.ast.get('decls', []):
            if decl['type'] == 'Function':
                self.check_function(decl)

    def register_function(self, func):
        params = [(p['name'], self.type_of(p['type'])) for p in func['params']]
        ret_type = self.type_of(func['ret_type']) if func['ret_type'] else None
        self.functions[func['name']] = (params, ret_type)

    def check_function(self, func):
        self.scopes.append({})
        for p in func['params']:
            # 函数参数必须有类型
            typ = self.type_of(p['type'])
            if typ is None:
                raise SyntaxError(f"函数参数{p['name']}必须显式声明类型")
            self.define_var(p['name'], typ, mut=p['mut'], inited=True)
        self.check_block(func['body'], func.get('ret_type'), func['name'])
        self.scopes.pop()

    def check_block(self, block, ret_type, func_name):
        self.scopes.append({})
        for stmt in block['stmts']:
            self.check_stmt(stmt, ret_type, func_name)
        # 检查本作用域所有变量类型是否都已推断
        for name, var in self.scopes[-1].items():
            if var.typ is None:
                raise SyntaxError(f"变量{name}类型无法推导")
        self.scopes.pop()

    def check_stmt(self, stmt, ret_type, func_name):
        t = stmt['type']
        if t == 'Let':
            self.check_let(stmt)
        elif t == 'Assign':
            self.check_assign(stmt)
        elif t == 'Return':
            self.check_return(stmt, ret_type, func_name)
        elif t == 'Break' or t == 'Continue':
            if self.in_loop <= 0:
                raise SyntaxError(f"{t.lower()}必须出现在循环体内")
        elif t == 'While' or t == 'Loop':
            self.in_loop += 1
            if t == 'While':
                self.check_expr(stmt['cond'])
            self.check_block_or_expr(stmt['body'], ret_type, func_name)
            self.in_loop -= 1
        elif t == 'For':
            self.in_loop += 1
            self.check_for(stmt, ret_type, func_name)
            self.in_loop -= 1
        elif t == 'ExprStmt':
            self.check_expr(stmt['expr'])
        elif t == 'If':
            self.check_if(stmt, ret_type, func_name)
        elif t == 'Block':
            self.check_block(stmt, ret_type, func_name)
        # ...如有更多语句类型，继续扩展...

    def check_let(self, stmt):
        name = stmt['name']
        declared_type = self.type_of(stmt['ty']) if stmt['ty'] else None
        if stmt['val']:
            expr_type = self.check_expr(stmt['val'])
            if declared_type and not self.types_equal(expr_type, declared_type):
                raise SyntaxError(f"变量{name}声明为{declared_type}，初始化类型为{expr_type}，类型不一致")
            typ = declared_type if declared_type else expr_type
            self.define_var(name, typ, mut=stmt['mut'], inited=True)
        else:
            # 没初值，允许声明为待推断类型，未初始化
            self.define_var(name, declared_type, mut=stmt['mut'], inited=False)

    def check_assign(self, stmt):
        target = stmt['target']
        
        # 处理元组成员访问赋值 (a.0 = value)
        if target['type'] == 'TupleGet':
            tuple_expr = target['tuple']
            if tuple_expr['type'] != 'Variable':
                raise SyntaxError(f"只支持对变量元组成员赋值")
                
            var = self.resolve_var(tuple_expr['name'])
            if not var:
                raise SyntaxError(f"变量{tuple_expr['name']}未声明")
                
            if not var.mut:
                raise SyntaxError(f"变量{tuple_expr['name']}为不可变变量，其成员不能赋值")
                
            # 检查元组类型
            if not (isinstance(var.typ, dict) and 'tuple' in var.typ):
                raise SyntaxError(f"变量{tuple_expr['name']}不是元组类型")
                
            # 检查索引是否有效
            idx = target['index']
            if idx < 0 or idx >= len(var.typ['tuple']):
                raise SyntaxError(f"元组索引{idx}超出范围[0,{len(var.typ['tuple'])-1}]")
                
            # 检查赋值类型匹配
            member_type = var.typ['tuple'][idx]
            val_type = self.check_expr(stmt['val'])
            
            if not self.types_equal(val_type, member_type):
                raise SyntaxError(f"元组{tuple_expr['name']}的第{idx}个成员类型为{member_type}，赋值类型为{val_type}，类型不一致")
                
            return
        
        # 处理变量赋值
        if target['type'] == 'Variable':
            var = self.resolve_var(target['name'])
            if not var:
                raise SyntaxError(f"变量{target['name']}未声明")
            
            # 对于元组类型的整体赋值，我们需要检查是否初始化过
            # 即使变量不可变，如果未初始化，也允许首次赋值
            if not var.mut and var.inited:
                raise SyntaxError(f"变量{target['name']}为不可变变量，不能赋值")
                
            val_type = self.check_expr(stmt['val'])
            if var.typ is None:
                var.typ = val_type  # 类型推断
            elif not self.types_equal(val_type, var.typ):
                raise SyntaxError(f"变量{target['name']}类型为{var.typ}，赋值类型为{val_type}，类型不一致")
            var.inited = True  # 赋值即已初始化
            
        # 处理数组索引赋值
        elif target['type'] == 'Index':
            array = target['array']
            if array['type'] != 'Variable':
                raise SyntaxError(f"只支持对变量数组元素赋值")
            
            var = self.resolve_var(array['name'])
            if not var:
                raise SyntaxError(f"变量{array['name']}未声明")
            if not var.mut:
                raise SyntaxError(f"变量{array['name']}为不可变变量，其元素不能赋值")
            
            # 检查索引是否为整数类型
            idx_type = self.check_expr(target['index'])
            if not self.types_equal(idx_type, 'i32'):
                raise SyntaxError(f"数组索引必须为i32类型，实际为{idx_type}")
            
            # 检查数组类型和赋值类型匹配
            if not isinstance(var.typ, dict) or 'array' not in var.typ:
                raise SyntaxError(f"变量{array['name']}不是数组类型，不能通过索引赋值")
            
            # 检查索引是否越界（只针对常量索引和已知大小的数组）
            self.check_index_bounds(target['index'], var.typ)
            
            element_type = var.typ['array']
            val_type = self.check_expr(stmt['val'])
            
            if not self.types_equal(val_type, element_type):
                raise SyntaxError(f"数组{array['name']}元素类型为{element_type}，赋值类型为{val_type}，类型不一致")
        else:
            raise SyntaxError(f"赋值左值必须是变量、数组索引或元组成员")

    def check_return(self, stmt, ret_type, func_name):
        expr = stmt['expr']
        expect_type = self.type_of(ret_type) if ret_type else None
        if expect_type:
            if expr is None:
                raise SyntaxError(f"函数{func_name}声明返回类型为{expect_type}，但return无值")
            actual_type = self.check_expr(expr)
            if not self.types_equal(actual_type, expect_type):
                raise SyntaxError(f"函数{func_name}声明返回类型为{expect_type}，但return类型为{actual_type}，类型不一致")
        else:
            if expr is not None:
                actual_type = self.check_expr(expr)
                raise SyntaxError(f"函数{func_name}未声明返回值，但return有值（类型为{actual_type}）")

    def check_for(self, stmt, ret_type, func_name):
        iter_var = stmt['iter']['name']
        mut = stmt['iter']['mut']
        self.scopes.append({})
        self.define_var(iter_var, 'i32', mut=mut, inited=True)
        self.check_expr(stmt['iter']['iter'])
        self.check_block_or_expr(stmt['body'], ret_type, func_name)
        self.scopes.pop()

    def check_if(self, stmt, ret_type, func_name):
        self.check_expr(stmt['cond'])
        self.check_block_or_expr(stmt['then'], ret_type, func_name)
        if stmt.get('else'):
            self.check_block_or_expr(stmt['else'], ret_type, func_name)

    def check_block_or_expr(self, node, ret_type, func_name):
        if node.get('type') == 'Block':
            self.check_block(node, ret_type, func_name)
        else:
            self.check_expr(node)

    def check_expr(self, expr):
        t = expr['type']
        if t == 'Number':
            return 'i32'
        elif t == 'Variable':
            var = self.resolve_var(expr['name'])
            if not var:
                raise SyntaxError(f"变量{expr['name']}未声明")
            if var.typ is None:
                raise SyntaxError(f"变量{expr['name']}类型无法推导")
            if not var.inited:
                raise SyntaxError(f"变量{expr['name']}未初始化")
            return var.typ
        elif t == 'BinaryOp':
            lt = self.check_expr(expr['left'])
            rt = self.check_expr(expr['right'])
            if not self.types_equal(lt, rt):
                raise SyntaxError(f"二元操作数类型不一致：{lt} vs {rt}")
            return lt
        elif t == 'UnaryOp':
            val_type = self.check_expr(expr['expr'])
            if expr['op'] == '-' and not self.types_equal(val_type, 'i32'):
                raise SyntaxError(f"一元负号操作数必须为i32")
            return val_type
        elif t == 'AddrOf':
            # 处理不可变引用 &expr
            inner_expr = expr['expr']
            # 只能引用变量
            if inner_expr['type'] != 'Variable':
                raise SyntaxError("只能引用变量")
                
            target_var = self.resolve_var(inner_expr['name'])
            if not target_var:
                raise SyntaxError(f"变量{inner_expr['name']}未声明")
                
            # 检查引用冲突
            if any(ref_type == 'mut' for ref_type in target_var.refs):
                raise SyntaxError(f"不能创建对{inner_expr['name']}的不可变引用，因为已存在可变引用")
                
            # 记录引用
            target_var.refs.append('imm')
                
            inner_type = self.check_expr(inner_expr)
            return {'ref': 'imm', 'to': inner_type}
        elif t == 'AddrOfMut':
            # 处理可变引用 &mut expr
            inner_expr = expr['expr']
            # 只能引用变量
            if inner_expr['type'] != 'Variable':
                raise SyntaxError("只能引用变量")
                
            target_var = self.resolve_var(inner_expr['name'])
            if not target_var:
                raise SyntaxError(f"变量{inner_expr['name']}未声明")
                
            # 检查目标变量是否可变
            if not target_var.mut:
                raise SyntaxError(f"只能从可变变量创建可变引用，{inner_expr['name']}不是可变变量")
                
            # 检查引用冲突
            if target_var.refs:
                raise SyntaxError(f"不能创建对{inner_expr['name']}的可变引用，因为已存在其他引用")
                
            # 记录引用
            target_var.refs.append('mut')
                
            inner_type = self.check_expr(inner_expr)
            return {'ref': 'mut', 'to': inner_type}
        elif t == 'Deref':
            inner_type = self.check_expr(expr['expr'])
            if not (isinstance(inner_type, dict) and 'ref' in inner_type and 'to' in inner_type):
                raise SyntaxError("解引用操作符 * 只能用于引用类型")
            return inner_type['to']
        elif t == 'Call':
            func = expr['func']
            if func['type'] == 'Variable':
                fname = func['name']
                if fname not in self.functions:
                    raise SyntaxError(f"函数{fname}未声明")
                params, ret_type = self.functions[fname]
                if len(expr['args']) != len(params):
                    raise SyntaxError(f"函数{fname}参数数量不符")
                for i, (arg, (pname, ptype)) in enumerate(zip(expr['args'], params)):
                    arg_type = self.check_expr(arg)
                    if not self.types_equal(arg_type, ptype):
                        raise SyntaxError(f"函数{fname}第{i+1}个参数类型期望{ptype}，实际{arg_type}")
                return ret_type
            else:
                raise SyntaxError("不支持的函数调用方式")
        elif t == 'Index':
            arr_type = self.check_expr(expr['array'])
            idx_type = self.check_expr(expr['index'])
            if not self.types_equal(idx_type, 'i32'):
                raise SyntaxError("数组或元组索引类型必须为i32")
                
            # 检查索引是否越界
            self.check_index_bounds(expr['index'], arr_type)
                
            if isinstance(arr_type, dict) and arr_type.get('array'):
                return arr_type['array']
            if isinstance(arr_type, dict) and arr_type.get('tuple'):
                idx = expr['index']
                if idx['type'] == 'Number':
                    idx_val = idx['value']
                    tuple_types = arr_type['tuple']
                    if idx_val >= len(tuple_types):
                        raise SyntaxError("元组索引越界")
                    return tuple_types[idx_val]
            raise SyntaxError(f"类型{arr_type}不支持索引操作")
        elif t == 'TupleGet':
            # 处理元组成员访问 a.0
            tuple_type = self.check_expr(expr['tuple'])
            if not (isinstance(tuple_type, dict) and 'tuple' in tuple_type):
                raise SyntaxError("只能对元组类型使用.索引访问")
                
            idx = expr['index']
            if idx < 0 or idx >= len(tuple_type['tuple']):
                raise SyntaxError(f"元组索引{idx}超出范围[0,{len(tuple_type['tuple'])-1}]")
                
            return tuple_type['tuple'][idx]
        elif t == 'Array':
            elem_types = [self.check_expr(e) for e in expr['elems']]
            if not elem_types:
                raise SyntaxError("数组不能为空")
            first_type = elem_types[0]
            for ty in elem_types:
                if not self.types_equal(ty, first_type):
                    raise SyntaxError("数组元素类型不一致")
            return {'array': first_type, 'size': len(expr['elems'])}
        elif t == 'Tuple':
            elem_types = [self.check_expr(e) for e in expr['elems']]
            return {'tuple': elem_types}
        # ...可以继续补充引用、解引用、可变引用等
        return 'i32'  # 默认

    def check_index_bounds(self, index_expr, array_type):
        """检查数组索引是否越界（仅对常量索引和已知大小的数组）"""
        # 只有当索引是常量，且数组大小已知时才能静态检查
        if index_expr['type'] == 'Number' and isinstance(array_type, dict):
            idx_val = index_expr['value']
            
            # 处理数组类型
            if 'array' in array_type and 'size' in array_type:
                array_size = array_type['size']
                if idx_val < 0 or idx_val >= array_size:
                    raise SyntaxError(f"数组索引{idx_val}超出范围[0,{array_size-1}]")
            
            # 处理元组类型
            elif 'tuple' in array_type:
                tuple_size = len(array_type['tuple'])
                if idx_val < 0 or idx_val >= tuple_size:
                    raise SyntaxError(f"元组索引{idx_val}超出范围[0,{tuple_size-1}]")

    def define_var(self, name, typ=None, mut=False, inited=False):
        # 允许二次声明，直接覆盖当前作用域同名变量
        self.scopes[-1][name] = Symbol(name, typ, mut, inited)

    def resolve_var(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def type_of(self, typ):
        if not typ:
            return None
        if isinstance(typ, dict):
            if typ.get('id'):
                return typ['id']
            # 处理数组类型
            if 'array' in typ:
                elem_type = self.type_of(typ['array'])
                return {'array': elem_type, 'size': typ.get('size')}
            # 处理其他复合类型
            if 'ref' in typ:
                to_type = self.type_of(typ['to'])
                return {'ref': typ['ref'], 'to': to_type}
            if 'tuple' in typ:
                tuple_types = [self.type_of(t) for t in typ['tuple']]
                return {'tuple': tuple_types}
            # 返回原始类型
            return typ
        if isinstance(typ, str):
            return typ
        return str(typ)

    def types_equal(self, type1, type2):
        """检查两个类型是否等价"""
        # 直接相等的情况
        if type1 == type2:
            return True
            
        # 如果一个是字符串，一个是字典
        if isinstance(type1, str) and isinstance(type2, dict) and type2.get('id') == type1:
            return True
        if isinstance(type2, str) and isinstance(type1, dict) and type1.get('id') == type2:
            return True
            
        # 如果都是字典，检查内部结构
        if isinstance(type1, dict) and isinstance(type2, dict):
            # 数组类型比较
            if 'array' in type1 and 'array' in type2:
                if type1.get('size') != type2.get('size'):
                    return False
                return self.types_equal(type1['array'], type2['array'])
                
            # 引用类型比较
            if 'ref' in type1 and 'ref' in type2:
                if type1['ref'] != type2['ref']:
                    return False
                return self.types_equal(type1['to'], type2['to'])
                
            # 元组类型比较
            if 'tuple' in type1 and 'tuple' in type2:
                tuples1 = type1['tuple']
                tuples2 = type2['tuple']
                if len(tuples1) != len(tuples2):
                    return False
                return all(self.types_equal(t1, t2) for t1, t2 in zip(tuples1, tuples2))
                
        return False