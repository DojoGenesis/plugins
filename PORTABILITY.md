# Portability Summary: dojo-genesis → AgenticGateway

**Audit Date:** 2026-02-12
**Status:** ✅ High Portability Confirmed
**Full Audit:** `AgenticStackOrchestration/phases/04-behavior/skill-portability-audit.md`

---

## Executive Summary

The dojo-genesis ecosystem (44 skills, 7 plugins, 7 agents) is **91% portable** to the AgenticGateway runtime with existing or minimal tooling.

### Portability by Tier

| Tier | Skills | % | Status |
|------|--------|---|--------|
| **Tier 1: Fully Portable** | 28 | 64% | ✅ Ready (needs file system tools only) |
| **Tier 2: Needs Adapters** | 12 | 27% | ⏳ Needs web tools + script execution |
| **Tier 3: Needs Abstraction** | 4 | 9% | ⏳ Needs skill invocation interface |
| **Tier 4: Claude-Specific** | 0 | 0% | N/A |

**Key Insight:** Zero skills are fundamentally Claude-specific. All skills are capability-agnostic and tool-based.

---

## What Makes These Skills Portable?

### 1. Tool-Based Design
Skills describe *what tools to use*, not *how Claude implements them*. The gateway just needs to provide the same tool primitives.

### 2. No UI Dependencies
Skills don't rely on Cowork-specific rendering (artifacts, computer:// links, plan mode UI). All outputs are files or structured data.

### 3. No Model-Specific Behaviors
Skills don't depend on Claude's specific reasoning patterns, multimodal capabilities, or prompt engineering quirks. Any sufficiently capable LLM can execute them.

### 4. Agent Definitions are Runtime-Agnostic
Agent YAML format describes *what* tools/skills an agent needs, not *how* Cowork implements them. Direct mapping to gateway's agent model.

---

## What the Gateway Needs to Provide

### Tier 1: File System Tools (64% of skills)
```
Read, Write, Edit, Glob, Grep, Bash (git operations)
```
**Status:** Gateway has these (Phase 1).

### Tier 2: Adapter Tools (27% of skills)
```
WebSearch, WebFetch (web research)
ExecuteScript (Python/Shell scripts with allowlist)
```
**Status:** Needs MCP server (Phase 3) + script execution implementation (Phase 4).

### Tier 3: Skill Invocation (9% of skills)
```
InvokeSkill(skillName, args) - Meta-skills calling other skills
```
**Status:** Needs abstraction design (Phase 4).

**Recommendation:** Register skills as tools in the gateway's tool registry. The `InvokeSkill` tool looks up and calls registered skill functions.

---

## Plugin-by-Plugin Breakdown

| Plugin | Skills | Tier 1 | Tier 2 | Tier 3 | Portability |
|--------|--------|--------|--------|--------|-------------|
| agent-orchestration | 4 | 4 | 0 | 0 | 100% (file system only) |
| continuous-learning | 8 | 6 | 2 | 0 | 75% Tier 1, 25% needs web tools |
| skill-forge | 4 | 2 | 1 | 1 | 50% Tier 1, 25% Tier 2, 25% Tier 3 |
| specification-driven-development | 10 | 8 | 0 | 2 | 80% Tier 1, 20% Tier 3 |
| strategic-thinking | 5 | 4 | 0 | 1 | 80% Tier 1, 20% Tier 3 |
| system-health | 8 | 6 | 1 | 1 | 75% Tier 1, 12.5% Tier 2, 12.5% Tier 3 |
| wisdom-garden | 5 | 4 | 1 | 0 | 80% Tier 1, 20% Tier 2 |

---

## Agent Compatibility

All 7 agent definitions are **100% compatible** with the gateway's agent model.

| Agent | Plugin | Tools Needed | Gateway Status |
|-------|--------|--------------|----------------|
| coordinator | agent-orchestration | Read, Write, Grep, Glob | ✅ Ready |
| researcher | continuous-learning | Read, Grep, Glob, WebSearch, WebFetch, Bash | ⏳ Needs web tools |
| forger | skill-forge | Read, Write, Edit, Grep, Glob, Bash | ✅ Ready |
| specifier | specification-driven-development | Read, Grep, Glob, Bash, Write | ✅ Ready |
| scout | strategic-thinking | Read, Grep, Glob, WebSearch, WebFetch | ⏳ Needs web tools |
| health-auditor | system-health | Read, Grep, Glob, Bash | ✅ Ready |
| gardener | wisdom-garden | Read, Write, Edit, Grep, Glob | ✅ Ready |

**Mapping:**
- `tools` → Gateway tool allowlist
- `model` → Gateway LLM provider selection
- `memory` → Gateway memory scope (project/user)
- `skills` → Preloaded skill set (skills registered as tools)

---

## External Dependencies

