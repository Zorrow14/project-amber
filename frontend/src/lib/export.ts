/**
 * Download a chart's data (CSV) or the chart itself (PNG). Loaded on demand:
 * nothing here is in the page's first download.
 *
 * Both files carry what the frame shows around the chart - its title, caveat,
 * honesty callout, notes and source - plus where it came from, so a caveat
 * travels with the data however far the file goes. The PNG redraws the plot's
 * own SVG on a canvas (no screenshot library): its styles copied inline, its text
 * drawn by the canvas in the page's fonts, so Burmese renders as it does on screen.
 */
import type { TableSpec } from "../components/DataTable";

/** The words around a chart, as the reader sees them, in the UI language. */
export interface FigureText {
  title: string;
  subtitle: string;
  caveats: string[];
  notes: string[];
  source: string;
}

const clean = (text: string | null | undefined) => (text ?? "").replace(/\s+/g, " ").trim();

/** Whether the reader can see it: a phone-only legend is skipped on desktop, and the reverse. */
function shown(element: Element): boolean {
  return typeof element.checkVisibility === "function" ? element.checkVisibility() : !element.closest("[hidden]");
}

export function figureText(figure: HTMLElement): FigureText {
  const one = (selector: string) => clean(figure.querySelector(selector)?.textContent);
  const all = (selector: string) =>
    [...figure.querySelectorAll(selector)].filter(shown).map((el) => clean(el.textContent)).filter(Boolean);
  return {
    title: one(".chart-frame__title"),
    subtitle: one(".chart-frame__subtitle"),
    caveats: [...all("[data-caveat]"), ...all(".chart-frame__callout")],
    notes: all(".chart-frame__notes li"),
    source: one(".chart-frame__source"),
  };
}

export function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// --------------------------------------------------------------------------- //
// CSV
// --------------------------------------------------------------------------- //

const BOM = String.fromCharCode(0xfeff);

