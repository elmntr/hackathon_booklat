"""The single-file frontend must expose each script hook exactly once."""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import re


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.parents = {}
        self.stack = []
    def handle_starttag(self, tag, attrs):
        identifier = dict(attrs).get('id')
        if identifier:
            self.ids.append(identifier)
            self.parents[identifier] = list(self.stack)
        if tag not in ('input', 'meta', 'link', 'br', 'hr', 'img', 'source', 'wbr'):
            self.stack.append((tag, identifier))
    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


def test_unique_ids_and_script_targets():
    html = (Path(__file__).resolve().parents[1] / 'web/index.html').read_text(encoding='utf-8')
    dom = Elements(); dom.feed(html)
    assert not [key for key, count in Counter(dom.ids).items() if count > 1]
    script = html.split('<script>')[1].split('</script>')[0]
    assert set(re.findall(r"\$\('([^']+)'\)", script)) <= set(dom.ids)
    assert len(re.findall(r"let passages\s*=", script)) == 1
    assert script.count('async function recent(') == 1
    assert script.count('function showScreen(') == 1
    for target, owner in [('reading-passage', 'reading-screen'), ('results-passage', 'results-screen'),
                          ('learner', 'setup-screen'), ('grading-form', 'results-screen'),
                          ('recording-player', 'results-screen')]:
        assert ('section', owner) in dom.parents[target]
    assert ('section', 'setup-screen') not in dom.parents['reading-screen']

