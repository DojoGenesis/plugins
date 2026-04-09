# /export-pdf

Export one or more files to a Pretext-typeset PDF.

## Usage

```
/export-pdf <file-or-glob> [options]
```

## Arguments

- `<file-or-glob>` — Path to a file or glob pattern (e.g., `src/**/*.ts`, `skills/*/SKILL.md`)

## Options

- `--output <path>` — Output file path (default: `./exports/<filename>.pdf`)
- `--bundle` — Combine multiple files into a single PDF with table of contents
- `--theme <light|dark>` — Color theme for syntax highlighting (default: `light`)
- `--renderer <auto|code|markdown|html|chat|structured>` — Force a specific renderer (default: `auto` detects from file extension)
- `--font-size <number>` — Body font size in points (default: `11`)
- `--line-height <number>` — Line height multiplier (default: `1.5`)
- `--page-size <letter|a4|legal>` — Page dimensions (default: `letter`)
- `--line-numbers` — Show line numbers in code exports
- `--toc` — Generate table of contents (auto-enabled with `--bundle`)
- `--disposition-typography` — Use ADA disposition mapping for chat exports

## Examples

Quick single file:
```
/export-pdf README.md
```

Code review bundle with dark theme:
```
/export-pdf src/lib/**/*.ts --bundle --theme dark --line-numbers
```

Skill reference manual:
```
/export-pdf plugins/agent-orchestration/skills/*/SKILL.md --bundle --toc --output agent-orchestration-manual.pdf
```

Chat archive with disposition typography:
```
/export-pdf conversation.json --renderer chat --disposition-typography
```

## Workflow

1. Reads specified files and detects format
2. Loads Pretext typography engine with configured fonts
3. Measures text layout using Canvas-based measurement
4. Generates PDF pages with precise glyph placement
5. Writes output to specified path

## Related Skills

- `pdf-export` — Full skill with philosophy and detailed guidance
- `pdf-typography` — Typography tuning for specific content types
