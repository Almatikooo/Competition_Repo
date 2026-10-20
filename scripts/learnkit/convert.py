"""Turns open course sources (Markdown flavours and web pages) into clean, safe lesson HTML."""
import posixpath
import re
from urllib.parse import urljoin, urlparse

import nh3
import yaml
from bs4 import BeautifulSoup, Comment, NavigableString
from markdown_it import MarkdownIt
from mdit_py_plugins.deflist import deflist_plugin
from mdit_py_plugins.footnote import footnote_plugin

_md = (MarkdownIt("commonmark", {"html": True, "linkify": False, "typographer": False})
       .enable(["table", "strikethrough"]).use(footnote_plugin).use(deflist_plugin))

FRONT_MATTER = re.compile(r"\A﻿?---\s*\n(.*?)\n---\s*\n", re.S)

# ---------------------------------------------------------------- markdown flavours

def split_front_matter(text: str) -> tuple[dict, str]:
    m = FRONT_MATTER.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    return (meta if isinstance(meta, dict) else {}), text[m.end():]


BOX_TITLES = {"objectives": "Objectives", "questions": "Questions", "challenge": "Exercise", "callout": "Note",
              "keypoints": "Key points", "prereq": "Prerequisites", "discussion": "Discussion", "checklist": "Checklist",
              "caution": "Caution", "testimonial": "Testimonial", "spoiler": "More", "hint": "Hint", "tab": "", "group-tab": ""}


def carpentries(md: str) -> str:
    """Carpentries Workbench fenced divs (':::: challenge') -> HTML boxes; solutions -> <details>; instructor notes dropped."""
    out, stack = [], []
    for line in md.splitlines():
        stripped = line.strip()
        opening = re.fullmatch(r":{3,}\s*\{?\.?([A-Za-z][\w-]*)[^:]*\}?\s*:*", stripped)
        closing = re.fullmatch(r":{3,}", stripped)
        if opening and not closing:
            kind = opening.group(1).lower()
            dropping = any(k == "instructor" for k in stack)
            stack.append(kind)
            if dropping or kind == "instructor":
                continue
            if kind == "solution":
                out += ["", '<details class="solution"><summary>Show solution</summary>', ""]
            else:
                title = BOX_TITLES.get(kind, kind.title())
                out += ["", f'<div class="box box-{kind}">', ""] + ([f'<p class="box-title">{title}</p>', ""] if title else [])
            continue
        if closing and stack:
            kind = stack.pop()
            if kind == "instructor" or any(k == "instructor" for k in stack):
                continue
            out += ["", "</details>" if kind == "solution" else "</div>", ""]
            continue
        if any(k == "instructor" for k in stack):
            continue
        line = re.sub(r"^(\s*)```\s*\{?\s*(?:r|R)\b[^`}]*\}?\s*$", r"\1```r", line)  # R Markdown chunks
        line = re.sub(r"\{:\s*\.[\w-]+\s*\}", "", line)
        out.append(line)
    return "\n".join(out)


def mdx(md: str, resolve_asset) -> str:
    """Nextra MDX (dair-ai guide): resolve imported screenshots, drop JSX-only components."""
    imports = dict(re.findall(r"^import\s+(\w+)\s+from\s+['\"]([^'\"]+\.(?:png|jpe?g|gif|webp|svg))['\"]", md, re.M))
    md = re.sub(r"^(import|export)\s.*$", "", md, flags=re.M)
    md = re.sub(r"\{/\*.*?\*/\}", "", md, flags=re.S)

    def screenshot(m):
        name, alt = m.group(1), (re.search(r'alt=["\']([^"\']*)', m.group(0)) or [None, ""])[1]
        return f"\n![{alt}]({resolve_asset(imports[name])})\n" if name in imports else ""
    md = re.sub(r"<Screenshot\s+src=\{(\w+)\}[^>]*/>", screenshot, md)
    md = re.sub(r"<Callout[^>]*>", '\n<div class="box box-callout">\n', md)
    md = md.replace("</Callout>", "\n</div>\n")
    md = re.sub(r"<(Cards|Tabs|Steps)\b.*?</\1>", "", md, flags=re.S)
    md = re.sub(r"<[A-Z]\w*\b[^>]*/>", "", md)          # other self-closing components
    md = re.sub(r"</?[A-Z]\w*\b[^>]*>", "", md)          # unknown component wrappers
    return md


