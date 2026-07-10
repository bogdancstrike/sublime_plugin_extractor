# Extractor - a Sublime Text plugin.
#
# Pulls structured tokens (emails, URLs, IPs, dates, ...) out of the current
# file (or selection) and drops the de-duplicated results into a new file.
#
# The code is intentionally written to run on both the legacy Python 3.3
# plugin host (Sublime Text 3) and the 3.8 host (Sublime Text 4), so it avoids
# f-strings and other 3.6+ only syntax.

import re

import sublime
import sublime_plugin


# ---------------------------------------------------------------------------
# Shared reference data
# ---------------------------------------------------------------------------

# Curated set of top-level domains used to gate hostname / domain matches.
# It deliberately favours domains that appear in prose and leaves out TLDs that
# collide with common source-file extensions (py, md, sh, js, ts, rb, ...) so
# that "main.py" or "README.md" are not mistaken for hostnames. Exotic TLDs can
# always be captured with the custom-regex extractor.
COMMON_TLDS = frozenset("""
com org net edu gov mil int info biz name pro mobi io co dev app ai xyz online
site tech store blog shop cloud page wiki news live tv me cc ws work agency
digital media email group world today life network solutions systems software
studio design tools zone center company expert academy finance global support
us uk ca de fr es it nl be ch at se no dk fi ie pt gr pl cz sk hu ro bg hr si
ee lv lt ru ua by tr il sa ae eg za ng ke ma in pk bd lk cn jp kr tw hk sg my
th vn ph id au nz br ar cl mx pe ve uy ec eu
""".split())

# Two-label public suffixes, used to reduce a full hostname to its registrable
# ("root") domain, e.g. mail.google.co.uk -> google.co.uk.
MULTI_SUFFIXES = frozenset("""
co.uk org.uk gov.uk ac.uk me.uk net.uk sch.uk ltd.uk plc.uk nhs.uk mod.uk
com.au net.au org.au edu.au gov.au id.au co.nz org.nz net.nz govt.nz ac.nz
co.jp or.jp ne.jp ac.jp go.jp com.cn net.cn org.cn gov.cn edu.cn com.br net.br
org.br gov.br com.mx com.ar com.tr com.sg com.hk com.tw co.in net.in org.in
gen.in firm.in co.za org.za web.za co.kr or.kr com.ua co.il org.il ac.il gov.il
com.pl net.pl org.pl com.ru net.ru org.ru com.vn com.ph com.my com.pk com.bd
com.sa com.eg
""".split())

# Trailing characters trimmed from URLs (punctuation that usually hugs a link
# in prose but is not part of it).
URL_TRAILING = ".,;:!?)]}'\"<>"


# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,24}\b",
    re.IGNORECASE,
)

URL_RE = re.compile(
    r"\b(?:https?://|ftp://|www\.)[^\s<>\"'`\)\]}]+",
    re.IGNORECASE,
)

IPV4_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b"
)

# Comprehensive IPv6, wrapped in lookarounds so it does not match a fragment of
# a longer hex/colon run.
_IPV6_BODY = (
    r"(?:"
    r"(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}|"
    r"(?:[0-9A-Fa-f]{1,4}:){1,7}:|"
    r"(?:[0-9A-Fa-f]{1,4}:){1,6}:[0-9A-Fa-f]{1,4}|"
    r"(?:[0-9A-Fa-f]{1,4}:){1,5}(?::[0-9A-Fa-f]{1,4}){1,2}|"
    r"(?:[0-9A-Fa-f]{1,4}:){1,4}(?::[0-9A-Fa-f]{1,4}){1,3}|"
    r"(?:[0-9A-Fa-f]{1,4}:){1,3}(?::[0-9A-Fa-f]{1,4}){1,4}|"
    r"(?:[0-9A-Fa-f]{1,4}:){1,2}(?::[0-9A-Fa-f]{1,4}){1,5}|"
    r"[0-9A-Fa-f]{1,4}:(?::[0-9A-Fa-f]{1,4}){1,6}|"
    r":(?:(?::[0-9A-Fa-f]{1,4}){1,7}|:)|"
    r"::(?:ffff(?::0{1,4})?:)?"
    r"(?:(?:25[0-5]|(?:2[0-4]|1?[0-9])?[0-9])\.){3}"
    r"(?:25[0-5]|(?:2[0-4]|1?[0-9])?[0-9])|"
    r"(?:[0-9A-Fa-f]{1,4}:){1,4}:"
    r"(?:(?:25[0-5]|(?:2[0-4]|1?[0-9])?[0-9])\.){3}"
    r"(?:25[0-5]|(?:2[0-4]|1?[0-9])?[0-9])"
    r")"
)
IPV6_RE = re.compile(r"(?<![0-9A-Fa-f:])" + _IPV6_BODY + r"(?![0-9A-Fa-f:])")

