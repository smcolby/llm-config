---
name: polars
description: >
  Polars 1.x conventions: expression-first style, lazy pipelines with
  scan/collect, strict-schema I/O, and renamed pre-1.0 APIs. Apply when
  writing or reviewing polars DataFrame or LazyFrame code, expressions,
  or data pipelines built on polars.
tier: requested
scope: ["**/*.py"]
stack: ["polars>=1.0"]
reviewed: 2026-06
---

You are an expert in data manipulation with polars 1.x.

## Principles

1. Think in expressions over columns, never in Python loops over rows.
2. Pipelines are lazy by default: scan, compose, `collect` once.
3. Schemas are explicit; polars is strict and that strictness is the feature.

## Directives

- Build transformations from `pl.col` expressions inside `select`/`with_columns`/`filter`; name derived columns with `.alias` or keyword syntax.
- For files and pipelines, prefer `pl.scan_csv`/`scan_parquet` plus a single `.collect()` over eager `read_*`, so the optimizer sees the whole plan.
- `map_elements` (Python UDF) is a last resort; check for a native expression first, and accept that a UDF forfeits parallelism and optimization.
- Use `when/then/otherwise` expression chains for conditionals, never row-wise apply.
- Declare `schema_overrides` at read time rather than casting downstream; handle nulls with expression methods (`fill_null`, `is_null`), never NaN sentinels.
- Interoperate via `.to_pandas()`/`from_pandas` only at library boundaries; do not flip back and forth mid-pipeline.

## Anti-hallucination

| Banned | Correct |
|---|---|
| `df.groupby(...)` (pre-1.0 name) | `df.group_by(...)` |
| `.apply(f)` on frames/series | `.map_elements(f)` (and prefer native expressions) |
| `with_column` (singular) | `with_columns` |
| `pl.count()` in aggregations | `pl.len()` |
| pandas idioms (`df["a"][0] = x`, index-based access) | expression API; polars has no index |
