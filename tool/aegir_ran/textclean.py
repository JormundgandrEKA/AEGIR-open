"""Normalise registry free text: HTML or markdown markup to plain text with simple list structure.

Registry versions mix HTML (<p>, <ul><li>, &#x2F;) and markdown (**bold**, "* item", \\*) for the same
content. Comparing or showing raw markup creates false changes and hides the words, so everything that is
compared or displayed goes through clean_text().
"""
import html
import re
from html.parser import HTMLParser

_TAG = re.compile(r"<\s*/?\s*(p|ul|ol|li|br|div|strong|b|em|i|u|span|h[1-6]|table|tr|td|th|sup|sub)\b", re.I)


class _ToText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.lists = [], []

    def _nl(self, n):
        s = "".join(self.out)
        have = len(s) - len(s.rstrip("\n"))
        if s and have < n:
            self.out.append("\n" * (n - have))

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self.out.append("\n")
        elif tag in ("p", "div") or (len(tag) == 2 and tag[0] == "h" and tag[1].isdigit()):
            self._nl(2)
        elif tag in ("ul", "ol"):
            self.lists.append([tag, 0])
            self._nl(1)
        elif tag == "li":
            self._nl(1)
            if self.lists and self.lists[-1][0] == "ol":
                self.lists[-1][1] += 1
                self.out.append(f"{'  ' * (len(self.lists) - 1)}{self.lists[-1][1]}. ")
            else:
                self.out.append(f"{'  ' * max(len(self.lists) - 1, 0)}• ")
        elif tag in ("tr",):
            self._nl(1)
        elif tag in ("td", "th"):
            self.out.append(" ")

    def handle_endtag(self, tag):
        if tag in ("p", "div") or (len(tag) == 2 and tag[0] == "h" and tag[1].isdigit()):
            self._nl(2)
        elif tag in ("ul", "ol"):
            if self.lists:
                self.lists.pop()
            self._nl(1)

    def handle_data(self, data):
        self.out.append(data)


def _unescape(s):
    for _ in range(3):
        t = html.unescape(s)
        if t == s:
            break
        s = t
    return s


def clean_text(s):
    if not s:
        return ""
    s = str(s).replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    if _TAG.search(s):
        p = _ToText()
        p.feed(s)
        p.close()
        s = "".join(p.out)
    s = _unescape(s)
    lines = []
    for line in s.split("\n"):
        line = line.replace("\t", " ")
        m = re.match(r"^(\s*)[*+\-]\s+(.*)$", line)          # markdown bullets (before unescaping \*)
        if m:
            line = "  " * min(len(m.group(1)) // 2, 3) + "• " + m.group(2)
        line = re.sub(r"^\s{0,3}#{1,6}\s*", "", line)         # markdown headings
        line = re.sub(r"(\*\*|__)(.+?)\1", r"\2", line)       # bold
        line = re.sub(r"\\([\\`*_{}\[\]()#+\-.!<>~|&])", r"\1", line)
        lead = re.match(r"^ *", line).group(0)
        line = lead + re.sub(r"[ ]{2,}", " ", line[len(lead):]).rstrip()
        lines.append(line)
    s = "\n".join(lines)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()