def ph(md: str, slug: str) -> str:
    """Programming Historian (Jekyll): figure includes -> images; other Liquid tags dropped."""
    def figure(m):
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        alt = attrs.get("alt") or attrs.get("caption", "")
        img = f"![{alt}](https://programminghistorian.org/images/{slug}/{attrs.get('filename', '')})"
        return f"\n{img}\n" + (f"\n*{attrs['caption']}*\n" if attrs.get("caption") and not re.fullmatch(r"Figure \d+\.?", attrs["caption"]) else "")
    md = re.sub(r"\{%\s*include figure\.html(.*?)%\}", figure, md)
    md = re.sub(r"\{%.*?%\}", "", md)
    md = re.sub(r"\{:\s*[^}]*\}", "", md)
    return md


def docfx(md: str) -> str:
    """Microsoft Docs flavour: includes, :::image::: blocks, zone pivots."""
    md = re.sub(r"^\s*\[!INCLUDE[^\]]*\]\([^)]*\)\]?\s*$", "", md, flags=re.M)
    md = re.sub(r":::image\s+type=\"[^\"]*\"\s+source=\"([^\"]+)\"\s+alt-text=\"([^\"]*)\"[^:]*:::",
                lambda m: f"![{m.group(2)}]({m.group(1)})", md)
    md = re.sub(r"^\s*:::\s*(zone|moniker|row|column)[^\n]*$", "", md, flags=re.M)
    md = re.sub(r"^\s*>\s*\[!div[^\]]*\]\s*$", "", md, flags=re.M)
    md = re.sub(r"\(\s*/([a-z][\w./-]*)\s*\)", r"(https://learn.microsoft.com/\1)", md)
    return md


def markdown_to_html(md: str) -> str:
    return _md.render(md)


# ---------------------------------------------------------------- HTML cleanup

NOISE_HEADING = re.compile(r"(pre[- ]?lecture quiz|post[- ]?lecture quiz|lecture quiz|^quiz$|knowledge check quiz|^assignment\b|translations|multi-language|"
                           r"^credits?$|^feedback$|table of contents|additional resources and learning|^contents$|^keep learning$|^great work!? continue)", re.I)
DROP_SECTION = re.compile(r"(^assignment\b|translations|multi-language|^feedback$|great work!? continue|^keep learning$|^credits?$)", re.I)
NOISE_TEXT = re.compile(r"(pre[- ]?lecture quiz|post[- ]?lecture quiz|this lesson is available in|click the image above|"
                        r"open (the|this) (notebook|lesson) in|^\s*→\s*go to|share this page|was this page helpful|back to top)", re.I)
REMOVE_TAGS = ["script", "style", "noscript", "iframe", "form", "button", "input", "select", "textarea", "svg", "canvas", "video", "audio",
               "nav", "header", "footer", "aside", "template", "object", "embed"]
BOX_ALERT = re.compile(r"^\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*", re.I)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "section"


def _level(tag) -> int:
    return int(tag.name[1]) if tag.name and re.fullmatch(r"h[1-6]", tag.name) else 0


def drop_sections(soup: BeautifulSoup, pattern: re.Pattern) -> None:
    """Remove a heading that matches `pattern` and everything until the next heading of the same or higher level."""
    for head in list(soup.find_all(re.compile(r"^h[1-6]$"))):
        if head.parent is None or not pattern.search(head.get_text(" ", strip=True)):
            continue
        level, node = _level(head), head.next_sibling
        head.decompose()
        while node is not None:
            nxt = node.next_sibling
            if getattr(node, "name", None) and 0 < _level(node) <= level:
                break
            node.extract()
            node = nxt


TEXTBOX_KINDS = {"learning-objectives": ("objectives", "Learning objectives"), "learning-outcomes": ("objectives", "Learning outcomes"),
                 "key-takeaways": ("keypoints", "Key takeaways"), "exercises": ("challenge", "Exercises"), "examples": ("callout", "Example"),
                 "tryit": ("challenge", "Try it")}