function csvCell(value: string | number | null | undefined): string {
  if (value == null || (typeof value === "number" && !Number.isFinite(value))) return "";
  const text = String(value);
  return /[",\r\n#]/.test(text) || text !== text.trim() ? `"${text.replace(/"/g, '""')}"` : text;
}

/**
 * The table as CSV: raw numbers where the table has them, a coverage column for
 * each series that tracks it, and the frame's words as leading `#` lines - read
 * it with `pandas.read_csv(path, comment="#")`. A BOM lets spreadsheets open
 * Burmese labels as UTF-8.
 */
export function tableCsv(table: TableSpec, text: FigureText, footer: string[]): string {
  const comments = [text.title, text.subtitle, ...text.caveats, ...text.notes, text.source, ...footer]
    .map(clean)
    .filter(Boolean)
    .map((line) => `# ${line}`);
  const { columns, rows } = table.data ?? table;
  const body = [columns, ...rows].map((row) => row.map(csvCell).join(","));
  return `${BOM}${[...comments, ...body].join("\r\n")}\r\n`;
}

export function exportCsv(figure: HTMLElement, table: TableSpec, footer: string[], filename: string) {
  download(new Blob([tableCsv(table, figureText(figure), footer)], { type: "text/csv;charset=utf-8" }), filename);
}

// --------------------------------------------------------------------------- //
// PNG
// --------------------------------------------------------------------------- //

const SCALE = 2;
const PAD = 24;
const SVG_PROPS = [
  "display",
  "visibility",
  "opacity",
  "fill",
  "fill-opacity",
  "stroke",
  "stroke-width",
  "stroke-dasharray",
  "stroke-dashoffset",
  "stroke-linecap",
  "stroke-linejoin",
  "stroke-opacity",
  "paint-order",
];

/** Copy each element's computed style onto the clone: an SVG drawn as an image sees no stylesheet. */
function inlineStyles(source: Element, target: Element) {
  const computed = window.getComputedStyle(source);
  const style = SVG_PROPS.map((name) => `${name}:${computed.getPropertyValue(name)}`).join(";");
  target.setAttribute("style", style);
  const from = source.children;
  const to = target.children;
  for (let i = 0; i < from.length; i++) {
    const a = from[i];
    const b = to[i];
    if (a && b) inlineStyles(a, b);
  }
}

/** One run of a chart's text, where the browser placed it, in canvas units relative to the plot. */
interface TextRun {
  text: string;
  x: number;
  y: number;
  align: CanvasTextAlign;
  matrix: DOMMatrix;
  font: string;
  fill: string;
  alpha: number;
}

/**
 * The plot's text, measured on screen. An SVG drawn as an image loads its web
 * fonts late and may paint no text at all, so the canvas draws the text itself,
 * in the page's own (loaded) fonts, at the positions the browser laid it out:
 * each run anchored where its first or last glyph sits, through its transform.
 */
function textRuns(svg: SVGSVGElement): TextRun[] {
  const box = svg.getBoundingClientRect();
  const runs: TextRun[] = [];
  for (const text of svg.querySelectorAll("text")) {
    const screen = text.getScreenCTM();
    if (!screen || !shown(text)) continue;
    const matrix = new DOMMatrix().translate(-box.left, -box.top).multiply(screen);
    const spans = [...text.querySelectorAll("tspan")];
    for (const run of spans.length > 0 ? spans : [text]) {
      const count = run.getNumberOfChars();
      const content = run.textContent?.trim() ?? "";
      if (count === 0 || !content) continue;
      const style = window.getComputedStyle(run);
      if (style.fill === "none" || style.visibility === "hidden") continue;
      const start = run.getStartPositionOfChar(0);
      const end = run.getEndPositionOfChar(count - 1);
      const anchor = style.textAnchor;
      runs.push({
        text: content,
        x: anchor === "end" ? end.x : anchor === "middle" ? (start.x + end.x) / 2 : start.x,
        y: start.y,
        align: anchor === "end" ? "right" : anchor === "middle" ? "center" : "left",
        matrix,
        font: `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`,
        fill: style.fill,
        alpha: Number(style.fillOpacity || 1) * Number(style.opacity || 1),
      });
    }
  }
  return runs;
}

function drawText(ctx: CanvasRenderingContext2D, runs: TextRun[], left: number, top: number) {
  for (const run of runs) {
    ctx.save();
    ctx.translate(left, top);
    const m = run.matrix;
    ctx.transform(m.a, m.b, m.c, m.d, m.e, m.f);
    ctx.font = run.font;
    ctx.fillStyle = run.fill;
    ctx.globalAlpha = run.alpha;
    ctx.textAlign = run.align;
    ctx.textBaseline = "alphabetic";
    ctx.fillText(run.text, run.x, run.y);
    ctx.restore();
  }
}

/** The plot's marks as an image (text removed), and its text runs to draw on top. */
async function svgImage(
  svg: SVGSVGElement,
): Promise<{ image: HTMLImageElement; width: number; height: number; text: TextRun[] }> {
  const { width, height } = svg.getBoundingClientRect();
  const text = textRuns(svg);
  const clone = svg.cloneNode(true) as SVGSVGElement;
  inlineStyles(svg, clone);
  for (const node of clone.querySelectorAll("text")) node.remove();
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.setAttribute("width", String(width));
  clone.setAttribute("height", String(height));
  const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(clone)], { type: "image/svg+xml" }));
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    return { image, width, height, text };
  } finally {
    URL.revokeObjectURL(url);
  }
}

/** Break text into lines that fit, at the language's word boundaries (Burmese has no spaces between words). */
function wrap(ctx: CanvasRenderingContext2D, text: string, width: number): string[] {
  const lang = document.documentElement.lang || "en";
  const pieces =
    typeof Intl.Segmenter === "function"
      ? [...new Intl.Segmenter(lang, { granularity: "word" }).segment(text)].map((s) => s.segment)
      : text.split(/(\s+)/);
  const lines: string[] = [];
  let line = "";
  for (const piece of pieces) {
    const next = line + piece;
    if (line.trim() === "" || ctx.measureText(next).width <= width) line = next;
    else {
      lines.push(line.trimEnd());
      line = piece.trimStart();
    }
  }
  if (line.trim()) lines.push(line.trimEnd());
  return lines;
}