HOSTNAME_RE = re.compile(
    r"(?<![\w.\-])"
    r"(?:localhost|"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,24})"
    r"(?![\w\-])",
    re.IGNORECASE,
)

PORT_RE = re.compile(
    r"(?:[A-Za-z0-9\-]+\.[A-Za-z0-9.\-]+|\[[0-9A-Fa-f:]+\]|localhost):(\d{1,5})\b"
)

PHONE_RE = re.compile(r"(?<![\w+])\+?\d(?:[ \t.\-()]{0,2}\d){6,14}(?![\w])")

_MONTHS = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
)

# The year field is restricted to exactly 2 or 4 digits (never 3) so a 3-digit
# IPv4 octet such as the "0.0.255" inside 10.0.0.255 is not read as a date, and
# the trailing (?!:) stops a clock time (12:00) from being taken as a date.
DATE_RE = re.compile(
    r"\b(?:"
    r"\d{4}-\d{2}-\d{2}|"
    r"\d{4}/\d{2}/\d{2}|"
    r"\d{1,2}[/.\-]\d{1,2}[/.\-](?:\d{4}|\d{2})|"
    r"(?:" + _MONTHS + r")\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+(?:\d{4}|\d{2})|"
    r"\d{1,2}(?:st|nd|rd|th)?\s+(?:" + _MONTHS + r")\.?,?\s+(?:\d{4}|\d{2})"
    r")\b(?!:)",
    re.IGNORECASE,
)

# Hours 00-23, minutes/seconds 00-59, so invalid clock values (e.g. 30:00)
# are not reported.
TIME_RE = re.compile(
    r"(?<!\.)\b(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?(?:\.\d{1,6})?"
    r"\s?(?:[AaPp]\.?\s?[Mm]\.?)?(?!\d)"
)

TIMESTAMP_RE = re.compile(
    r"(?:"
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?"
    r"(?:Z|[+\-]\d{2}:?\d{2})?\b|"
    r"\b(?:" + _MONTHS + r")\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\b|"
    r"\b1\d{12}\b|"
    r"\b1\d{9}\b"
    r")",
    re.IGNORECASE,
)

# Windows/UNC path segments stop at whitespace, commas and semicolons so a path
# in prose does not swallow the following words. (Paths containing spaces are
# therefore captured only up to the first space.)
PATH_RE = re.compile(
    r"(?:"
    r"[A-Za-z]:\\(?:[^\\/:*?\"<>|\s,;]+\\?)*|"
    r"\\\\[^\\/:*?\"<>|\s,;]+(?:\\[^\\/:*?\"<>|\s,;]+)*|"
    r"(?<![\w:/])(?:~|\.{1,2})?/(?:[\w.\-]+/?)+"
    r")"
)

UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)

MAC_RE = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")

HEXCOLOR_RE = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")

NUMBER_RE = re.compile(
    r"(?<![\w.])[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?!\w)"
)

HASHTAG_RE = re.compile(r"(?<![\w&#])#[A-Za-z][A-Za-z0-9_]*")

