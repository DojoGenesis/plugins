---
name: figma-to-code
description: Bridge between Figma MCP server and code generation. Extract design tokens, component structure, and layout from Figma nodes, then generate framework-specific code (HTML, Svelte, React, Vue). Use when the user shares a Figma URL or asks to implement a design. Trigger phrases: "implement this figma design", "convert figma to code", "extract tokens from figma", "build this component from the design", "generate HTML from figma".
license: Adapted from nafiurrahmanniloy/figma-skill (MIT)
---

# Figma to Code

---

## I. Philosophy: Design Intent Over Pixel Copying

The goal is not to reproduce every pixel from Figma — it is to capture the *design intent* (spacing rhythm, color relationships, typographic hierarchy) and express it in idiomatic code for the target framework. A good conversion reads like a developer wrote it with the design open, not like a screenshot was OCR'd into divs.

---

## II. When to Use This Skill

Use when:
- User shares a Figma URL and wants code generated
- Building HTML kits that should match an existing Figma design
- Extracting design tokens (colors, spacing, typography) from a Figma file
- Need to verify implementation fidelity against a Figma source

Do NOT use when:
- User wants to CREATE a Figma design from code (use `use_figma` MCP tool directly)
- Design is a screenshot, not a Figma file (use manual CSS instead)

---

## III. Workflow

### Step 1: Resolve Figma Context

Extract `fileKey` and `nodeId` from the Figma URL.
Call `get_design_context` MCP tool with these parameters.
This returns: reference code, screenshot, component metadata, and Code Connect mappings.

### Step 2: Extract Design Tokens

From the design context, extract:
- **Colors**: hex values, CSS custom properties, semantic names
- **Typography**: font families, sizes, weights, line heights
- **Spacing**: padding, margin, gap values
- **Border radius**: corner radius values
- **Shadows**: box-shadow definitions
- **Layout**: flex/grid structure, auto-layout direction and gap

If DESIGN.md files are available in `HTMLCraftStudio/templates/design-systems/`, cross-reference tokens against the closest matching design system.

### Step 3: Generate Framework Code

Based on user's target framework:

| Framework | Output |
|-----------|--------|
| HTML/CSS | Semantic HTML + CSS custom properties + utility classes |
| Svelte | `.svelte` component with scoped styles |
| React | TSX component with Tailwind or CSS modules |
| Vue | SFC with `<script setup>` and scoped styles |

Rules:
- Use semantic HTML elements (`nav`, `section`, `article`, `button`) not generic divs
- Extract repeated patterns as sub-components
- Use CSS custom properties for design tokens, not hardcoded values
- Preserve auto-layout as flexbox/grid, not absolute positioning

### Step 4: Verify Fidelity

Compare generated code against the Figma screenshot:
- Layout structure matches
- Typography hierarchy preserved
- Color relationships correct
- Spacing rhythm consistent
- Interactive states accounted for (hover, focus, active)

---

## IV. Best Practices

1. **Tokens first, components second.** Extract the design token set before generating any component code.
2. **Respect the component boundary.** If Figma shows a component with variants, generate one component with props — not multiple separate components.
3. **Use existing design system tokens when available.** Check `HTMLCraftStudio/templates/design-systems/` for matching DESIGN.md files before inventing new token names.
4. **Preserve accessibility.** Add `aria-label`, `role`, and proper heading hierarchy even if not explicit in the Figma design.
5. **Generate mobile-first.** Start with the smallest breakpoint and add `@media` queries for larger sizes.

---

## V. Quality Checklist

- [ ] Design tokens extracted and documented as CSS custom properties
- [ ] Semantic HTML used throughout (no div soup)
- [ ] Layout uses flexbox/grid matching Figma auto-layout
- [ ] Typography hierarchy preserved (h1 > h2 > h3 > p)
- [ ] Colors reference token variables, not hardcoded hex
- [ ] Component is responsive (mobile-first)
- [ ] Accessibility attributes present

---

## VI. Related Skills

- `canvas-design` — Visual artifact generation
- `theme-factory` — Styling toolkit for HTML pages
- `artifacts-builder` — HTML artifact scaffolding