KEEP_CLASS = re.compile(r"^(box|box-[\w-]+|box-title|table-wrap|solution|attrib|language-[\w+#-]+)$")
ATTRIB_HEADING = re.compile(r"^(media attributions?|licen[cs]es? and attributions?|attributions?|image (credits|attributions?)|references and attributions)$", re.I)


def _textboxes(soup, body) -> None:
    """Pressbooks/Lumen textboxes -> our boxes; interactive 'Try it' widgets lose their iframes, so empty ones vanish later."""
    for box in body.select("div.textbox, aside.textbox"):
        classes = " ".join(box.get("class", []))
        kind, label = "callout", None
        for key, (k, l) in TEXTBOX_KINDS.items():
            if key in classes:
                kind, label = k, l
                break
        head = box.select_one(".textbox__title, .textbox__header, header h1, header h2, header h3, header p")
        if head is not None:
            label = head.get_text(" ", strip=True) or label
        for h in box.select(".textbox__header, header"):
            h.decompose()
        box.name = "div"
        box.attrs = {"class": ["box", f"box-{kind}"]}
        title = soup.new_tag("p", attrs={"class": "box-title"})
        title.string = label or "Note"
        box.insert(0, title)
    for lic in body.select("div.licensing, section.licensing, div.license-attribution"):
        lic.name = "details"
        lic.attrs = {"class": ["attrib"]}
        summary = soup.new_tag("summary")
        summary.string = "Licenses and attributions"
        lic.insert(0, summary)


def _attribution_sections(soup, body) -> None:
    """Keep source attributions (licences require them) but fold them away under a <details>."""
    for head in list(body.find_all(re.compile(r"^h[1-6]$"))):
        if head.parent is None or not ATTRIB_HEADING.match(head.get_text(" ", strip=True)):
            continue
        level = _level(head)
        details = soup.new_tag("details", attrs={"class": "attrib"})
        summary = soup.new_tag("summary")
        summary.string = head.get_text(" ", strip=True)
        details.append(summary)
        node = head.next_sibling
        while node is not None:
            nxt = node.next_sibling
            if getattr(node, "name", None) and 0 < _level(node) <= level:
                break
            details.append(node.extract())
            node = nxt
        head.replace_with(details)


def _box_titles(body) -> None:
    """A heading that opens a box becomes the box title (Carpentries callouts start with '## Title')."""
    for box in body.select("div.box"):
        label = box.find("p", class_="box-title", recursive=False)
        first = next((c for c in box.children if getattr(c, "name", None) and c is not label), None)
        if first is not None and re.fullmatch(r"h[1-6]", first.name or ""):
            text = first.get_text(" ", strip=True)
            if label is None:
                label = BeautifulSoup('<p class="box-title"></p>', "lxml").p
                box.insert(0, label)
            label.string = text
            first.decompose()
        if label is not None and not box.get_text(" ", strip=True).replace(label.get_text(" ", strip=True), "", 1).strip() and not box.find("img"):
            box.decompose()


