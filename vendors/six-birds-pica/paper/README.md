# Paper Workspace

This directory contains a minimal LaTeX manuscript scaffold for the project paper.

## Requirements

- A LaTeX distribution (`pdflatex`)
- `latexmk` recommended (optional but preferred)

## Build

From the repository root:

```bash
make -C paper
```

Or explicitly:

```bash
make -C paper pdf
```

If `latexmk` is available, the Makefile uses it automatically. Otherwise it falls back to two `pdflatex` passes.

## Clean

```bash
make -C paper clean
```

## Output

The built PDF is written to:

- `paper/main.pdf`