### Scripts (7 total)
1. `init_skill.py` - Skill initialization (skill-creation)
2. `suggest_seeds.py` - Seed recommendation (seed-library)
3. `apply_seed.py` - Seed application (seed-library)
4. `diff_tracker.py` - Change tracking (repo-context-sync)
5. `context_mapper.py` - Context compression (repo-context-sync)
6. `smart_clone.sh` - Sparse checkout (repo-context-sync)

### External Tools (1 total)
1. `lychee` - Link checking (documentation-audit)

**Gateway Requirement:** `ExecuteScript` tool with allowlist for these 7 scripts + 1 binary.

---

## Porting Effort Estimate

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| 4.1 Foundation | 2 weeks | 5 Tier 1 skills running on gateway (proof-of-concept) |
| 4.2 Adapters | 2 weeks | Web tools + script execution implemented, 3 Tier 2 skills working |
| 4.3 Abstractions | 2 weeks | Skill invocation interface, 4 Tier 3 meta-skills working |
| 4.4 Full Ecosystem | 2 weeks | All 44 skills + 7 agents ported and validated |
| 4.5 Documentation | 1 week | Gateway skill development guide, migration docs |
| **Total** | **9 weeks** | **44 skills, 7 agents, full behavioral layer** |

---

## Key Decisions Needed

### 1. Skill Invocation Mechanism (Tier 3)
**Options:**
- **A.** DAG subtask creation (heavyweight orchestration)
- **B.** Skill registry + direct function calls (lightweight, tool-like)
- **C.** Workflow definition language (declarative)

**Recommendation:** **Option B** (aligns with gateway tool architecture, minimal overhead).

### 2. Web Tool Implementation (Tier 2)
**Options:**
- **A.** Native gateway tools (compiled in)
- **B.** MCP server tools (external, pluggable)

**Recommendation:** **Option B** (separation of concerns, requires Phase 3 MCP server).

### 3. Script Execution Security (Tier 2)
**Options:**
- **A.** Full sandbox (containerized)
- **B.** Allowlist-only (pre-approved scripts)

**Recommendation:** **Option B** (simpler, sufficient for known scripts).

---

## Migration Checklist

When porting skills to the gateway:

**For Tier 1 Skills:**
- [ ] Read SKILL.md YAML frontmatter
- [ ] Register skill as tool in gateway tool registry
- [ ] Test skill invocation with file system tools
- [ ] Validate output matches expected format

**For Tier 2 Skills:**
- [ ] Ensure web tools or script execution is available
- [ ] Add script to allowlist if needed
- [ ] Test web search/fetch or script execution
- [ ] Validate skill works end-to-end

**For Tier 3 Meta-Skills:**
- [ ] Refactor skill invocations to use gateway's `InvokeSkill` tool
- [ ] Test sub-skill invocation chains
- [ ] Verify circular invocation prevention
- [ ] Validate full workflow executes correctly

**For Agents:**
- [ ] Map agent YAML to gateway agent config
- [ ] Ensure all required tools are available
- [ ] Register agent's skill set
- [ ] Test agent invocation with sample task

---

## Success Criteria

The port is complete when:

- [ ] All 44 skills are registered in gateway tool registry
- [ ] All 7 agents can be invoked via gateway API
- [ ] Smoke tests pass for all skills (basic invocation)
- [ ] Integration tests pass for 10 critical skills (full workflows)
- [ ] No skill invocation errors in gateway logs
- [ ] Skill development guide allows creating new skills for gateway
- [ ] Migration guide enables porting additional Cowork skills

---

## Why This Matters

**Behavioral portability is the crown jewel of the agentic stack.**

These 44 skills represent:
- **Institutional knowledge** — patterns refined through real use
- **Reusable capabilities** — behaviors that work across projects
- **Quality standards** — A+ skill template ensures consistency
- **Ecosystem effects** — skills compose and invoke each other

Porting them to the gateway means:
- **AgenticGateway is not just a runtime** — it's a capable agent platform from day one
- **Skills run anywhere** — Cowork, gateway, future runtimes
- **Knowledge compounds** — new skills build on existing patterns
- **Platform moat** — 44 production-ready capabilities is a competitive advantage

---

## Next Steps

1. ✅ **Portability audit complete** (this document)
2. ⏳ **Update `AgenticStackOrchestration/STATUS.md`** with findings
3. ⏳ **Write `contracts/gateway-skills.md`** (skill development contract for gateway)
4. ⏳ **Begin Phase 4.1** (port 5 Tier 1 skills as proof-of-concept)

---

**Conclusion:** The ecosystem is ready for porting. The gateway just needs to provide the tool primitives, and the skills will run.

For full technical details, see the complete audit in `AgenticStackOrchestration/phases/04-behavior/skill-portability-audit.md`.