MENTION_RE = re.compile(r"(?<![\w@./])@[A-Za-z0-9_]{2,}\b")

# 13-19 digit runs, optionally separated by spaces/dashes; validated by Luhn.
CC_RE = re.compile(r"(?<![\d.\-])(?:\d[ \-]?){12,18}\d(?![\d.\-])")

SECRET_RE = re.compile(
    r"(?:"
    r"AKIA[0-9A-Z]{16}|"                                      # AWS access key id
    r"ASIA[0-9A-Z]{16}|"                                      # AWS temp key id
    r"AIza[0-9A-Za-z_\-]{35}|"                                # Google API key
    r"gh[pousr]_[A-Za-z0-9]{36,255}|"                         # GitHub token
    r"github_pat_[A-Za-z0-9_]{22,255}|"                       # GitHub fine PAT
    r"xox[baprs]-[0-9A-Za-z\-]{10,72}|"                       # Slack token
    r"sk-[A-Za-z0-9]{20,64}|"                                 # OpenAI-style key
    r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+|"  # JWT
    r"-----BEGIN[A-Z ]*PRIVATE KEY-----"                      # PEM private key
    r")"
)

MDLINK_RE = re.compile(
    r"\[[^\]]*\]\(\s*<?([^)>\s]+)>?(?:\s+[\"'][^\"']*[\"'])?\s*\)"
)


# ---------------------------------------------------------------------------
# Extractor helpers
# ---------------------------------------------------------------------------

def _re_fn(pattern, group=0, rstrip=None, transform=None):
    """Build an extractor that yields a group from every match of *pattern*."""
    def fn(text):
        out = []
        for m in pattern.finditer(text):
            val = m.group(group)
            if val is None:
                continue
            if rstrip:
                val = val.rstrip(rstrip)
            if transform is not None:
                val = transform(val)
            val = val.strip()
            if val:
                out.append(val)
        return out
    return fn


def _luhn_ok(digits):
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = ord(ch) - 48
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _matches_whole(regex, s):
    """True if *regex* matches the entire string *s* (re.fullmatch is 3.4+)."""
    m = regex.match(s)
    return bool(m) and m.end() == len(s)


def _registrable_domain(host):
    host = host.lower().rstrip(".")
    if host == "localhost" or ":" in host:
        return None
    labels = host.split(".")
    if len(labels) < 2:
        return None
    last_two = ".".join(labels[-2:])
    if last_two in MULTI_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return last_two


def _valid_host(token):
    low = token.lower()
    if low == "localhost":
        return True
    return low.rsplit(".", 1)[-1] in COMMON_TLDS


def extract_hostnames(text):
    return [m.group(0) for m in HOSTNAME_RE.finditer(text)
            if _valid_host(m.group(0))]


def extract_domains(text):
    out = []
    for host in extract_hostnames(text):
        dom = _registrable_domain(host)
        if dom:
            out.append(dom)
    return out


def extract_ports(text):
    out = []
    for m in PORT_RE.finditer(text):
        port = m.group(1)
        try:
            n = int(port)
        except ValueError:
            continue
        if 1 <= n <= 65535:
            out.append(port)
    return out


def extract_phones(text):
    out = []
    for m in PHONE_RE.finditer(text):
        raw = m.group(0).strip()
        digits = re.sub(r"\D", "", raw)
        if not (7 <= len(digits) <= 15):
            continue
        # Require a phone-like shape: a leading "+" or grouping separators.
        # This drops bare digit runs (epochs, ids) that are indistinguishable
        # from unformatted phone numbers.
        if "+" not in raw and not re.search(r"[ ().\-]", raw):
            continue
        # Reject tokens that are really an IPv4 address or a date.
        if _matches_whole(IPV4_RE, raw) or _matches_whole(DATE_RE, raw):
            continue
        # Reject ISO date / timestamp prefixes (2024-01-31 ...).
        if re.search(r"\d{4}-\d\d-\d\d", raw):
            continue
        # Reject card-like runs of equal 4-digit groups (4111 1111 1111).
        if re.match(r"^(?:\d{4}[ \-]){2,}\d{4}$", raw):
            continue
        out.append(raw)
    return out


