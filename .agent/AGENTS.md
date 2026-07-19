# Project-Scoped Rules

## Multi-Repository Maintenance

When instructed to perform updates, checks, or refactors across multiple repositories in the manifest:
1. **Parallel Delegation**: Instead of performing updates sequentially in the main orchestrator context, use the `invoke_subagent` tool to spawn a separate subagent for each target repository.
2. **Context Isolation**: Pass the `cruft_resolution` skill to each subagent so they can perform the worktree cloning, updating, testing, and PR creation independently in their own isolated context.
3. **Aggregation**: Monitor the subagents, wait for them to finish, and compile a single summary report with the PR links for the user.
