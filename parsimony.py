"""Prototype line-breaker: open the fewest brackets that fit the line.

Unlike black/blue/ruff -- which explode the *outermost* bracket first and
stack every closing bracket on its own line -- this tool opens the minimum
number of brackets and coalesces adjacent ones, e.g.

    response = authed_client().get(reverse('forwarding:detail', args=[c.id]))

becomes

    response = authed_client().get(reverse(
        'forwarding:detail',
        args=[c.id],
    ))

rather than the deep staircase black/ruff produce. The motivation is
readability: coalescing reduces the vertical noise and keeps related calls
visually grouped (pattern recognition / least surprise).

Algorithm
---------
While a physical line exceeds LIMIT, explode one container that intersects an
over-long line, chosen by:
  1. multi-item containers only (>= 2 args/elements); single-item containers
     are never opened -- see "Contract" below.
  2. outermost (shallowest) of those.
Then re-measure and repeat. "Explode" = each element on its own line at a +4
hanging indent, with a trailing comma, and the closing bracket dedented to the
opening line's indent. Because we only open the *chosen* container and never
its single-item parents, adjacent openers like `get(reverse(` stay coalesced
for free -- coalescing was never about depth, only about not opening the
single-item wrappers.

Contract
--------
The tool only ever *adds* breaks to over-long lines; it never removes or
rewrites existing breaks. This makes it idempotent, safe to re-run, and safe
to combine with hand-formatting -- preserving existing line breaks is a
feature, not a gap. It is therefore the *owner* of line-wrapping and cannot be
combined with `ruff format`, which would re-flow its output back into the
staircase. Pair it with ruff-as-linter (E501 off) instead.

Multi-item-only is also a correctness guardrail: opening a single-item
subscript would turn `x[0]` into `x[0,]` (== `x[(0,)]`), which changes meaning.
Restricting to multi-item containers avoids that and, conveniently, avoids the
single-element "hanging" splits that are the very ugliness we set out to drop.

Known limitations (prototype)
-----------------------------
- Lines long for non-bracket reasons -- ternaries, boolean/arithmetic chains,
  attribute chains, long string literals -- are left untouched and *reported*,
  not fixed.
- A call chain whose first line stays over LIMIT even after its innermost
  multi-item container opens (e.g. `a.order_by(...).prefetch_related(P(...))`)
  is left partially wrapped and reported, rather than falling back to a
  staircase.
- No "join" pass: it will not re-flow code that another tool has already
  split. It only acts on lines that are physically too long.
- Greedy-shallowest, not provably minimum-count; the two diverge only in
  contrived deep nests. Comments inside brackets and pre-existing trailing
  commas are not specially handled.
"""

import argparse
import difflib
import sys
from pathlib import Path

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

LIMIT = 79
INDENT = 4

# Node types that carry an explodable comma-separated child list.
BRACKETED = (cst.Call, cst.List, cst.Tuple, cst.Set, cst.Dict, cst.Subscript)


def children_of(node):
    """Return the comma-separated children for a bracketed node."""
    if isinstance(node, cst.Call):
        return list(node.args)
    if isinstance(node, cst.Subscript):
        return list(node.slice)
    return list(node.elements)


def is_multi_item(node):
    return len(children_of(node)) >= 2


def is_explodable(node):
    """A bare tuple (`a, b` with no parens) has no bracket to open."""
    if isinstance(node, cst.Tuple):
        return bool(node.lpar)
    return True


def parenthesized_ws(indent):
    return cst.ParenthesizedWhitespace(
        first_line=cst.TrailingWhitespace(newline=cst.Newline()),
        indent=False,
        last_line=cst.SimpleWhitespace(indent),
    )


def explode(node, inner, outer):
    """Return `node` with its children split one-per-line."""
    kids = children_of(node)
    new_kids = []
    for i, kid in enumerate(kids):
        last = i == len(kids) - 1
        comma = cst.Comma(whitespace_after=parenthesized_ws(outer if last else inner))
        new_kids.append(kid.with_changes(comma=comma))

    open_ws = parenthesized_ws(inner)
    if isinstance(node, cst.Call):
        return node.with_changes(whitespace_before_args=open_ws, args=new_kids)
    if isinstance(node, cst.Subscript):
        lbracket = node.lbracket.with_changes(whitespace_after=open_ws)
        return node.with_changes(lbracket=lbracket, slice=new_kids)
    if isinstance(node, cst.List):
        lbracket = node.lbracket.with_changes(whitespace_after=open_ws)
        return node.with_changes(lbracket=lbracket, elements=new_kids)
    if isinstance(node, (cst.Set, cst.Dict)):
        lbrace = node.lbrace.with_changes(whitespace_after=open_ws)
        return node.with_changes(lbrace=lbrace, elements=new_kids)
    # Tuple (parenthesized; bare tuples are filtered out before we get here).
    lpar = [node.lpar[0].with_changes(whitespace_after=open_ws), *node.lpar[1:]]
    return node.with_changes(lpar=lpar, elements=new_kids)


