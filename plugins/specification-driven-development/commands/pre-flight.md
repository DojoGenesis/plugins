---
description: Runs the pre-implementation checklist. Use before spec handoff.
---

# /pre-flight — Run the Pre-Implementation Checklist

**Argument hint:** `<path to specification or prompt>`

## Workflow

### Step 1: Read the Document

Read the specification or implementation prompt provided by the user. If no file is provided, ask for it.

### Step 2: Run the Checklist

Evaluate each item. For each failing check, explain what is missing and suggest a specific fix.

#### 1. Objective Clarity
- [ ] **Single clear objective?** The document has one unambiguous sentence stating what will be built.

#### 2. File & Endpoint Integrity
- [ ] **All referenced files/endpoints exist or are flagged as "to create"?** Every file path and API endpoint mentioned in the document either exists in the codebase or is explicitly listed in the file manifest as a new file.

#### 3. Code Quality
- [ ] **TypeScript/Go/Python types are real, not pseudocode?** All type definitions, interfaces, and structs use valid language syntax and could compile.

#### 4. Success Criteria
- [ ] **Success criteria are binary (pass/fail)?** Every criterion can be evaluated as TRUE or FALSE. No criteria use words like "improved", "better", "enhanced", or "optimized" without a specific threshold.

#### 5. File Manifest Completeness
- [ ] **File manifest is complete?** Every file mentioned anywhere in the document text appears in the file manifest. No files are referenced in requirements but missing from the manifest.

#### 6. Dependency Explicitness
- [ ] **Dependencies are explicit?** npm/pip/go packages, API versions, framework versions, and external service dependencies are listed with version numbers.

#### 7. Rollback Plan
- [ ] **Rollback plan exists?** There is a documented procedure for undoing the changes if something goes wrong.

#### 8. Testing Specificity
- [ ] **Testing requirements are specific?** The testing section names specific test files, coverage targets, and scenarios — not just "write tests."

#### 9. Integration Points
- [ ] **Integration points are documented with both sides defined?** For every integration point, both the provider and consumer are documented with matching interfaces.

#### 10. Constraint Boundaries
- [ ] **Constraints are explicit?** There is a clear "do not" list specifying what the implementer must NOT do (no refactoring unrelated code, no new dependencies, etc.).

### Step 3: Produce Verdict

Count passing and failing checks:

- **PASS** (10/10): All checks pass. Ready for implementation.
- **PASS WITH WARNINGS** (7-9/10): Minor gaps that should be addressed but don't block implementation. List the warnings.
- **FAIL** (<7/10): Significant gaps that will cause implementation problems. List all failures with suggested fixes. Do NOT proceed until failures are resolved.

### Step 4: Present Report

Format the report as:

```
## Pre-Flight Report: [Document Name]

**Verdict:** PASS / PASS WITH WARNINGS / FAIL

### Results
- [x] Single clear objective
- [x] All files/endpoints accounted for
- [ ] FAIL: Types use pseudocode (lines 45-60)
...

### Required Fixes (if any)
1. [Specific fix with line reference]
2. [Specific fix with line reference]
```
