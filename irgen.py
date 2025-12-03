# irgen.py - Optimized version

import itertools

class IRGen:
    def __init__(self):
        self.temp_count = itertools.count()
        self.label_count = itertools.count()
        self.quadruples = []
        self.loop_stack = []  # Stack of (start_label, end_label) for loop control
        self.current_function = None

    def new_temp(self):
        return f"t{next(self.temp_count)}"

    def new_label(self):
        return f"L{next(self.label_count)}"

    def emit(self, op, arg1='', arg2='', res=''):
        self.quadruples.append({
            'op': op,
            'arg1': arg1,
            'arg2': arg2,
            'res': res
        })

    def gen(self, ast):
        if not ast or ast.get('type') != 'Program':
            return []
        self.quadruples = []
        for decl in ast.get('decls', []):
            self.gen_function(decl)
        self.optimize_ir()  # Apply optimizations to the IR
        return self.quadruples

    def gen_function(self, func):
        self.current_function = func['name']
        self.emit('FUNC', func['name'], '', '')
        
        # Process parameters
        for i, param in enumerate(func.get('params', [])):
            self.emit('PARAM', param['name'], 'i32', str(i))  # Assuming i32 for simplicity
        
        # Generate function body
        self.gen_block(func['body'])
        
        # Ensure there's a return at the end if not already present
        if not self.quadruples or self.quadruples[-1]['op'] != 'RET':
            self.emit('RET', '', '', '')
            
        self.emit('ENDFUNC', func['name'], '', '')
        self.current_function = None

    def gen_block(self, block):
        for stmt in block.get('stmts', []):
            self.gen_stmt(stmt)

    def gen_stmt(self, stmt):
        t = stmt['type']
        
        if t == 'Let':
            self.gen_let(stmt)
        elif t == 'Assign':
            self.gen_assign(stmt)
        elif t == 'Return':
            self.gen_return(stmt)
        elif t == 'If':
            self.gen_if_stmt(stmt)
        elif t == 'While':
            self.gen_while_stmt(stmt)
        elif t == 'For':
            self.gen_for_stmt(stmt)
        elif t == 'Loop':
            self.gen_loop_stmt(stmt)
        elif t == 'Break':
            self.gen_break_stmt(stmt)
        elif t == 'Continue':
            self.gen_continue_stmt(stmt)
        elif t == 'ExprStmt':
            self.gen_expr(stmt['expr'])
        elif t == 'Block':
            self.gen_block(stmt)
        elif t == 'Empty':
            pass  # Nothing to emit for empty statement
    
    def gen_let(self, stmt):
        if stmt['val'] is not None:
            res = self.gen_expr(stmt['val'])
            self.emit('LET', stmt['name'], res, '')
        else:
            self.emit('LET', stmt['name'], '', '')
    
    def gen_assign(self, stmt):
        target = stmt['target']
        value = self.gen_expr(stmt['val'])
        
        # Handle different assignment targets
        if target['type'] == 'Variable':
            self.emit('=', target['name'], value, '')
        elif target['type'] == 'Index':
            # Array index assignment: a[i] = value
            array = self.gen_expr(target['array'])
            index = self.gen_expr(target['index'])
            self.emit('ASTORE', array, index, value)
        elif target['type'] == 'TupleGet':
            # Tuple member assignment: a.0 = value
            tuple_expr = self.gen_expr(target['tuple'])
            index = str(target['index'])
            self.emit('TSTORE', tuple_expr, index, value)
        elif target['type'] == 'Deref':
            # Dereference assignment: *ptr = value
            ptr = self.gen_expr(target['expr'])
            self.emit('PSTORE', ptr, value, '')
    
    def gen_return(self, stmt):
        if stmt['expr'] is not None:
            res = self.gen_expr(stmt['expr'])
            self.emit('RET', res, '', '')
        else:
            self.emit('RET', '', '', '')
    
    def gen_if_stmt(self, stmt):
        cond = self.gen_expr(stmt['cond'])
        label_else = self.new_label()
        label_end = self.new_label()
        
        self.emit('IFZ', cond, '', label_else)
        self.gen_block_or_expr(stmt['then'])
        
        if stmt['else']:
            self.emit('GOTO', label_end, '', '')
            self.emit('LABEL', label_else, '', '')
            self.gen_block_or_expr(stmt['else'])
            self.emit('LABEL', label_end, '', '')
        else:
            self.emit('LABEL', label_else, '', '')
    
    def gen_while_stmt(self, stmt):
        label_start = self.new_label()
        label_cond = self.new_label()
        label_end = self.new_label()
        
        # Push loop context for break/continue
        self.loop_stack.append((label_cond, label_end))
        
        self.emit('GOTO', label_cond, '', '')
        self.emit('LABEL', label_start, '', '')
        self.gen_block_or_expr(stmt['body'])
        
        self.emit('LABEL', label_cond, '', '')
        cond = self.gen_expr(stmt['cond'])
        self.emit('IFNZ', cond, '', label_start)
        
        self.emit('LABEL', label_end, '', '')
        
        # Pop loop context
        self.loop_stack.pop()
    
    def gen_for_stmt(self, stmt):
        iter_var = stmt['iter']['name']
        mut = stmt['iter']['mut']
        iter_expr = stmt['iter']['iter']
        
        # Setup for range-based for loop
        if isinstance(iter_expr, dict) and 'range' in iter_expr:
            start = self.gen_expr(iter_expr['range'][0])
            end = self.gen_expr(iter_expr['range'][1])
            
            label_cond = self.new_label()
            label_body = self.new_label()
            label_end = self.new_label()
            
            # Initialize loop variable
            self.emit('=', iter_var, start, '')
            
            # Push loop context
            self.loop_stack.append((label_cond, label_end))
            
            self.emit('GOTO', label_cond, '', '')
            
            # Loop body label
            self.emit('LABEL', label_body, '', '')
            self.gen_block_or_expr(stmt['body'])
            
            # Increment loop variable
            self.emit('+', iter_var, '1', iter_var)
            
            # Condition check
            self.emit('LABEL', label_cond, '', '')
            cond_temp = self.new_temp()
            self.emit('<', iter_var, end, cond_temp)
            self.emit('IFNZ', cond_temp, '', label_body)
            
            self.emit('LABEL', label_end, '', '')
            
            # Pop loop context
            self.loop_stack.pop()
        else:
            # Handle other iterable types (future extension)
            pass
    
    def gen_loop_stmt(self, stmt):
        label_start = self.new_label()
        label_end = self.new_label()
        
        # Push loop context
        self.loop_stack.append((label_start, label_end))
        
        self.emit('LABEL', label_start, '', '')
        self.gen_block_or_expr(stmt['body'])
        self.emit('GOTO', label_start, '', '')
        self.emit('LABEL', label_end, '', '')
        
        # Pop loop context
        self.loop_stack.pop()
    
    def gen_break_stmt(self, stmt):
        if not self.loop_stack:
            raise ValueError("Break statement outside of loop")
        
        _, end_label = self.loop_stack[-1]
        
        if stmt['expr'] is not None:
            # Handle break with value (for returning from a loop)
            res = self.gen_expr(stmt['expr'])
            break_result = f"break_result_{self.current_function}"
            self.emit('=', break_result, res, '')
        
        self.emit('GOTO', end_label, '', '')
    
    def gen_continue_stmt(self, stmt):
        if not self.loop_stack:
            raise ValueError("Continue statement outside of loop")
        
        start_label, _ = self.loop_stack[-1]
        self.emit('GOTO', start_label, '', '')

    def gen_block_or_expr(self, node):
        if node and node.get('type') == 'Block':
            self.gen_block(node)
        else:
            self.gen_expr(node)

    def gen_expr(self, expr):
        if not expr:
            return ''
            
        t = expr.get('type', '')
        
        if t == 'Number':
            return str(expr['value'])
        elif t == 'Variable':
            return expr['name']
        elif t == 'BinaryOp':
            left = self.gen_expr(expr['left'])
            right = self.gen_expr(expr['right'])
            tmp = self.new_temp()
            self.emit(expr['op'], left, right, tmp)
            return tmp
        elif t == 'UnaryOp':
            val = self.gen_expr(expr['expr'])
            tmp = self.new_temp()
            self.emit(expr['op'], val, '', tmp)
            return tmp
        elif t == 'Deref':
            # Handle dereference operation (*ptr)
            ptr = self.gen_expr(expr['expr'])
            tmp = self.new_temp()
            self.emit('LOAD', ptr, '', tmp)
            return tmp
        elif t == 'AddrOf' or t == 'AddrOfMut':
            # Handle address-of operations (&x or &mut x)
            target = expr['expr']
            if target['type'] != 'Variable':
                raise ValueError("Can only take address of variables")
            tmp = self.new_temp()
            self.emit('ADDR', target['name'], '', tmp)
            return tmp
        elif t == 'Call':
            # Process function call
            args = []
            for i, arg in enumerate(expr.get('args', [])):
                arg_val = self.gen_expr(arg)
                self.emit('ARG', arg_val, '', str(i))
                args.append(arg_val)
                
            tmp = self.new_temp()
            func_name = ''
            if expr['func']['type'] == 'Variable':
                func_name = expr['func']['name']
            else:
                func_name = self.gen_expr(expr['func'])
                
            self.emit('CALL', func_name, str(len(args)), tmp)
            return tmp
        elif t == 'Index':
            # Handle array indexing (a[i])
            array = self.gen_expr(expr['array'])
            index = self.gen_expr(expr['index'])
            tmp = self.new_temp()
            self.emit('ALOAD', array, index, tmp)
            return tmp
        elif t == 'TupleGet':
            # Handle tuple member access (t.0)
            tuple_var = self.gen_expr(expr['tuple'])
            index = str(expr['index'])
            tmp = self.new_temp()
            self.emit('TLOAD', tuple_var, index, tmp)
            return tmp
        elif t == 'Tuple':
            # Handle tuple creation
            elems = []
            for e in expr.get('elems', []):
                elems.append(self.gen_expr(e))
                
            tmp = self.new_temp()
            self.emit('TUPLE', str(len(elems)), ','.join(elems), tmp)
            return tmp
        elif t == 'Array':
            # Handle array creation
            elems = []
            for e in expr.get('elems', []):
                elems.append(self.gen_expr(e))
                
            tmp = self.new_temp()
            self.emit('ARRAY', str(len(elems)), ','.join(elems), tmp)
            return tmp
        elif t == 'IfExpr':
            # Handle if expression (if cond { then } else { else })
            cond = self.gen_expr(expr['cond'])
            label_else = self.new_label()
            label_end = self.new_label()
            result = self.new_temp()
            
            self.emit('IFZ', cond, '', label_else)
            then_result = self.gen_expr(expr['then'])
            self.emit('=', result, then_result, '')
            self.emit('GOTO', label_end, '', '')
            
            self.emit('LABEL', label_else, '', '')
            else_result = self.gen_expr(expr['else'])
            self.emit('=', result, else_result, '')
            
            self.emit('LABEL', label_end, '', '')
            return result
        elif t == 'LoopExpr':
            # Handle loop expression with break value
            label_start = self.new_label()
            label_end = self.new_label()
            result = self.new_temp()
            
            # Create a special variable to hold potential break values
            break_result = f"break_result_{self.current_function}"
            self.emit('LET', break_result, '', '')
            
            # Push loop context
            self.loop_stack.append((label_start, label_end))
            
            self.emit('LABEL', label_start, '', '')
            self.gen_block_or_expr(expr['body'])
            self.emit('GOTO', label_start, '', '')
            
            self.emit('LABEL', label_end, '', '')
            self.emit('=', result, break_result, '')
            
            # Pop loop context
            self.loop_stack.pop()
            
            return result
        elif t == 'Block':
            # Handle block expression
            result = None
            for i, stmt in enumerate(expr.get('stmts', [])):
                if i == len(expr['stmts']) - 1 and stmt['type'] == 'ExprStmt' and stmt.get('tail', False):
                    # Last expression becomes the result
                    result = self.gen_expr(stmt['expr'])
                else:
                    self.gen_stmt(stmt)
            
            if result is None:
                # Empty block or no tail expression
                result = ''
                
            return result
            
        # Default fallback
        return ''

    def optimize_ir(self):
        """Apply basic optimizations to the IR"""
        self.remove_dead_code()
        self.constant_folding()
        self.copy_propagation()
        self.remove_unused_labels()

    def remove_dead_code(self):
        """Remove unreachable code segments"""
        # Implement dead code elimination
        pass

    def constant_folding(self):
        """Evaluate constant expressions at compile time"""
        # Implement constant folding
        pass

    def copy_propagation(self):
        """Replace variables with their values when possible"""
        # Implement copy propagation
        pass

    def remove_unused_labels(self):
        """Remove labels that are never jumped to"""
        used_labels = set()
        
        # Find all used labels
        for quad in self.quadruples:
            if quad['op'] in ('GOTO', 'IFZ', 'IFNZ') and quad['arg1']:
                used_labels.add(quad['arg1'])
            elif quad['op'] in ('IFZ', 'IFNZ') and quad['res']:
                used_labels.add(quad['res'])
        
        # Remove unused labels
        i = 0
        while i < len(self.quadruples):
            quad = self.quadruples[i]
            if quad['op'] == 'LABEL' and quad['arg1'] not in used_labels:
                self.quadruples.pop(i)
            else:
                i += 1