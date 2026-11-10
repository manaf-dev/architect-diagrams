# Contributing

Thanks for helping improve the architecture-diagrams skill. Bug reports, new examples, icon fixes and
script improvements are all welcome.

## Reporting a problem

Open an issue with:

- what you asked the agent, or the spec you ran;
- what came out (attach the PNG if you can) and what you expected;
- your agent (Claude Code, Codex, Cursor…), OS and Python version.

For a wrong or missing icon, include the output of
`python skills/architecture-diagrams/scripts/icons.py search "<name>"`.

## Making a change

1. Fork the repo and create a branch from `main`.
2. Make your change (see the sections below).
3. Build and lint every example, as CI does:

   ```bash
   cd skills/architecture-diagrams
   for spec in examples/*.yaml; do python scripts/archdiagram.py "$spec" --out-dir /tmp/out; done
   ```

4. Open a pull request against `main`. Describe what changed and why, and attach a rendered PNG for anything
   that changes how diagrams look.

`main` only accepts changes through pull requests, and the **examples** check must pass before a PR can be
merged.

## Adding an example

Examples live in `skills/architecture-diagrams/examples/` and double as starting templates for the agent.

- Use a made-up system with generic names. Don't submit diagrams of a real company's or client's systems.
- Resolve every icon with `icons.py search` / `icons.py show` first; never guess a reference.
- Follow `references/design-rules.md`: one main row, bands above and below, an 8 px grid.
- Lint must come back clean. If you accept a remaining finding, explain why in a comment at the top of the
  spec (see `azure-web-app.yaml`).
- Render it and look at it: `python scripts/render.py out/<name>.drawio out/<name>.png`.
- Add a `credits:` line naming the icon sets you used.
- List the new example in the "Write the spec" step of `SKILL.md`.

## Changing the scripts

- Keep them to Python 3.10+ and the standard library. PyYAML is the only optional extra.
- Keep the agent workflow in `SKILL.md` in step with any change to a script's commands or options.

## Icons and licensing

- Contributions are released under the repo's [MIT licence](LICENSE).
- Don't commit vendor icon files. The skill references icons from their published sources; the bundled
  catalogs only index them.
- A new icon source needs a licence that allows use in diagrams. Add it to
  [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and `references/icon-sources.md`.
