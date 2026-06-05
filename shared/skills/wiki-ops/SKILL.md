---
name: wiki-ops
description: >
  LLM wiki operations: ingest raw sources into structured wiki pages, query the
  wiki with synthesized answers, and lint for stale/orphaned content. Use when
  working inside an llm-wiki project directory — for ingest ("process this
  source", "add this to the wiki"), query ("what does the wiki say about X"),
  or maintenance ("lint the wiki", "find orphan pages").
---

# Wiki Ops

Universal workflow skill for LLM-maintained wikis. The per-wiki `AGENTS.md`
holds domain context; this skill holds the operational procedures.

---

## Boot (run at session start)

```
1. read index.md                          — orient to existing wiki content
2. ctx_index(path: "wiki/", source: "wiki-<name>")  — load pages into FTS5
3. read last entry of log.md              — check what was done most recently
```

The `<name>` in the source label should match the wiki's domain (e.g., `wiki-openamdet`).

---

## Ingest workflow

Triggered by: "ingest this", "add this source", "process [file/URL]"

### Steps

**Read the source**
- If a file path: use `read` (for files you will reference by exact text later)
  or `ctx_execute_file` (for large files where you only need a summary)
- If a URL: use `ctx_fetch_and_index(url, source: "raw-<slug>")`, then
  `ctx_search` to extract key content
- If a repository: read `README.md`, key source files, and any docs/ directory;
  use `ctx_batch_execute` to gather multiple files in parallel

**Discuss with user (interactive)**
- Summarize the 3–5 most important takeaways
- Ask: "Anything you want to emphasize or de-emphasize before I write the pages?"
- Note any contradictions with existing wiki content you spotted while reading

**Write the source summary page**
- Path: `wiki/sources/<slug>.md`
- Frontmatter: `tags: [source]`, `created`, `updated`, `sources: 1`
- Sections: Summary, Key Takeaways, Cross-references, Raw Source

**Update entity and concept pages (run in parallel)**
- For each entity or concept touched by the source:
  - If the page exists: read it, then edit to integrate new information;
    note any contradiction with existing claims using a `> ⚠️ Contradiction:` blockquote
  - If the page doesn't exist: create it with the standard frontmatter
- Use `subagent(tasks: [...], concurrency: 4)` to update multiple pages in parallel
  when there are 3+ pages to update and the updates are independent

**Update `wiki/overview.md`**
- Add the new source to the source count
- Revise the Summary if the new source shifts the overall picture
- Add/update any Open Questions the source raises or answers

**Update `index.md`**
- Add an entry for each new page created (link + one-line description)
- Update the entry for any existing page that changed significantly

**Append to `log.md`**
- Format: `## [YYYY-MM-DD] ingest | <source title>`
- Include: pages created (N), pages updated (N), any contradictions flagged

---

## Query workflow

Triggered by: direct questions about wiki content

### Steps

1. `ctx_search(queries: ["<question terms>"], source: "wiki-<name>")` — find
   relevant pages (batch multiple angle queries in one call)
2. Read the top 2–3 pages in full if snippets are insufficient
3. Synthesize an answer with `[[page]]` citations
4. Ask: "Should I save this as a wiki page?" — if yes, write to an appropriate
   path (e.g., `wiki/concepts/` or a new `wiki/analyses/` subdirectory)
5. If saved: update `index.md` and append to `log.md` as
   `## [YYYY-MM-DD] query | <question summary>`

---

## Lint workflow

Triggered by: "lint the wiki", "health check", "find orphan pages"

### Steps

1. `ctx_index(path: "wiki/", source: "wiki-<name>")` — ensure FTS5 is current
2. Run `ctx_execute` to scan for structural issues:

```javascript
// find pages with no outbound wikilinks
const fs = require('fs');
const path = require('path');

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap(e =>
    e.isDirectory() ? walk(path.join(dir, e.name)) : path.join(dir, e.name)
  );
}

const pages = walk('wiki').filter(f => f.endsWith('.md'));
const allSlugs = new Set(pages.map(f => path.basename(f, '.md')));

const report = pages.map(f => {
  const content = fs.readFileSync(f, 'utf8');
  const outbound = [...content.matchAll(/\[\[([^\]]+)\]\]/g)].map(m => m[1]);
  const broken = outbound.filter(s => !allSlugs.has(s.toLowerCase().replace(/ /g, '-')));
  const isOrphan = !pages.some(other => {
    if (other === f) return false;
    return fs.readFileSync(other, 'utf8').includes(`[[${path.basename(f, '.md')}]]`);
  });
  return { file: f, outbound: outbound.length, broken, orphan: isOrphan };
});

console.log('=== broken links ===');
report.filter(r => r.broken.length).forEach(r =>
  console.log(`${r.file}: broken → ${r.broken.join(', ')}`)
);

console.log('\n=== orphan pages (no inbound links) ===');
report.filter(r => r.orphan && !r.file.includes('overview') && !r.file.includes('index'))
  .forEach(r => console.log(r.file));

console.log('\n=== pages with no outbound links ===');
report.filter(r => r.outbound === 0).forEach(r => console.log(r.file));
```

3. `ctx_search` for contradiction markers: `ctx_search(queries: ["Contradiction", "⚠️"])`
4. Check `index.md` for pages not listed (run a diff between index entries and actual files)
5. Report findings grouped by: broken links, orphans, contradictions, index gaps
6. Ask user which issues to fix automatically vs. flag for human review
7. Append to `log.md` as `## [YYYY-MM-DD] lint | N issues found, N fixed`

---

## index.md format

The index is organized by category. Each entry is one line:

```markdown
## Entities
- [[entity-slug]] — one-line description

## Concepts
- [[concept-slug]] — one-line description

## Sources
- [[source-slug]] — Title (YYYY-MM-DD ingested)

## Analyses
- [[analysis-slug]] — question or topic this page addresses
```

Update the index on every ingest and every time a query result is saved as a page.

---

## log.md format

Append-only. One `##` entry per operation. Parseable with:

```bash
grep "^## \[" log.md | tail -10   # last 10 operations
grep "ingest" log.md               # all ingests
```

Entry format:
```markdown
## [YYYY-MM-DD] ingest | Source Title
- Pages created: N (list them)
- Pages updated: N (list them)
- Contradictions flagged: N
```

---

## Wrap-up (mandatory after every ingest)

Before ending any session that created or modified wiki pages:

1. **Verify page count** — must match `index.md` header:
   ```bash
   find wiki -name "*.md" | wc -l   # must equal "Pages: N" in index.md
   ```
2. **Update `index.md`** — correct the `Pages:` count and add entries for any
   new pages under the appropriate section header
3. **Append to `log.md`** — one `##` entry per ingest/operation performed
4. **Commit** — the user may ask for atomic commits; group by logical ingest unit

Do not skip these steps even if the user has not asked for them. The index header
comment says "Updated by wiki-ops on every ingest" — honour it on every ingest.

---

## Conventions

- Never modify files in `raw/` — read only
- Prefer updating an existing page over creating a new one for minor new info
- Flag contradictions inline with `> ⚠️ Contradiction: <description>` rather than
  silently overwriting the old claim
- Keep source pages lean (summary + citations); put synthesis on entity/concept pages
- When unsure whether to create a new page, err toward updating the overview and
  adding an Open Question — let the wiki grow organically