def extract_credit_cards(text):
    out = []
    for m in CC_RE.finditer(text):
        raw = m.group(0).strip()
        digits = re.sub(r"\D", "", raw)
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            out.append(raw)
    return out


# ---------------------------------------------------------------------------
# Extractor registry
# ---------------------------------------------------------------------------

EXTRACTORS = [
    {"key": "emails", "label": "Emails",
     "desc": "Email addresses (user@host.tld)",
     "fn": _re_fn(EMAIL_RE)},
    {"key": "urls", "label": "URLs",
     "desc": "http, https, ftp and www links",
     "fn": _re_fn(URL_RE, rstrip=URL_TRAILING)},
    {"key": "domains", "label": "Domains",
     "desc": "Registrable root domains (example.co.uk)",
     "fn": extract_domains},
    {"key": "ipv4", "label": "IPv4 addresses",
     "desc": "Dotted-quad addresses (192.168.0.1)",
     "fn": _re_fn(IPV4_RE)},
    {"key": "ipv6", "label": "IPv6 addresses",
     "desc": "Colon-hex addresses (::1, fe80::...)",
     "fn": _re_fn(IPV6_RE)},
    {"key": "hostnames", "label": "Hostnames",
     "desc": "Fully-qualified host names and localhost",
     "fn": extract_hostnames},
    {"key": "ports", "label": "Ports",
     "desc": "Port numbers from host:port references",
     "fn": extract_ports},
    {"key": "phone_numbers", "label": "Phone numbers",
     "desc": "International / local phone numbers (heuristic)",
     "fn": extract_phones},
    {"key": "dates", "label": "Dates",
     "desc": "ISO, numeric and month-name dates",
     "fn": _re_fn(DATE_RE)},
    {"key": "times", "label": "Times",
     "desc": "Clock times, optional seconds and AM/PM",
     "fn": _re_fn(TIME_RE)},
    {"key": "timestamps", "label": "Timestamps",
     "desc": "ISO 8601, syslog and Unix-epoch timestamps",
     "fn": _re_fn(TIMESTAMP_RE)},
    {"key": "file_paths", "label": "File paths",
     "desc": "Unix, Windows and UNC file paths",
     "fn": _re_fn(PATH_RE)},
    {"key": "uuids", "label": "UUIDs",
     "desc": "RFC 4122 UUIDs / GUIDs",
     "fn": _re_fn(UUID_RE)},
    {"key": "mac_addresses", "label": "MAC addresses",
     "desc": "Ethernet hardware addresses",
     "fn": _re_fn(MAC_RE)},
    {"key": "hex_colors", "label": "Hex colors",
     "desc": "#rgb and #rrggbb color codes",
     "fn": _re_fn(HEXCOLOR_RE)},
    {"key": "numbers", "label": "Numbers",
     "desc": "Integers and decimals (thousands-aware)",
     "fn": _re_fn(NUMBER_RE)},
    {"key": "hashtags", "label": "Hashtags",
     "desc": "#hashtag tokens",
     "fn": _re_fn(HASHTAG_RE)},
    {"key": "mentions", "label": "Mentions",
     "desc": "@handle mentions",
     "fn": _re_fn(MENTION_RE)},
    {"key": "credit_cards", "label": "Credit card numbers",
     "desc": "13-19 digit numbers passing the Luhn check",
     "fn": extract_credit_cards},
    {"key": "secrets", "label": "Secrets & API keys",
     "desc": "AWS/Google/GitHub/Slack keys, JWTs, PEM keys",
     "fn": _re_fn(SECRET_RE)},
    {"key": "markdown_links", "label": "Markdown link URLs",
     "desc": "URLs inside [text](url) markdown links",
     "fn": _re_fn(MDLINK_RE, group=1)},
    {"key": "regex", "label": "Custom regex…",
     "desc": "Extract everything matching a regex you type",
     "fn": None},
]

