# YAML frontmatter traps in SKILL.md

The `skills` CLI parses SKILL.md frontmatter with a **strict YAML parser**.
Malformed frontmatter means the skill is skipped: the install reports
`Found N skills` with N lower than expected.

## The validator (run this before every push)

```bash
npx skills add <path-to-clone> -l
```

It installs nothing. For each bad file it prints a `⚠ Skipped <path> — …` line
with the parse error, line and column, or the missing field. Your skill must
appear under `Available Skills`. No extra Python packages needed.

## Trap 1 — colon-space inside an unquoted scalar

```yaml
description: Foo bar. Especially important: trigger proactively at the end ...
```

YAML reads `important: trigger ...` as a mapping key/value pair, not as part of
the description. The CLI reports `Nested mappings are not allowed in compact
mappings`.

**Fix**: replace `: ` with ` — `, `, ` or `. `:
```yaml
description: Foo bar. Especially important — trigger proactively at the end ...
```

Or use a block scalar for the whole description:
```yaml
description: |
  Foo bar. Especially important: trigger proactively at the end ...
```

**Watch for**: `note:`, `important:`, `e.g.:`, `Example:`, `Tip:`, `Warning:`,
`Use case:`, `Trigger:`, `Goal:` — anything followed by a space inside an
unquoted description.

**Safe colons**: tokens with no space after the colon (`git@github.com:owner/repo`,
`https://`, `~/.agents/`).

## Trap 2 — BOM (byte-order mark)

A SKILL.md saved with a UTF-8 BOM (`\xef\xbb\xbf` at the start) no longer
starts with `---`, so the frontmatter is not detected.

Detect, then strip:
```bash
python3 -c "import sys; print(open(sys.argv[1],'rb').read(3))" <path>/SKILL.md      # want b'---'
python3 -c "import sys; p=sys.argv[1]; b=open(p,'rb').read(); open(p,'wb').write(b.lstrip(b'\xef\xbb\xbf'))" <path>/SKILL.md
```

Common causes: Windows Notepad, and PowerShell 5 `Set-Content` / `Out-File`.

## Trap 3 — multiline scalar without an indicator

```yaml
description: This is a description
that wraps onto a second line
without a continuation indicator.
```

This either errors or silently truncates the description at the first line.
Fixes:

- **One physical line**: keep it long. Renderers wrap it visually.
- **Folded scalar** (`>`): line breaks become spaces.
- **Literal block scalar** (`|`): line breaks preserved.

## Trap 4 — quotes and backticks

Quotes inside an unquoted scalar are literal, and backticks are never special,
so `User said "install X"` is fine. A description that **starts** with a quote
or backtick is not: YAML then expects the whole value to be quoted. Start with
a word.

## Trap 5 — leading whitespace on the closing `---`

The closing `---` must be at column 0. Common when copy-pasting between editors
with different indentation defaults.

## Trap 6 — `name:` does not match the folder

Not a YAML error, but the same symptom: the CLI installs and selects by the
frontmatter `name:`, so `-s <folder-name>` reports `No matching skills found`.
Keep them equal.
