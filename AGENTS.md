# Agent instructions

- This repo is public. Never commit machine-specific paths, private hostnames, internal repo names, usernames or tokens. Examples use placeholders (`<owner>/<repo>`, `example.com`).
- One folder per skill; the folder name equals the frontmatter `name:`. Add a row to `README.md` for every new skill.
- Skills are agent-agnostic: say "the agent", not a product name, unless the text is about a literal CLI agent id.
- Scripts are Python 3 stdlib only and must run on Windows, macOS and Linux: no `rsync`/`tar`/shell pipelines, always pass `encoding="utf-8"`.
- Validate before pushing: `npx skills add . -l`.
