# Web search and cited answers

Jarvis uses a self-hosted SearXNG JSON endpoint:

```bash
export JARVIS_SEARCH_URL=https://search.example.com
jarvis web-search "query" --limit 8
jarvis "research this current topic and cite the sources"
```

SearXNG controls the underlying engines. It may enable Google, Bing, Brave, or
other sources without adding a paid search dependency to Jarvis.

For requests that appear time-sensitive, the local agent attempts web search.
It can then fetch public HTTP(S) pages for more evidence. Results are
deduplicated, bounded, normalized by `jarvis-agent-core`, and retain their
source URLs. Web text is always marked untrusted and cannot grant permissions
or redefine the task.

The fetcher resolves hosts and rejects non-global IP addresses to reduce SSRF
risk. It also checks redirect targets, limits downloads to 2 MiB, and truncates
model-visible text. The current standalone fetcher supports HTML and plain
text; PDF extraction is a future feature.

Search is evidence retrieval, not a truth guarantee. Prefer primary sources,
compare independent sources for consequential claims, and do not use the tool
as the sole authority for medical, legal, financial, or safety-critical action.