class Exploder(cst.CSTTransformer):
    """Explode the single node whose start position matches `target`."""

    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, target, inner, outer):
        self.target = target  # (line, column)
        self.inner = inner
        self.outer = outer

    def _maybe(self, original, updated):
        pos = self.get_metadata(PositionProvider, original)
        if (pos.start.line, pos.start.column) == self.target:
            return explode(updated, self.inner, self.outer)
        return updated

    def leave_Call(self, o, u):
        return self._maybe(o, u)

    def leave_List(self, o, u):
        return self._maybe(o, u)

    def leave_Tuple(self, o, u):
        return self._maybe(o, u)

    def leave_Set(self, o, u):
        return self._maybe(o, u)

    def leave_Dict(self, o, u):
        return self._maybe(o, u)

    def leave_Subscript(self, o, u):
        return self._maybe(o, u)


class Collector(cst.CSTVisitor):
    """Collect bracketed nodes with their position, depth and arity."""

    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self):
        self.found = []
        self.depth = 0

    def on_visit(self, node):
        if isinstance(node, BRACKETED):
            pos = self.get_metadata(PositionProvider, node)
            already = "\n" in cst.Module([]).code_for_node(node)
            self.found.append(
                {
                    "pos": pos,
                    "depth": self.depth,
                    "multi": is_multi_item(node) if not already else False,
                    "exploded": already,
                    "explodable": is_explodable(node),
                }
            )
            self.depth += 1
        return True

    def on_leave(self, node):
        if isinstance(node, BRACKETED):
            self.depth -= 1


def overlong_lines(code):
    return {i for i, ln in enumerate(code.splitlines(), 1) if len(ln) > LIMIT}


def line_indent(code, lineno):
    line = code.splitlines()[lineno - 1]
    return len(line) - len(line.lstrip())


def format_code(code):
    """Return (formatted_code, skipped) where skipped lists (lineno, text)
    of lines still over the limit that no bracket rule could fix."""
    for _ in range(50):  # safety cap
        bad = overlong_lines(code)
        if not bad:
            return code, []

        wrapper = MetadataWrapper(cst.parse_module(code))
        collector = Collector()
        wrapper.visit(collector)

        # Candidates: not-yet-exploded MULTI-ITEM containers intersecting an
        # over-long line. We deliberately ignore single-item containers --
        # hanging a lone element is the staircase ugliness we avoid, and it is
        # never safe for a subscript index (`x[0]` -> `x[0,]` changes meaning).
        candidates = [
            c
            for c in collector.found
            if not c["exploded"]
            and c["explodable"]
            and c["multi"]
            and bad & set(range(c["pos"].start.line, c["pos"].end.line + 1))
        ]
        if not candidates:
            break  # no multi-item container to open on the remaining long lines

        # Priority: outermost (shallowest) container.
        chosen = max(candidates, key=lambda c: -c["depth"])
        pos = chosen["pos"]
        outer = line_indent(code, pos.start.line)
        inner = outer + INDENT

        wrapper = MetadataWrapper(cst.parse_module(code))
        exploder = Exploder(
            (pos.start.line, pos.start.column), " " * inner, " " * outer
        )
        code = wrapper.visit(exploder).code

    lines = code.splitlines()
    skipped = [(i, lines[i - 1]) for i in sorted(overlong_lines(code))]
    return code, skipped


def iter_paths(paths):
    for p in paths:
        path = Path(p)
        if path.is_dir():
            yield from sorted(path.rglob("*.py"))
        else:
            yield path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*", help="files/dirs (default: stdin)")
    parser.add_argument("-i", "--in-place", action="store_true")
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if any file would change; print a diff. No writes.",
    )
    args = parser.parse_args(argv)

    if not args.paths:
        formatted, skipped = format_code(sys.stdin.read())
        sys.stdout.write(formatted)
        report_skipped("<stdin>", skipped)
        return 0

    changed = False
    for path in iter_paths(args.paths):
        original = path.read_text()
        try:
            formatted, skipped = format_code(original)
        except Exception as exc:  # noqa: BLE001 - dry-run resilience
            print(f"{path}: ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        report_skipped(str(path), skipped)
        if formatted == original:
            continue
        changed = True
        if args.check:
            sys.stdout.writelines(
                difflib.unified_diff(
                    original.splitlines(keepends=True),
                    formatted.splitlines(keepends=True),
                    f"a/{path}",
                    f"b/{path}",
                )
            )
        elif args.in_place:
            path.write_text(formatted)
            print(f"reformatted {path}", file=sys.stderr)
        else:
            sys.stdout.write(formatted)

    return 1 if (args.check and changed) else 0


def report_skipped(name, skipped):
    for lineno, text in skipped:
        print(f"{name}:{lineno}: still over {LIMIT} cols: {text.strip()[:60]}…", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
