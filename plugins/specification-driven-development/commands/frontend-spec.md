---
description: Writes a backend-grounded frontend spec. Use when speccing UI.
---

# /frontend-spec — Write a Frontend Spec Grounded in Backend Architecture

**Argument hint:** `<frontend feature to specify>`

Load the `frontend-from-backend` skill before proceeding.

## Workflow

### Step 1: Backend Grounding First

Before writing a single line of frontend spec:

- **If ~~repository is connected:** Read the backend codebase — API endpoints, data models, authentication flow, error handling patterns.
- **Otherwise:** Ask the user to describe or provide the backend architecture.

Document every backend API the frontend will consume:
- Method, path, request/response types
- Auth requirements, rate limits
- Error codes and error response shapes

Map the backend data model to frontend state shapes.

### Step 2: Gather Frontend Preferences

Ask the user about:
- Target framework (React, Vue, Svelte, etc.)
- Design system or component library
- Routing approach
- State management preferences (Redux, Zustand, Context, etc.)

### Step 3: Draft Frontend Specification

The spec MUST include all of these sections:

1. **Backend Integration Map** — Table of every API call the frontend makes, with method, path, request body, response body, auth, and error handling
2. **Component Architecture** — Component tree with props/state for each component
3. **State Management** — Stores, contexts, or hooks with TypeScript interfaces for all state shapes
4. **Route Structure** — Paths, layouts, guards, and loading states
5. **UI Components** — For each component: purpose, props interface, internal state, API calls it makes, loading/error states
6. **Integration Points** — SSE/WebSocket connections, real-time updates, optimistic UI patterns

### Step 4: Save

Save as `[version]_frontend_spec_[feature].md` in the workspace.

## Critical Rules

- The frontend spec MUST reference actual backend endpoints by name, not invented ones.
- If the backend doesn't have an endpoint the frontend needs, flag it as a **"Backend Prerequisite"** — do not silently invent endpoints.
- Every component must document its loading state, error state, and empty state.
- State shapes must be TypeScript interfaces, not prose descriptions.
- The backend is the source of truth. If the frontend design conflicts with the backend API, the frontend design must adapt.
