# Contributing to ATML

Thanks for stopping by. ATML 1.0.0 is small on purpose.

## Ground rules

1. **Spec first.** `ATML_LANGUAGE_GUIDE.md` is the source of truth. If the compiler
   and the guide disagree, the guide wins — fix the compiler.
2. **Don't break 1.0 files.** `<atml version="1.0.0">` files must keep compiling.
3. **One-file output stays dependency-free.** The emitted `.html` must run from
   `file://` with no network.
4. **Examples must build.** Every `examples/*.atml` must pass `./atml check` and
   `build` in CI.

## Workflow

```bash
./atml check examples/
python3 -m unittest discover -s tests -v
```

Open a PR with: what changed, a runnable `.atml` snippet, and the `check`/`build`
output. Keep PRs small.
