# Dashboard & Visualization Style Guide

When creating interactive dashboards and visualization pages for your site, follow the **Stratum dashboard** as the canonical template.

## Color Palette

Use these CSS variables (defined in `:root`):

```css
--bg:       #0d1117;      /* Dark background */
--surface:  #161b22;      /* Card/section background */
--border:   #21262d;      /* Borders and dividers */
--accent:   #06b6d4;      /* Cyan accent (primary) */
--accent2:  #22d3ee;      /* Light cyan (highlights) */
--teal:     #14b8a6;      /* Teal accent */
--green:    #10b981;      /* Success/status */
--red:      #f43f5e;      /* Errors/exceptions */
--yellow:   #f59e0b;      /* Warnings/highlights */
--violet:   #7c3aed;      /* Secondary accent */
--text:     #e6edf3;      /* Main text */
--muted:    #8b949e;      /* Secondary text */
--card-bg:  #11192a;      /* Deep card background */
```

## Layout Structure

All dashboards follow this vertical structure:

```
┌─────────────────────────────────────┐
│ HERO SECTION                        │
│ - Badge (status indicator)          │
│ - H1 title (with accent span)       │
│ - Descriptive subtitle              │
│ - Action links (GitHub, etc)        │
│ - Stats bar (4 metric cards)        │
└─────────────────────────────────────┘
│ MAIN CONTAINER (padding: 40px)      │
├─────────────────────────────────────┤
│ SECTION 1 (metric/chart)            │
│ - Section header (title + desc)     │
│ - Chart or data visualization       │
├─────────────────────────────────────┤
│ SECTION 2 (table/comparison)        │
│ - Data table with syntax            │
├─────────────────────────────────────┤
│ SECTION N (additional content)      │
└─────────────────────────────────────┘
```

## Hero Section

**Component: `.hero`**

- Background: gradient from `#0d1117` → `#042a35` → `#0d1117` (135deg)
- Contains radial gradient glows (cyan/teal with low opacity)
- Padding: 56px top, 40px sides, 40px bottom
- Border-bottom: 1px solid `var(--border)`

**Badge: `.hero-badge`**

- Background: rgba(6,182,212,.15)
- Border: 1px solid rgba(6,182,212,.4)
- Text: uppercase, 11px, letter-spacing .08em
- Pseudo-element `::before` shows green dot status
- Animation: fadeUp .6s ease (staggered with others)

**Title: `<h1>`**

- Font-size: clamp(28px, 4vw, 48px)
- Font-weight: 800
- Use `<span>` for `color: var(--accent2)` highlight
- Animation: fadeUp .6s ease .1s both

**Subtitle: `.hero-sub`**

- Color: `var(--muted)`
- Font-size: 15px
- Code blocks use cyan background + border
- Animation: fadeUp .6s ease .2s both

**Links: `.hero-links a`**

- Border: 1px solid `var(--border)`
- Hover: border-color → `var(--accent)`, color → `var(--accent2)`
- Transition: all .2s

**Stats Bar: `.stats-bar`**

- Grid: 4 equal columns with 1px gaps
- Each `.stat` card:
  - Label: uppercase, 11px, muted
  - Value: 32px, 800 weight, accent2 color
  - Unit: 14px, muted
  - Hover: background changes to rgba(6,182,212,.08)

## Main Sections

**Container: `.container`**

- Max-width: 1400px
- Margin: 0 auto
- Padding: 40px

**Section: `.section`**

- Background: `var(--surface)`
- Border: 1px solid `var(--border)`
- Border-radius: 16px
- Padding: 28px 32px
- Margin-bottom: 48px
- Animation: fadeUp .6s ease (staggered)

**Section Header: `.section-header`**

- Title: uppercase 11px, letter-spacing .12em, color accent2
- Has pseudo-element `::before` (20px cyan line)
- H2: 22px, 700 weight
- Description: 14px, muted, max-width 800px

## Charts

**Wrapper: `.chart-wrap`**

- Position: relative
- Height: 380px (use `.tall` for 460px)
- Margin-top: 24px

