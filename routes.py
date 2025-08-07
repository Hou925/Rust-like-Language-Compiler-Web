from flask import request, jsonify, render_template_string
from tokenizer import tokenize
from parser import Parser
from irgen import IRGen
from checker import Checker
from codegen import CodeGen  # 新增

def index():
    return render_template_string(open("frontend.html", encoding="utf-8").read())

def analyze():
    code = request.json.get("code", "")
    tokens = tokenize(code)
    parser = None
    ast = None
    ir = []
    asm = ""  # 新增
    try:
        parser = Parser(tokens)
        ast = parser.parse_program()
        checker = Checker(ast)
        checker.check()
        irgen = IRGen()
        ir = irgen.gen(ast)
        codegen = CodeGen(ir)
        asm = codegen.gen()  # 新增
        return jsonify({"tokens": tokens, "ast": ast, "ir": ir, "asm": asm, "success": True})
    except SyntaxError as e:
        return jsonify({"success": False, "error": str(e), "tokens": tokens}), 400
    except Exception as e:
        return jsonify({"success": False, "error": "其它错误：" + str(e), "tokens": tokens}), 400