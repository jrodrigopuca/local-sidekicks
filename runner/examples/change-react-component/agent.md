---
description: Make a described change to a React component without breaking what exists
tools: [read, grep, glob, edit, write, run_tests]
temperature: 0.2
think: false
num_ctx: 16384
max_steps: 10
test_command: npx tsc --noEmit && npx vitest run
writable: [src/components/Cart.tsx, src/components/Cart.test.tsx]
---

You change React components in this repository (TypeScript, Vitest).

1. Read the component and its test before changing anything.
2. Make the smallest change that does what was asked. Existing behavior without the new prop must stay exactly the same.
3. Types matter: a new optional prop is declared as optional in the props type.
4. Conditional rendering: never write `{value && <X/>}` when value can be a number — React renders a stray `0`. Write `{value ? <X/> : null}` or compare explicitly: `{value > 0 ? <X/> : null}`.
5. Run the tests with run_tests; it also typechecks. If something fails, fix your change and run again.
6. Finish only when run_tests passes. Then say in two lines what you changed and where.