**Chart.js Configuration:**

- Font: 'Inter', system-ui
- Text color: `#e6edf3`
- Grid color: rgba(33, 38, 45, 0.5)
- Border colors: Use accent or accent2 for primary, red/yellow for exceptions
- Animation: smooth transitions on hover

**Layout:**

- Single column: full width chart
- Two columns: `.two-col` grid (1fr 1fr, gap 24px)
- Responsive: single column on < 800px

## Tables

**Element: `table.cmp`**

- Width: 100%
- Font-size: 13px
- Border-collapse: collapse

**Header Styling: `th`**

- Color: `var(--muted)`
- Font-weight: 600
- Font-size: 11px
- Text-transform: uppercase
- Letter-spacing: .06em
- Background: transparent (no bg color, let section color show)

**Cell Styling: `td`**

- Padding: 10px 12px
- Border-bottom: 1px solid `var(--border)`
- Text-align: right (except first column)
- Font-variant-numeric: tabular-nums

**Highlighted Rows: `tr.hl`**

- Background: rgba(6,182,212,.06)
- First cell: color accent2, font-weight 600

**Special Values:**

- `.star`: color yellow (for best performers, etc)

## Animations

All fade-in animations use the same keyframe:

```css
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}
```

Apply to hero elements with staggered delay:
- Badge: .0s
- Title: .1s
- Subtitle: .2s
- Links: .2s (same as subtitle, together)
- Stats bar: .3s

Apply to sections with .6s ease both, no delay (they render after hero).

## Typography

- Font: 'Inter' from Google Fonts (weights: 300, 400, 500, 600, 700, 800)
- Fallback: system-ui, -apple-system, sans-serif
- Base: 14px, line-height: 1.6

**Sizes:**

- H1: clamp(28px, 4vw, 48px) — responsive
- H2: 22px, letter-spacing -.01em
- Labels: 11px, uppercase, letter-spacing .08em
- Body: 14-15px
- Code: 12px, monospace

## Responsive Design

- Container: max-width 1400px
- Hero: padding adjusts at 40px sides
- Two-column grid: 1fr 1fr at desktop, 1fr at < 800px
- Stats bar: 4 columns responsive (natural flow on mobile)
- Charts: 100% width, height fixed or relative

## Code Blocks

- Background: rgba(6,182,212,.12)
- Border: 1px solid rgba(6,182,212,.25)
- Border-radius: 4px
- Padding: 1px 6px
- Font: 'SF Mono', 'Fira Code', monospace
- Font-size: 12px
- Color: var(--accent2)

## Back Links & Navigation

- Style: `.back-link`
- Color: var(--accent2)
- Font-size: 13px
- Font-weight: 500
- Hover: text-decoration: underline
- Display: flex with gap 6px for arrow

## Implementation Checklist

When building a new dashboard:

- [ ] Define :root CSS variables (copy from Stratum)
- [ ] Create hero section with gradient and glows
- [ ] Add hero-badge with status indicator
- [ ] Use fadeUp animations with staggered delays
- [ ] Create stats-bar with 4 key metrics
- [ ] Build main sections with proper header structure
- [ ] Use Chart.js for visualizations
- [ ] Style tables with .cmp class
- [ ] Use two-column layouts for multiple charts
- [ ] Test responsive design at 800px breakpoint
- [ ] Ensure dark theme consistency
- [ ] Verify animation performance

## Example Section

```html
<div class="section">
  <div class="section-header">
    <div class="section-title">§1 Metric Name</div>
    <h2>Descriptive Title</h2>
    <div class="section-desc">
      Explanation of what this section shows.
    </div>
  </div>
  <div class="chart-wrap">
    <canvas id="myChart"></canvas>
  </div>
</div>
```

## Files Using This Style

- `stratum-dashboard.html` ← **CANONICAL TEMPLATE**
- `leap-dashboard.html` ← Reference implementation
- Future dashboards should follow this guide

---

**Last updated:** 2026-09-06
**Canonical reference:** stratum-dashboard.html