interface Swatch {
  label: string;
  color: string;
  variant: string;
}

function legendSwatches(figure: HTMLElement): Swatch[] {
  return [...figure.querySelectorAll<HTMLElement>(".legend__item")].filter(shown).map((item) => {
    const swatch = item.querySelector<HTMLElement>(".legend__swatch");
    const variant = /legend__swatch--(\w+)/.exec(swatch?.className ?? "")?.[1] ?? "line";
    return { label: clean(item.textContent), color: swatch ? window.getComputedStyle(swatch).color : "", variant };
  });
}

function drawSwatch(ctx: CanvasRenderingContext2D, { color, variant }: Swatch, x: number, y: number) {
  ctx.save();
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = variant === "bold" ? 3 : 2;
  ctx.lineCap = variant === "dotted" ? "round" : "butt";
  ctx.setLineDash(variant === "dashed" ? [5, 3] : variant === "dotted" ? [0.5, 4] : []);
  ctx.beginPath();
  if (variant === "band") {
    ctx.globalAlpha = 0.25;
    ctx.fillRect(x, y - 4, 20, 8);
  } else if (variant === "hollow") {
    ctx.arc(x + 10, y, 4, 0, Math.PI * 2);
    ctx.stroke();
  } else if (variant === "hatch") {
    ctx.rect(x, y - 6, 20, 12);
    ctx.clip();
    ctx.beginPath();
    ctx.lineWidth = 1.5;
    for (let i = -12; i < 20; i += 4) {
      ctx.moveTo(x + i, y + 6);
      ctx.lineTo(x + i + 12, y - 6);
    }
    ctx.stroke();
  } else if (variant === "bracket") {
    ctx.moveTo(x, y - 4);
    ctx.lineTo(x, y + 4);
    ctx.lineTo(x + 20, y + 4);
    ctx.lineTo(x + 20, y - 4);
    ctx.stroke();
  } else {
    ctx.moveTo(x, y);
    ctx.lineTo(x + 20, y);
    ctx.stroke();
  }
  ctx.restore();
}

/**
 * The chart as a PNG at twice its on-screen size: title, subtitle, caveat tags,
 * legend, plot, notes, source and the export line. Null when the plot has not
 * rendered yet.
 */
