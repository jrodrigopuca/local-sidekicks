#!/bin/sh
# External verification for change-react-component: typecheck, the fixture's
# own tests, and the oracle tests the model never saw. Run from the fixture.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
cp "$HERE/cart.oracle.test.tsx" src/components/__oracle__.test.tsx
npx tsc --noEmit; TSC=$?
npx vitest run; VT=$?
rm -f src/components/__oracle__.test.tsx
echo "typecheck exit $TSC"
[ "$TSC" -eq 0 ] && [ "$VT" -eq 0 ]
