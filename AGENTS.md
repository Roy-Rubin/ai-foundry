# Repository collaboration rules

- When the user asks to plan first, prepare the plan and wait for their approval before implementing it.
- Get explicit user approval before pushing commits or updating branches on a remote. This applies to Git commands, APIs, and pushes performed while preparing or updating a pull request.
- Approval to plan, edit files, or commit locally does not authorize a push. Approval for one push is limited to the commits and branch covered by that request.
- When push approval is missing, keep authorized work local and tell the user what is ready to push.

## Implementation conventions

- Prefer object-oriented design and classes throughout new code. Model components with clear responsibilities and use composition to connect them.
- Write Google-style docstrings for every new class, function, and method. Document arguments, return values, and raised exceptions where applicable. Include step comments in each function and method to explain its logical stages.
- Use descriptive, readable variable names. Avoid short names and unclear abbreviations.
- Use targeted try/except blocks where operations can fail and the code can recover, clean up, or add useful context. Catch specific exceptions and preserve the original cause when raising a new exception.
- Assign the result of a function or method call to a clearly named variable before returning it. For example, use `report = renderer.render(papers)` followed by `return report`.
- Add explicit type annotations for all new variables, attributes, function and method parameters, and return values, including `None` returns.
