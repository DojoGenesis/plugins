#!/usr/bin/env bash
# normalize-skill.sh — Normalizes a community SKILL.md to Dojo-compatible format.
# Usage: ./normalize-skill.sh <input-skill.md> [output-skill.md]
# If output is omitted, writes to stdout.
set -euo pipefail

INPUT="$1"
OUTPUT="${2:-/dev/stdout}"

if [[ ! -f "$INPUT" ]]; then
    echo "Error: File not found: $INPUT" >&2
    exit 1
fi

python3 - "$INPUT" "$OUTPUT" << 'PYTHON_SCRIPT'
import sys
import re
import os

def parse_frontmatter(content):
    """Extract YAML frontmatter and body from a SKILL.md file."""
    if not content.startswith('---'):
        return {}, content

    end = content.find('---', 3)
    if end == -1:
        return {}, content

    fm_text = content[3:end].strip()
    body = content[end+3:].strip()

    # Simple YAML parsing (handles flat and nested)
    fm = {}
    current_key = None
    current_list = None

    for line in fm_text.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        # Handle list items
        if stripped.startswith('- ') and current_list is not None:
            current_list.append(stripped[2:].strip().strip('"').strip("'"))
            continue

        # Handle key: value
        if ':' in stripped:
            key, _, val = stripped.partition(':')
            key = key.strip()
            val = val.strip()

            if key == 'metadata':
                continue  # Skip nested metadata wrapper

            if val == '':
                # Start of a list or nested block
                current_key = key
                current_list = []
                fm[key] = current_list
            else:
                fm[key] = val.strip('"').strip("'")
                current_key = key
                current_list = None

    return fm, body


def extract_triggers(description):
    """Extract trigger phrases from description text."""
    # Pattern 1: Explicit "Trigger phrases: ..."
    match = re.search(r'[Tt]rigger\s+phrases?:\s*(.+?)(?:\.|$)', description)
    if match:
        raw = match.group(1)
        triggers = [t.strip().strip('"').strip("'") for t in raw.split(',')]
        return [t for t in triggers if t]

    # Pattern 2: Quoted phrases in description
    quoted = re.findall(r'"([^"]{3,50})"', description)
    if len(quoted) >= 2:
        return quoted[:5]

    # Pattern 3: Generate from first sentence
    first_sentence = description.split('.')[0].strip()
    if len(first_sentence) > 10:
        return [first_sentence.lower()]

    return ["invoke this skill"]


def infer_tier(fm, body):
    """Infer tier from tool dependencies and body content."""
    deps = fm.get('tool_dependencies', [])
    if isinstance(deps, str):
        deps = [deps]

    # Check for meta-skill indicators
    if any(kw in body.lower() for kw in ['meta-skill', 'invokes other skills', 'invoke_skill', 'sub-skill']):
        return 3

    # Check for script dependencies
    if any(kw in body.lower() for kw in ['python_scripts', 'shell_scripts', 'scripts/']):
        return 2

    # Check for tool dependencies
    if deps or any(kw in body.lower() for kw in ['file_system', 'bash', 'web_tools', 'execute_script']):
        return 2

    # Prompt-only
    return 1


def normalize(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    fm, body = parse_frontmatter(content)

    # Validate minimum required fields
    name = fm.get('name', '')
    description = fm.get('description', '')

    if not name:
        print(f"SKIP: No 'name' field in {input_path}", file=sys.stderr)
        sys.exit(1)

    if not description:
        print(f"SKIP: No 'description' field in {input_path}", file=sys.stderr)
        sys.exit(1)

    # Extract or infer missing fields
    triggers = fm.get('triggers', [])
    if isinstance(triggers, str):
        triggers = [triggers]
    if not triggers:
        triggers = extract_triggers(description)

    tier = fm.get('tier', '')
    if not tier:
        tier = infer_tier(fm, body)
    else:
        tier = int(tier)

    agents = fm.get('agents', [])
    if isinstance(agents, str):
        agents = [agents]
    if not agents:
        agents = ['primary']

    # Ensure triggers are in description (Dojo convention)
    trigger_text = ', '.join(f'"{t}"' for t in triggers[:5])
    if 'trigger' not in description.lower():
        description = description.rstrip('.')
        description += f'. Trigger phrases: {trigger_text}.'

    # Build normalized frontmatter
    license_text = fm.get('license', 'Complete terms in LICENSE.txt')

    output_lines = ['---']
    output_lines.append(f'name: {name}')
    output_lines.append(f'description: {description}')
    output_lines.append(f'license: {license_text}')
    output_lines.append('---')
    output_lines.append('')
    output_lines.append(body)

    result = '\n'.join(output_lines)

    if output_path == '/dev/stdout':
        print(result)
    else:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"OK: {name} (tier={tier}, triggers={len(triggers)}, agents={agents})", file=sys.stderr)


if __name__ == '__main__':
    normalize(sys.argv[1], sys.argv[2])
PYTHON_SCRIPT
