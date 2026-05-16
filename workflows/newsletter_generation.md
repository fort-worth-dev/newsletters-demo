# Workflow: Newsletter Generation

## Objective
Given a topic, produce a polished HTML newsletter with data-driven charts and deliver it to an inbox.

## Required Inputs
- **topic** (required): The subject of the newsletter. Be specific — "AI agents in enterprise software" beats "AI".
- **to** (required for delivery): Recipient email address.
- **tone** (optional): e.g. "technical and direct" / "executive summary" / "beginner-friendly". Defaults to professional/informative.

## Required API Keys (in `.env`)
```
PERPLEXITY_API_KEY=pplx-...
ANTHROPIC_API_KEY=sk-ant-...
RESEND_API_KEY=re_...
RESEND_FROM=Newsletter <you@yourdomain.com>   # optional, defaults to Resend sandbox
```

---

## Tool Execution Sequence

### Step 1 — Research
```bash
python tools/01_research.py --topic "AI agents in enterprise software"
```
- Calls Perplexity `sonar-pro`
- **Caching**: If `.tmp/research_{slug}.json` exists and is < 24 hours old, the API call is skipped automatically. Use `--force` to bypass.
- Output: `.tmp/research_{slug}.json`

### Step 2 — Structure Content
```bash
python tools/02_structure_content.py --research-file .tmp/research_ai_agents_in_enterprise_software.json
```
- Calls `claude-haiku-4-5` to convert research into newsletter schema
- Validates JSON schema before writing; retries once on invalid output
- Output: `.tmp/content_{slug}.json`

### Step 3 — Generate Charts
```bash
python tools/03_generate_charts.py --content-file .tmp/content_ai_agents_in_enterprise_software.json
```
- Reads `key_stats[]` from content JSON
- Generates a horizontal bar chart (all stats) and up to 3 stat cards
- Output: `.tmp/charts_{slug}/chart_bar.png`, `chart_stat_1.png`, etc.

### Step 4 — Render HTML
```bash
python tools/04_render_html.py \
  --content-file .tmp/content_ai_agents_in_enterprise_software.json \
  --charts-dir .tmp/charts_ai_agents_in_enterprise_software
```
- Loads Jinja2 template, embeds charts as base64 data URIs, inlines CSS via premailer
- Output: `.tmp/newsletter_{slug}_{YYYYMMDD}.html`

**Template development (zero API cost):**
```bash
python tools/04_render_html.py --dry-run
```
Uses `tools/fixtures/sample_content.json` and no charts. Fast iteration on visual design.

### Step 5 — Send Email
```bash
python tools/05_send_email.py \
  --html-file .tmp/newsletter_ai_agents_in_enterprise_software_20250515.html \
  --to rob.zey@gmail.com
```
- Sends via Resend API
- Subject auto-derived from filename if `--subject` not provided
- Prints Resend message ID to stdout

---

## Newsletter Content JSON Schema

`02_structure_content.py` validates that output matches this schema before writing:

```json
{
  "headline": "string",
  "subheadline": "string",
  "sections": [
    {
      "title": "string",
      "body": "string (paragraphs separated by \\n\\n)",
      "stat_callout": "string or null"
    }
  ],
  "key_insight": "string",
  "key_stats": [
    { "label": "string", "value": number, "unit": "string" }
  ],
  "cta": "string"
}
```

**Critical constraint:** `key_stats[].value` must be a numeric type (int or float), never a string like `"67%"`. The chart generator will fail if this is a string. The structuring tool validates this and will retry if violated.

---

## Error Handling

| Error | Cause | Fix |
|---|---|---|
| Perplexity returns no citations | Topic too vague or too recent | Add a year or specifics to the topic; use `--force` to retry |
| `json.JSONDecodeError` in step 2 | Claude added markdown fences despite instructions | Script strips fences automatically and retries once |
| `key_stats value must be numeric` | Claude returned `"67%"` instead of `67` | Script retries with schema reminder; check the retry log |
| `matplotlib display backend error` | Missing `Agg` backend call | `matplotlib.use('Agg')` is at top of `03_generate_charts.py` — do not move it |
| `Gmail clips email` warning | HTML > 102 KB (base64 charts inflate size) | Reduce chart count or image width; charts are 600px max by default |
| Resend `403` or `domain not verified` | Sending from unverified domain | Use `onboarding@resend.dev` as FROM for testing; verify your domain in Resend dashboard for production |

---

## Rate Limits
- **Perplexity `sonar-pro`**: 50 requests/min. Not a concern for single newsletter runs.
- **Anthropic `claude-haiku-4-5`**: 50 requests/min tier-1. Not a concern.
- **Resend free tier**: 3,000 emails/month, 100/day.

---

## Known Quirks

1. **Outlook CSS**: The template uses `<table>` layout intentionally. Outlook (desktop) ignores `display: flex`, `grid`, and `border-radius`. Do not add flexbox or grid to the template.
2. **Gmail 102 KB clip**: Gmail silently clips HTML emails over ~102 KB. The renderer warns you if the output exceeds 100 KB. Base64 encoding inflates PNG size by ~33%.
3. **Perplexity `citations` field**: The `citations` array is at the response root, separate from `choices[0].message.content`. Both are captured in step 1.
4. **WSL2 display**: `matplotlib.use('Agg')` must appear before any other matplotlib import. This is already correct in `03_generate_charts.py`.
5. **Font fallback**: If DejaVu Sans `.ttf` files are not found, stat cards fall back to PIL's default font (smaller, bitmap). Install with `sudo apt install fonts-dejavu` if cards look degraded.

---

## Cost Tracking

All API calls append to `.tmp/token_usage.json`. After several runs:
```bash
python tools/show_costs.py   # prints a summary table (not yet created — add when needed)
```

Or inspect directly:
```bash
cat .tmp/token_usage.json
```

---

## Self-Improvement Notes
*(Update this section when you discover new constraints or better approaches)*

- If Perplexity's `sonar-pro` raises quality concerns on niche topics, try adding "as of 2025" to the research prompt to anchor recency.
- If chart stat cards look too plain, `03_generate_charts.py` uses Pillow — add a subtle drop shadow via `ImageFilter.GaussianBlur` on a shadow layer.
- The Jinja2 template's color palette is defined as CSS variables in the `<style>` block. To change the newsletter's color scheme, update the six hex values in `newsletter.html.j2` and the `PALETTE` dict in `03_generate_charts.py` to match.