export async function figurePng(figure: HTMLElement, footer: string[]): Promise<Blob | null> {
  const svgs = [...figure.querySelectorAll<SVGSVGElement>(".chart-frame__plot svg.recharts-surface")].filter(shown);
  if (svgs.length === 0) return null;
  const plots = await Promise.all(svgs.map(svgImage));
  const text = figureText(figure);
  const legend = legendSwatches(figure);
  const colorOf = (selector: string, fallback: string) => {
    const el = figure.querySelector(selector);
    return el ? window.getComputedStyle(el).color : fallback;
  };
  const frame = window.getComputedStyle(figure);
  const font = frame.fontFamily;
  const ink = { background: frame.backgroundColor, title: colorOf(".chart-frame__title", "#000") };
  const second = colorOf(".chart-frame__subtitle", ink.title);
  const third = colorOf(".chart-frame__source", second);
  const pill = figure.querySelector("[data-caveat], .chart-frame__callout .pill");
  const pillStyle = pill ? window.getComputedStyle(pill) : null;
  const width = Math.max(480, ...plots.map((p) => p.width)) + PAD * 2;
  const inner = width - PAD * 2;
  // Burmese stacks glyphs above and below the line: it needs more leading, as on screen.
  const leading = document.documentElement.lang === "my" ? 1.25 : 1;

  // Lay out once to measure, then draw the same steps onto a canvas of that height.
  const steps: ((ctx: CanvasRenderingContext2D) => void)[] = [];
  const measure = document.createElement("canvas").getContext("2d");
  if (!measure) return null;
  let y = PAD;
  const paragraph = (value: string, size: number, weight: number, color: string, lineHeight: number) => {
    if (!value) return;
    measure.font = `${weight} ${size}px ${font}`;
    for (const line of wrap(measure, value, inner)) {
      const top = y;
      steps.push((ctx) => {
        ctx.font = `${weight} ${size}px ${font}`;
        ctx.fillStyle = color;
        ctx.fillText(line, PAD, top + size);
      });
      y += Math.round(lineHeight * leading);
    }
  };

  paragraph(text.title, 16, 600, ink.title, 22);
  y += 2;
  paragraph(text.subtitle, 13, 400, second, 19);
  if (text.caveats.length > 0) {
    // The caveat tags, as on screen: a row of pills, wrapping as needed.
    y += 8;
    measure.font = `500 12px ${font}`;
    let x = PAD;
    let row = 0;
    for (const caveat of text.caveats) {
      const lines = wrap(measure, caveat, inner - 20);
      const w = Math.min(inner, Math.max(...lines.map((l) => measure.measureText(l).width)) + 20);
      const line = Math.round(16 * leading);
      const h = lines.length * line + 8;
      if (x > PAD && x + w > PAD + inner) {
        x = PAD;
        y += row + 6;
        row = 0;
      }
      const left = x;
      const top = y;
      steps.push((ctx) => {
        ctx.fillStyle = pillStyle?.backgroundColor ?? ink.background;
        ctx.strokeStyle = pillStyle?.borderTopColor ?? third;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.roundRect(left + 0.5, top + 0.5, w - 1, h - 1, 11);
        ctx.fill();
        ctx.stroke();
        ctx.font = `500 12px ${font}`;
        ctx.fillStyle = pillStyle?.color ?? ink.title;
        lines.forEach((l, i) => ctx.fillText(l, left + 10, top + 4 + line * (i + 0.75)));
      });
      x += w + 6;
      row = Math.max(row, h);
    }
    y += row + 12;
  }
  if (legend.length > 0) {
    y += 4;
    measure.font = `400 12px ${font}`;
    let x = PAD;
    for (const item of legend) {
      const w = 28 + measure.measureText(item.label).width;
      if (x > PAD && x + w > PAD + inner) {
        x = PAD;
        y += 20;
      }
      const left = x;
      const top = y;
      steps.push((ctx) => {
        drawSwatch(ctx, item, left, top + 8);
        ctx.font = `400 12px ${font}`;
        ctx.fillStyle = second;
        ctx.fillText(item.label, left + 28, top + 12);
      });
      x += w + 18;
    }
    y += 28;
  }
  for (const plot of plots) {
    const top = y;
    steps.push((ctx) => {
      ctx.drawImage(plot.image, PAD, top, plot.width, plot.height);
      drawText(ctx, plot.text, PAD, top);
    });
    y += plot.height + 8;
  }
  y += 8;
  for (const note of text.notes) paragraph(note, 12, 400, second, 17);
  paragraph(text.source, 11, 400, third, 16);
  y += 6;
  const rule = y;
  steps.push((ctx) => {
    ctx.fillStyle = third;
    ctx.globalAlpha = 0.4;
    ctx.fillRect(PAD, rule, inner, 1);
    ctx.globalAlpha = 1;
  });
  y += 8;
  for (const line of footer) paragraph(line, 11, 400, third, 16);
  y += PAD - 8;

  const canvas = document.createElement("canvas");
  canvas.width = Math.ceil(width * SCALE);
  canvas.height = Math.ceil(y * SCALE);
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.scale(SCALE, SCALE);
  ctx.fillStyle = ink.background;
  ctx.fillRect(0, 0, width, y);
  ctx.textBaseline = "alphabetic";
  for (const step of steps) step(ctx);
  return new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
}

export async function exportPng(figure: HTMLElement, footer: string[], filename: string): Promise<boolean> {
  const blob = await figurePng(figure, footer);
  if (!blob) return false;
  download(blob, filename);
  return true;
}