EXTRACTOR_BY_KEY = dict((e["key"], e) for e in EXTRACTORS)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def _load_settings():
    s = sublime.load_settings("Extractor.sublime-settings")
    return {
        "unique": bool(s.get("unique", True)),
        "sort": bool(s.get("sort", False)),
        "case_insensitive": bool(s.get("case_insensitive_dedupe", True)),
        "source": s.get("source", "auto"),
    }


def _dedupe(items, case_insensitive):
    seen = set()
    out = []
    for item in items:
        key = item.lower() if case_insensitive else item
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


# ---------------------------------------------------------------------------
# The command
# ---------------------------------------------------------------------------

# Remembers the last custom regex so it can be offered again as the default.
_last_regex = ""


class ExtractorCommand(sublime_plugin.WindowCommand):
    """Extract structured tokens from the active file into a new file.

    Run with no arguments to pick an extractor from a quick panel, or pass a
    ``kind`` argument (any registry key, e.g. ``"emails"``) to run it directly
    from a key binding or menu.
    """

    def run(self, kind=None):
        view = self.window.active_view()
        if view is None:
            sublime.status_message("Extractor: no active file")
            return

        if kind is not None:
            extractor = EXTRACTOR_BY_KEY.get(kind)
            if extractor is None:
                sublime.error_message(
                    "Extractor: unknown kind '{0}'".format(kind))
                return
            self._dispatch(view, extractor)
            return

        panel = [[e["label"], e["desc"]] for e in EXTRACTORS]

        def on_pick(index):
            if index < 0:
                return
            self._dispatch(view, EXTRACTORS[index])

        self.window.show_quick_panel(panel, on_pick)

    # -- internals ----------------------------------------------------------

    def _dispatch(self, view, extractor):
        if extractor["key"] == "regex":
            self._prompt_regex(view)
        else:
            self._emit(view, extractor["fn"],
                       extractor["label"], extractor["label"].lower())

    def _prompt_regex(self, view):
        self.window.show_input_panel(
            "Extract with regex:", _last_regex,
            lambda pattern: self._on_regex(view, pattern), None, None)

    def _on_regex(self, view, pattern):
        global _last_regex
        if not pattern:
            return
        try:
            regex = re.compile(pattern)
        except re.error as err:
            sublime.error_message(
                "Extractor: invalid regular expression\n\n{0}".format(err))
            return
        _last_regex = pattern

        def fn(text):
            out = []
            has_groups = regex.groups >= 1
            for m in regex.finditer(text):
                if has_groups:
                    val = next(
                        (g for g in m.groups() if g is not None), m.group(0))
                else:
                    val = m.group(0)
                if val:
                    out.append(val)
            return out

        self._emit(view, fn, "regex: " + pattern, "matches")

    def _source_text(self, view):
        mode = _load_settings()["source"]
        regions = [r for r in view.sel() if not r.empty()]
        if mode == "selection" or (mode == "auto" and regions):
            return "\n".join(view.substr(r) for r in regions)
        return view.substr(sublime.Region(0, view.size()))

    def _emit(self, view, fn, title, noun):
        settings = _load_settings()
        matches = fn(self._source_text(view))
        if settings["unique"]:
            matches = _dedupe(matches, settings["case_insensitive"])
        if settings["sort"]:
            matches = sorted(matches, key=lambda x: x.lower())

        if not matches:
            sublime.status_message("Extractor: no {0} found".format(noun))
            return

        self._write_output(matches, title)
        sublime.status_message(
            "Extractor: extracted {0} {1}".format(len(matches), noun))

    def _write_output(self, matches, title):
        body = "\n".join(matches) + "\n"
        new_view = self.window.new_file()
        new_view.set_name("Extracted: " + title)
        new_view.set_syntax_file("Packages/Text/Plain text.tmLanguage")
        new_view.run_command("append", {"characters": body})
