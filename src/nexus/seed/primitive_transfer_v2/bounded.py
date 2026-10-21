"""Small total-budget AST interpreter; never compile/exec submitted Python.

This initial subset is deliberately narrower than the planned final families.
Unsupported syntax fails closed. It is not a replacement general Python sandbox.
"""
from __future__ import annotations

import ast
import operator

from .contracts import encode

BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv}
CMP = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
       ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge}
BUILTINS = {"sum": sum, "len": len, "min": min, "max": max, "abs": abs,
            "sorted": sorted, "list": list, "reversed": lambda x: list(reversed(x))}
ALLOWED = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return,
           ast.Constant, ast.Name, ast.Load, ast.Store, ast.List, ast.Tuple,
           ast.BinOp, ast.UnaryOp, ast.USub, ast.UAdd, ast.Call, ast.IfExp,
           ast.Compare, ast.ListComp, ast.comprehension, ast.Subscript,
           *BIN, *CMP)


def check_source(source):
    if type(source) is not str or len(source.encode()) > 8192:
        raise ValueError("source limit")
    tree = ast.parse(source)
    if not 1 <= len(tree.body) <= 8 or any(type(n) is not ast.FunctionDef for n in tree.body):
        raise ValueError("one to eight pure function definitions required")
    names = [n.name for n in tree.body]
    if len(set(names)) != len(names) or any(n.startswith("_") or n in BUILTINS for n in names):
        raise ValueError("unique nonreserved function names required")
    nodes = list(ast.walk(tree))
    if len(nodes) > 1024:
        raise ValueError("AST limit")
    for n in nodes:
        if type(n) not in ALLOWED:
            raise ValueError("AST construct not supported: " + type(n).__name__)
        if isinstance(n, ast.FunctionDef):
            a = n.args
            if (len(a.args) != 1 or a.posonlyargs or a.kwonlyargs or a.vararg or a.kwarg
                    or a.defaults or a.kw_defaults or n.decorator_list or n.returns
                    or n.type_params or a.args[0].annotation or len(n.body) != 1
                    or type(n.body[0]) is not ast.Return or n.body[0].value is None):
                raise ValueError("one-argument expression function required")
        if isinstance(n, ast.Call) and (type(n.func) is not ast.Name or n.keywords
                                       or len(n.args) != 1 or n.func.id not in names + list(BUILTINS)):
            raise ValueError("unapproved function call")
        if isinstance(n, ast.Name) and n.id.startswith("_"):
            raise ValueError("reserved identifier")
        if isinstance(n, ast.comprehension) and (n.is_async or type(n.target) is not ast.Name):
            raise ValueError("simple synchronous comprehension required")
    return tree


def bounded_value(x, depth=0):
    if depth > 8:
        raise ValueError("value depth limit")
    if type(x) in (int, float):
        if not -1e9 <= x <= 1e9:
            raise ValueError("numeric limit")
    elif type(x) in (list, tuple):
        if len(x) > 64:
            raise ValueError("collection limit")
        for y in x:
            bounded_value(y, depth + 1)
    elif type(x) is str:
        if len(x) > 256:
            raise ValueError("string limit")
    elif x is not None and type(x) is not bool:
        raise ValueError("unsupported input/output type")
    return x


class Program:
    def __init__(self, source, max_steps=4096):
        self.tree = check_source(source)
        self.functions = {n.name: n for n in self.tree.body}
        if type(max_steps) is not int or not 1 <= max_steps <= 4096:
            raise ValueError("bounded instruction limit required")
        self.limit = max_steps
        self.steps = self.calls = 0

    def call(self, name, x):
        # JSON serializability and size are also bounded before any evaluation.
        self.steps = self.calls = 0
        encode({"input": x})
        bounded_value(x)
        return self._call(name, x, 0)

    def tick(self):
        self.steps += 1
        if self.steps > self.limit:
            raise ValueError("AST execution budget exhausted")

    def _call(self, name, x, depth):
        self.tick()
        if depth > 8:
            raise ValueError("call depth limit")
        if name not in BUILTINS and name not in self.functions:
            raise KeyError(name)
        self.calls += 1
        if name in BUILTINS:
            out = BUILTINS[name](x)
        else:
            fn = self.functions[name]
            out = self.expr(fn.body[0].value, {fn.args.args[0].arg: x}, depth + 1)
        return bounded_value(out)

    def expr(self, n, env, depth):
        self.tick()
        if type(n) is ast.Constant:
            return bounded_value(n.value)
        if type(n) is ast.Name:
            return env[n.id]
        if type(n) in (ast.List, ast.Tuple):
            return bounded_value([self.expr(e, env, depth) for e in n.elts])
        if type(n) is ast.BinOp:
            a, b = self.expr(n.left, env, depth), self.expr(n.right, env, depth)
            # Prevent huge sequence allocation BEFORE multiplication/addition.
            if type(a) not in (int, float) or type(b) not in (int, float):
                raise ValueError("numeric binary operations only")
            return bounded_value(BIN[type(n.op)](a, b))
        if type(n) is ast.UnaryOp:
            a = self.expr(n.operand, env, depth)
            if type(a) not in (int, float):
                raise ValueError("numeric unary operations only")
            return bounded_value(-a if type(n.op) is ast.USub else +a)
        if type(n) is ast.Call:
            return self._call(n.func.id, self.expr(n.args[0], env, depth), depth)
        if type(n) is ast.Compare:
            a = self.expr(n.left, env, depth)
            for op, right in zip(n.ops, n.comparators):
                b = self.expr(right, env, depth)
                if not CMP[type(op)](a, b):
                    return False
                a = b
            return True
        if type(n) is ast.IfExp:
            return self.expr(n.body if self.expr(n.test, env, depth) else n.orelse, env, depth)
        if type(n) is ast.Subscript:
            value, index = self.expr(n.value, env, depth), self.expr(n.slice, env, depth)
            if type(index) is not int:
                raise ValueError("integer index required")
            return value[index]
        if type(n) is ast.ListComp:
            out = []

            def visit(i, local):
                self.tick()
                if i == len(n.generators):
                    if len(out) >= 64:
                        raise ValueError("comprehension output limit")
                    out.append(self.expr(n.elt, local, depth))
                    return
                g = n.generators[i]
                items = self.expr(g.iter, local, depth)
                if type(items) not in (list, tuple, str):
                    raise ValueError("bounded iterable required")
                for item in items:
                    self.tick()
                    inner = dict(local, **{g.target.id: item})
                    if all(self.expr(c, inner, depth) for c in g.ifs):
                        visit(i + 1, inner)

            visit(0, env)
            return bounded_value(out)
        raise ValueError("unsupported expression")
