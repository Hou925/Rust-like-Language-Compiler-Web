from flask import request, jsonify, render_template_string, Response
from tokenizer import Lexer  # 使用增量 Lexer（供词法可视化与错误时兜底）
from parser import Parser
from irgen import IRGen
from checker import Checker
from codegen import CodeGen  # 生成汇编

def index():
    return render_template_string(open("frontend.html", encoding="utf-8").read())

def _ir_to_text(ir):
    """与前端渲染一致的四元式文本格式"""
    if not ir or len(ir) == 0:
        return "（无中间代码）"
    lines = []
    for i, q in enumerate(ir):
        op = q.get('op', '') or '_'
        arg1 = q.get('arg1', '') or '_'
        arg2 = q.get('arg2', '') or '_'
        res = q.get('res', '') or '_'
        lines.append(f"[{i}] ({op}, {arg1}, {arg2}, {res})")
    return "\n".join(lines)

def analyze():
    code = request.json.get("code", "")
    parser = None
    ast = None
    ir = []
    asm = ""
    tokens = []

    try:
        # 一遍扫描：语法分析驱动词法分析
        parser = Parser(code)
        ast = parser.parse_program()

        # 语义检查
        checker = Checker(ast)
        checker.check()

        # IR 生成
        irgen = IRGen()
        ir = irgen.gen(ast)

        # 代码生成（汇编）
        codegen = CodeGen(ir)
        asm = codegen.gen()

        # 词法结果用于前端展示：将剩余 token 排空至 EOF
        parser.lexer.drain_to_eof()
        tokens = parser.lexer.get_tokens()

        return jsonify({"tokens": tokens, "ast": ast, "ir": ir, "asm": asm, "success": True})
    except SyntaxError as e:
        # 出错也尽量给出完整的词法结果
        if parser and hasattr(parser, 'lexer'):
            parser.lexer.drain_to_eof()
            tokens = parser.lexer.get_tokens()
        else:
            lex = Lexer(code)
            lex.drain_to_eof()
            tokens = lex.get_tokens()
        return jsonify({"success": False, "error": str(e), "tokens": tokens}), 400
    except Exception as e:
        if parser and hasattr(parser, 'lexer'):
            parser.lexer.drain_to_eof()
            tokens = parser.lexer.get_tokens()
        else:
            lex = Lexer(code)
            lex.drain_to_eof()
            tokens = lex.get_tokens()
        return jsonify({"success": False, "error": "其它错误：" + str(e), "tokens": tokens}), 400

def download_ir():
    """下载中间代码（四元式），作为文本文件"""
    data = request.get_json(silent=True) or {}
    code = data.get("code", "")
    try:
        parser = Parser(code)
        ast = parser.parse_program()
        checker = Checker(ast)
        checker.check()
        ir = IRGen().gen(ast)
        content = _ir_to_text(ir)
        return Response(
            content,
            mimetype="text/plain; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="ir.txt"'},
        )
    except SyntaxError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": "其它错误：" + str(e)}), 400

def download_asm():
    """下载目标代码（汇编），作为文本文件"""
    data = request.get_json(silent=True) or {}
    code = data.get("code", "")
    try:
        parser = Parser(code)
        ast = parser.parse_program()
        checker = Checker(ast)
        checker.check()
        ir = IRGen().gen(ast)
        asm = CodeGen(ir).gen()
        return Response(
            asm,
            mimetype="text/plain; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="out.asm"'},
        )
    except SyntaxError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": "其它错误：" + str(e)}), 400