def clean_html(html: str, *, page_url: str, asset_base: str | None = None, link_base: str | None = None,
               title: str | None = None, drop_selectors: tuple = (), keep_images: bool = True, same_host_images: bool = False,
               drop_headings: tuple = ()) -> str:
    """Normalise one lesson: remove chrome & noise, absolutise URLs, demote headings, wrap tables, add heading ids."""
    soup = BeautifulSoup(html, "lxml")
    body = soup.body or soup
    for comment in body.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()
    for sel in drop_selectors:
        for el in body.select(sel):
            el.decompose()
    _textboxes(soup, body)
    for tag in REMOVE_TAGS:
        for el in body.find_all(tag):
            el.decompose()
    for el in body.select('[role="navigation"], [aria-hidden="true"], .visually-hidden, .sr-only, .usa-sr-only, .screen-reader-text'):
        el.decompose()
    drop_sections(body, DROP_SECTION)
    if drop_headings:
        drop_sections(body, re.compile("|".join(drop_headings), re.I))
    for head in list(body.find_all(re.compile(r"^h[1-6]$"))):
        if NOISE_HEADING.search(head.get_text(" ", strip=True)):
            head.decompose()
    for el in list(body.find_all(["p", "li", "div"])):
        if el.parent is None:
            continue
        text = el.get_text(" ", strip=True)
        if text and len(text) < 220 and NOISE_TEXT.search(text):
            el.decompose()
    _attribution_sections(soup, body)
    # GitHub/Docs alerts:  > [!NOTE] ...
    for bq in body.find_all("blockquote"):
        first = bq.find("p")
        if first and first.contents and isinstance(first.contents[0], NavigableString) and BOX_ALERT.match(str(first.contents[0])):
            kind = BOX_ALERT.match(str(first.contents[0])).group(1).lower()
            first.contents[0].replace_with(BOX_ALERT.sub("", str(first.contents[0])))
            bq.name = "div"
            bq["class"] = ["box", f"box-{kind}"]
            label = soup.new_tag("p", attrs={"class": "box-title"})
            label.string = kind.title()
            bq.insert(0, label)
    page_host = urlparse(page_url).netloc
    for img in list(body.find_all("img")):
        src = img.get("data-src") or img.get("data-lazy-src") or img.get("src") or ""
        if not keep_images or not src or src.startswith("data:") or re.search(r"shields\.io|badge|/badges?/|\.svg\?|spacer|pixel|gravatar", src):
            img.decompose()
            continue
        absolute = urljoin(asset_base or page_url, src)
        if same_host_images and urlparse(absolute).netloc not in (page_host, "www." + page_host, page_host.removeprefix("www.")):
            img.decompose()
            continue
        img.attrs = {k: v for k, v in img.attrs.items() if k in ("alt", "title", "width", "height")}
        img["src"] = absolute
        img["loading"] = "lazy"
        img["alt"] = img.get("alt", "")
    for a in body.find_all("a"):
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("javascript:", "data:")):
            a.unwrap()
            continue
        if href.startswith("#"):
            a.attrs = {"href": href}
            continue
        absolute = urljoin(link_base or page_url, href)
        a.attrs = {"href": absolute, "target": "_blank", "rel": "noopener noreferrer"}
    # headings: the lesson title is shown by the app, so drop a leading duplicate h1 and demote the rest
    for h1 in body.find_all("h1"):
        if title and _slug(h1.get_text(" ", strip=True)) == _slug(title):
            h1.decompose()
        else:
            h1.name = "h2"
    _box_titles(body)
    seen = set()
    for head in body.find_all(["h2", "h3"]):
        slug = _slug(head.get_text(" ", strip=True))
        while slug in seen:
            slug += "-x"
        seen.add(slug)
        head.attrs = {"id": slug}
    for h in body.find_all(["h4", "h5", "h6"]):
        h.attrs = {}
    for table in body.find_all("table"):
        if table.parent and "table-wrap" not in (table.parent.get("class") or []):
            wrapper = soup.new_tag("div", attrs={"class": "table-wrap"})
            table.wrap(wrapper)
    for el in body.find_all(class_=True):
        kept = [c for c in el.get("class", []) if KEEP_CLASS.match(c)]
        if kept:
            el["class"] = kept
        else:
            del el["class"]
    for el in body.find_all("span"):
        el.unwrap()
    for p in body.find_all("p"):
        if not p.get_text(strip=True) and not p.find(["img", "math"]):
            p.decompose()
    html = body.decode_contents() if body.name == "body" else str(body)
    return sanitize(html)


def demote_headings(html: str) -> str:
    """Used when stitching pages into one lesson: each page title becomes h2, so its own headings move down a level."""
    soup = BeautifulSoup(html, "lxml")
    body = soup.body or soup
    for level in (5, 4, 3, 2):
        for h in body.find_all(f"h{level}"):
            h.name = f"h{level + 1}"
    return body.decode_contents() if body.name == "body" else str(body)


