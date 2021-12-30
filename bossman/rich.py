def bracketize(s: str, open: str = '[', close: str = ']') -> str:
  from rich.markup import escape
  return escape(open + s + close)