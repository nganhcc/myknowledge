# AGENTS.md

## Project Overview

This proect implements a multi-tenant Retrieval-Augmented Generation (RAG) platform that enables users to upload documents, ask queries, and receive streaming answers with precise source citations.

## Engineering Principles

- Prefer the smallest change that correctly solves the requested problem.
- Read existing code and follow established patterns before introducing new abstractions.
- Prefer simple, explicit code over clever or speculative abstractions.
- Do not refactor unrelated code while implementing a feature or fix.
- Reuse existing utilities, services, repositories, and infrastructure when appropriate.
- Keep functions and classes focused on a single responsibility.
- Prefer clear names and straightforward control flow.
- Avoid premature optimization; optimize only when there is evidence of a bottleneck.
- Preserve existing behavior unless the task explicitly requires changing it.

## Architecture

- Preserve the existing architectural boundaries.
- Keep business logic independent from infrastructure concerns where practical.
- Do not access the database directly from controllers.
- Do not put business logic in controllers.
- Keep external services behind explicit interfaces or adapters when the existing architecture uses them.
- Do not introduce a new architectural pattern unless the existing design cannot reasonably support the requirement.

## Dependencies

- Prefer existing dependencies over adding new libraries.
- Before adding a dependency, check whether the project already provides equivalent functionality.
- Do not add dependencies for trivial functionality that can be implemented clearly with the standard library.
- When adding a dependency, use the latest project-compatible version and verify its license and security implications.
- Do not replace an existing library without a concrete technical reason.

## Updating This File

When working on the project:

- If you encounter a mistake, unexpected behavior, or project-specific convention that could cause another agent to make the same mistake, inform the developer about it.
- If the issue is confirmed and generally useful for future work, update this file with a concise entry explaining: What was misunderstood or went wrong, The correct behavior, How future agents should avoid the mistake
- Do not add temporary, task-specific, or speculative information.
- Keep this file concise and organized. Prefer updating an existing section over creating duplicate entries.

## Testing

- Test behavior the application actually owns.
- Start with fast static checks available in the project (formatting, linting, compilation, and type-checking).
- Run the smallest test relevant to the change.
- Expand to integration tests when the change crosses component or infrastructure boundaries.
- Reserve the full test suite for release gates or changes with broad impact.
- Run tests sequentially by default unless parallel execution is known to be safe.
- Use E2E, race, load, and stress tests intentionally.
- Never retry failures blindly. Read the failure evidence first.
- Fix the root cause instead of masking or weakening tests.
- Never weaken tests just to make CI green.
