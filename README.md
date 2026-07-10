<h1 align="center">🔎 Extractor</h1>

<p align="center">
  <em>Pull every email, URL, IP, date, UUID, secret — or anything a regex can match —
  out of the current file and into a fresh, de-duplicated one.</em>
</p>

<p align="center">
  <img alt="Sublime Text" src="https://img.shields.io/badge/Sublime%20Text-3%20%7C%204-orange?logo=sublimetext&logoColor=white">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.3%2B-blue?logo=python&logoColor=white">
  <img alt="Platform" src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey">
  <img alt="Dependencies" src="https://img.shields.io/badge/dependencies-none-brightgreen">
</p>

---

Logs, configs, dumps and docs are full of buried structure. **Extractor** scrapes
it out in one command: choose *what* to pull, and it collects every match from the
file (or your selection), removes duplicates, and opens the results in a new tab —
ready to save, sort or paste elsewhere.

## ✨ Features

- 🎯 **22 built-in extractors** — from emails to Luhn-checked credit-card numbers
- 🧩 **Custom regex** — type any pattern; capture groups are honored
- 🧹 **De-duplicated output**, optionally case-insensitive and/or sorted
- ✂️ **Whole file or selection** — your choice, configurable
- 🖱️ **Everywhere** — Command Palette, Tools menu, and right-click
- 📦 **Zero dependencies** — pure Python standard library
- 🐍 **ST3 & ST4** — runs on both plugin hosts

## 🚀 Usage

1. Open the **Command Palette** (`Ctrl/Cmd + Shift + P`).
2. Run **`Extractor: Extract to new file…`**.
3. Pick what to extract. Done — the matches open in a new tab.

Prefer fewer clicks? Every extractor also has:

- a **direct** Command Palette entry, e.g. `Extractor: Emails`
- an item under **Tools → Extractor**

> 💡 By default Extractor reads the whole file, or just your selection when you
> have one. Change this under *Preferences → Package Settings → Extractor → Settings*.

### Bind a key

Any extractor can be bound directly by passing its `kind`:

```json
{ "keys": ["ctrl+alt+e"], "command": "extractor", "args": { "kind": "emails" } }
```

Omit `args` to open the picker.

## 🧰 What it can extract

| Extractor            | Matches                                                          |
| -------------------- | --------------------------------------------------------------- |
| **Emails**           | `user@host.tld`                                                 |
| **URLs**             | `http`, `https`, `ftp` and `www.` links                        |
| **Domains**          | Registrable root domains (`example.co.uk`)                     |
| **Hostnames**        | Fully-qualified host names and `localhost`                     |
| **IPv4 addresses**   | Dotted-quad addresses (`192.168.0.1`)                          |
| **IPv6 addresses**   | Colon-hex addresses (`::1`, `fe80::…`)                         |
| **Ports**            | Port numbers from `host:port` references                       |
| **Phone numbers**    | International / local numbers (heuristic)                      |
| **Dates**            | ISO, numeric and month-name dates                              |
| **Times**            | Clock times, optional seconds and AM/PM                        |
| **Timestamps**       | ISO 8601, syslog and Unix-epoch timestamps                     |
| **File paths**       | Unix, Windows and UNC paths                                    |
| **UUIDs**            | RFC 4122 UUIDs / GUIDs                                          |
| **MAC addresses**    | Ethernet hardware addresses                                    |
| **Hex colors**       | `#rgb` and `#rrggbb`                                            |
| **Numbers**          | Integers and decimals (thousands-aware)                        |
| **Hashtags**         | `#hashtag`                                                      |
| **Mentions**         | `@handle`                                                       |
| **Credit cards**     | 13–19 digit numbers that pass the Luhn check                   |
| **Secrets & API keys** | AWS / Google / GitHub / Slack keys, JWTs, PEM private keys    |
| **Markdown links**   | URLs inside `[text](url)`                                       |
| **Custom regex…**    | Everything matching a pattern you type                         |

## 📦 Installation

### Package Control (recommended)

1. Open the Command Palette and run **Package Control: Install Package**.
2. Search for **Extractor** and press <kbd>Enter</kbd>.

### Manual install

1. In Sublime Text, open **Preferences → Browse Packages…**.
2. Create a folder named `Extractor`.
3. Copy the contents of this repository into it.
4. Restart Sublime Text, or run **Tools → Developer → Reload Plugins**.

## ⚙️ Settings

`Preferences → Package Settings → Extractor → Settings`

```json
{
    "unique": true,                  // drop duplicate matches
    "case_insensitive_dedupe": true, // "Example.com" == "example.com"
    "sort": false,                   // keep first-seen order (true = sort A→Z)
    "source": "auto"                 // "auto" | "selection" | "file"
}
```

## ⚠️ Notes on accuracy

Extraction from free-form text is inherently heuristic. A few deliberate trade-offs:

- **Domains / hostnames** are gated to a curated list of common TLDs, so
  `main.py` and `README.md` are *not* mistaken for hosts. Exotic TLDs are best
  captured with the **Custom regex** extractor.
- **Phone numbers** require a `+` prefix or grouping separators; bare digit runs
  (which are indistinguishable from IDs or timestamps) are skipped.
- **File paths** containing spaces are captured up to the first space.
- **Numbers** is intentionally broad and will match digits inside IPs, dates, etc.

## 🤝 Contributing

Issues and pull requests are welcome — new extractors, better patterns, and test
cases especially.

## 📄 License

Released under the [MIT License](LICENSE).