def split_sections(html: str, target: int = 1600, drop: tuple = (), titles: list | None = None, intro_title: str = "Introduction") -> list[tuple[str, str]]:
    """Split one long page into lesson-sized parts at h2 boundaries; consecutive short sections are grouped to ~target words."""
    sections = [(t or intro_title, h) for t, h in split_by_heading(html, "h2")]
    if drop:
        rx = re.compile("|".join(drop), re.I)
        sections = [(t, h) for t, h in sections if not rx.search(t)]
    groups, current, words = [], [], 0
    for t, h in sections:
        w = word_count(h)
        if current and words + w > target * 1.35 and words >= target * 0.45:
            groups.append(current)
            current, words = [], 0
        current.append((t, h))
        words += w
    if current:
        if groups and words < target * 0.3:
            groups[-1].extend(current)
        else:
            groups.append(current)
    out = []
    for i, group in enumerate(groups):
        name = titles[i] if titles and i < len(titles) else group[0][0]
        body = "".join((f'<h2 id="{_slug(t)}">{t}</h2>' if j or t != name else "") + h for j, (t, h) in enumerate(group))
        out.append((name, body))
    return out


ALLOWED_TAGS = {"p", "br", "hr", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "dl", "dt", "dd", "a", "img", "figure", "figcaption",
                "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption", "blockquote", "pre", "code", "em", "strong", "b", "i",
                "u", "sub", "sup", "small", "mark", "kbd", "del", "ins", "s", "div", "span", "details", "summary", "abbr", "cite", "q",
                "math", "mrow", "mi", "mo", "mn", "ms", "mtext", "msup", "msub", "msubsup", "mfrac", "msqrt", "mroot", "mover", "munder",
                "munderover", "mtable", "mtr", "mtd", "mspace", "mstyle", "mpadded", "mphantom", "menclose", "semantics"}
ALLOWED_ATTRS = {"a": {"href", "title", "target"}, "img": {"src", "alt", "title", "width", "height", "loading"},
                 "th": {"colspan", "rowspan", "scope"}, "td": {"colspan", "rowspan"}, "ol": {"start", "type"},
                 "code": {"class"}, "pre": {"class"}, "div": {"class"}, "span": {"class"}, "p": {"class"},
                 "details": {"class"}, "abbr": {"title"}, "h2": {"id"}, "h3": {"id"}, "table": {"class"},
                 "math": {"display"}, "mo": {"stretchy", "fence", "separator", "form"}, "mfrac": {"linethickness"},
                 "mtd": {"columnspan", "rowspan"}, "mstyle": {"displaystyle", "scriptlevel"}}


def sanitize(html: str) -> str:
    return nh3.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, url_schemes={"http", "https", "mailto"},
                     link_rel="noopener noreferrer", strip_comments=True).strip()


def plain_text(html: str) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(html, "lxml").get_text(" ")).strip()


def word_count(html: str) -> int:
    soup = BeautifulSoup(html, "lxml")
    for pre in soup.find_all("pre"):
        pre.decompose()
    return len(soup.get_text(" ").split())


def headings(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    return [{"id": h.get("id"), "text": h.get_text(" ", strip=True), "level": int(h.name[1])} for h in soup.find_all(["h2", "h3"]) if h.get("id")]


def select_main(html: str, selectors: tuple) -> str:
    soup = BeautifulSoup(html, "lxml")
    for sel in selectors:
        found = soup.select(sel)
        if found:
            return "".join(str(f) for f in found)
    return str(soup.body or soup)


def split_by_heading(html: str, level: str = "h2") -> list[tuple[str, str]]:
    """[(heading text, section html)] — text before the first heading is returned with heading ''."""
    soup = BeautifulSoup(html, "lxml")
    body = soup.body or soup
    sections, title, buf = [], "", []
    for node in list(body.children):
        if getattr(node, "name", None) == level:
            if buf:
                sections.append((title, "".join(str(x) for x in buf)))
            title, buf = node.get_text(" ", strip=True), []
        else:
            buf.append(node)
    if buf:
        sections.append((title, "".join(str(x) for x in buf)))
    return sections


def rel_asset(repo_dir: str, href: str) -> str:
    return posixpath.normpath(posixpath.join(repo_dir, href))
