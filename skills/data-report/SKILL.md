---
name: data-report
description: Build a report from data, with findings, charts and tables, as one standalone HTML file. Use when someone wants a report, an evaluation, a BI summary or charts from data in files (CSV, Excel, JSON), a database or an API.
license: Apache-2.0
compatibility: Python 3.11+. With a Chrome on the machine the check measures the page, without one it checks the file and draws pictures with weasyprint and pdftoppm when they are installed.
metadata:
  version: "1"
  geki-tags: report, charts, html, bi, data-analysis, csv, excel
  geki-category: analytics
---

# Report from data

This is advice, not a template. Structure, look and depth are yours to decide for the request and the reader. The points below keep the numbers right, the charts honest and the work short.

## How to work

1. Look at the data first: rows, columns, the period it covers, missing values, duplicate rows, impossible and extreme values. Decide what you do with each problem. The report says what you found, what you did, and how much it changes the totals.
2. Analyse, then write one script that reads the data, computes every number and writes the HTML file. To change the report, change the script and run it again.
3. Check it with `scripts/report_check.py` (below) and fix what is wrong.
4. Answer: the file, the three most important findings with their numbers, and what is uncertain.

Looking at pictures of the page is the slow part of this work. Every picture you open costs time, and most rounds after the second only polish. So: let the script find the defects, open each overview picture once, open at most three detail pictures in the whole task, and stop after two rounds of fixes. Use the pictures of the script and do not make your own screenshots or PDF pages of the report. What still bothers you after two rounds goes into your answer as a note.

## Numbers

- Every number comes out of the script: in charts, tables and sentences. Do not type a number from a tool result or from memory into the text.
- When the data only arrives in the conversation (a query tool), write each result once into a data file and let the script read it. A live source changes while you work: fix one cutoff time at the start, use it in every query, and show it as "data as of".
- Let the script assert that every breakdown sums to its total.
- A total can hide a part that moved. Before you write "stable" or "no trend", look at the measure per main group and over time together, for example delivery time per region per month.
- Show the base next to a rate, and mark a value from few cases (under about 30) as not reliable. Mark a period that is not complete and do not compare it with full ones.
- For durations and amounts use the median and a high percentile. One extreme value moves an average.
- Keep what the data shows apart from what you guess is the reason.

## Charts

- People ask for a report to see the data. Show the main findings as charts, not only as tables. One question per chart, and a title that says what it shows.
- Over time: a line, or bars for few periods. Categories: horizontal bars, sorted. Shares: sorted bars or one stacked bar. Two measures with different units: two charts, not two axes.
- Bars start at zero. A value of zero draws nothing: no minimum size. Charts that are compared share a scale. Labels carry units.
- The same thing has the same colour in every chart. About six colours at most, the rest is "Other". Never colour alone: label it.
- A scale you wrote yourself is the usual place for a mistake. Test it with the smallest and the largest value: both must land inside the chart, and the longest bar must belong to the largest value.
- A chart drawn for a wide page shrinks on a phone until nobody can read it. Let its box scroll, not the page:

```css
.chart { overflow-x: auto; }
.chart svg { min-width: 520px; width: 100%; height: auto; }
```

## The file

- One HTML file that opens offline: CSS in a `<style>` block, charts as inline SVG, system fonts, no request to another address. JavaScript only when it adds something, inline, and the report still reads without it.
- Title, period, source and data-as-of time on top. Then the summary with the most important finding first. At the end: what the data does not show and how bad rows were treated.
- A viewport meta tag, a container with a maximum width, and every wide table inside a box that scrolls sideways.
- The reader's language and number format, for example German `1.234,5` and `16.11.2026`, and always the unit.

## Check

```
python scripts/report_check.py REPORT.html --shots DIR
python scripts/report_check.py REPORT.html --shots DIR --part 1280,2500,3200
```

You do not need to read the script. The first call prints JSON:

- `problems`: what is wrong. From the file: an address outside the file, a missing value shown as `nan` or `None`, a placeholder left in the text, chart shapes drawn outside the chart area (a wrong scale: the chart looks empty). Measured in a browser at 1280 px and 390 px: sideways scrolling, chart labels that overlap or are cut off, charts too small to read. An empty list means none of these was found.
- `images`: one overview picture per width. It shows the whole page as columns, scaled down. The yellow numbers are the distance from the top in px. Look at each once for what a script cannot judge: a chart that does not match its numbers, a card alone in a row, a section that looks wrong.
- The second call writes one full-size picture between two of the yellow numbers (width, from, to). Use it when the overview shows something you cannot make out.

If you cannot open pictures, work from `problems` alone and say in your answer that nobody looked at the page.

Run the check once more after your last change. Hand over a report with an empty `problems` list, or name in your answer what is left.

When `note` says that no browser was found, the layout was not measured and the pictures come from a PDF engine. It draws inline SVG and tables like a browser, but not every CSS layout, and it shows no phone. So draw the charts as SVG, trust the pictures for charts and tables, and do not rebuild the page layout because of them.
