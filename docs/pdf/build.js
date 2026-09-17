// Сборка PDF-учебника «Скажи домашку»:
//   docs/tutorial.md  ->  docs/tutorial.pdf
//
// Требования: Node.js, npm install в этой папке, установленный Google Chrome
// (путь к нему берется из CHROME ниже или из env CHROME_PATH).
// Запуск: npm run build   (или node build.js)
//
// Оформление в духе учебников O'Reilly/Head First: обложка, содержание,
// открывающие «В ЭТОЙ ГЛАВЕ»-блоки, каллауты, выполнение [✎], резюме и ответы.

const fs = require("fs");
const path = require("path");
const MarkdownIt = require("markdown-it");
const hljs = require("highlight.js");
const puppeteer = require("puppeteer-core");

const CHROME =
  process.env.CHROME_PATH ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

const HERE = __dirname;
const TUTORIAL = path.join(HERE, "..", "tutorial.md");
const OUT_PDF = path.join(HERE, "..", "tutorial.pdf");
const OUT_PREVIEW = process.env.PREVIEW ? path.join(HERE, "preview.png") : null;

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function buildMd() {
  const md = new MarkdownIt({
    html: true,
    linkify: true,
    typographer: false,
    highlight: (str, lang) => {
      let codeHtml;
      let label = "text";
      if (lang && hljs.getLanguage(lang)) {
        label = lang;
        codeHtml = hljs.highlight(str, { language: lang }).value;
      } else {
        codeHtml = escapeHtml(str);
      }
      return (
        `<div class="codeblock">` +
        `<div class="code-lang">${label}</div>` +
        `<pre><code>${codeHtml}</code></pre>` +
        `</div>`
      );
    },
  });
  return md;
}

function splitFront(raw) {
  // title (first h1), front-matter blockquote, remainder
  const lines = raw.split(/\r?\n/);
  let i = 0;
  let titleLine = "";
  if (lines[0].startsWith("# ")) {
    titleLine = lines[0].slice(2).trim();
    i = 1;
  }
  while (i < lines.length && lines[i].trim() === "") i++;
  const front = [];
  const rest = [];
  let inFront = lines[i] && lines[i].startsWith(">");
  if (inFront) {
    while (i < lines.length && (lines[i].startsWith(">") || lines[i].trim() === "")) {
      front.push(lines[i]);
      i++;
    }
  }
  rest.push(...lines.slice(i));
  return { titleLine, frontMd: front.join("\n"), restMd: rest.join("\n") };
}

function buildToc(h2s) {
  const items = h2s
    .map((t, idx) => {
      const num = t.match(/Глава (\d+)/);
      const text = t.replace(/^Глава \d+\.\s*/, "").replace(/^Глава \d+:\s*/, "");
      const chip = num
        ? `<span class="toc-num">${num[1]}</span>`
        : `<span class="toc-num toc-num-muted">✦</span>`;
      return `<li><a href="#ch-${idx + 1}">${chip}${escapeHtml(text)}</a></li>`;
    })
    .join("\n");
  return `<nav class="toc"><h1 class="toc-title">Содержание</h1><ol>${items}</ol></nav>`;
}

async function main() {
  const raw = fs.readFileSync(TUTORIAL, "utf8");
  const { titleLine, frontMd, restMd } = splitFront(raw);
  const md = buildMd();

  let restHtml = md.render(restMd);
  // inject anchors into <h2>
  let counter = 0;
  restHtml = restHtml.replace(/<h2>/g, () => `<h2 id="ch-${++counter}">`);
  const h2s = [];
  for (const m of restHtml.matchAll(/<h2[^>]*>(.*?)<\/h2>/g)) {
    h2s.push(m[1].replace(/<[^>]+>/g, ""));
  }

  const frontHtml = md.render(frontMd);
  const tocHtml = buildToc(h2s);

  const coverOverline = "УЧЕБНИК&nbsp;·&nbsp;PYTHON&nbsp;·&nbsp;ВЕБ&nbsp;·&nbsp;ASYNC";
  const coverSub = "Как устроен настоящий Python-проект: от webhook до деплоя";
  const coverMeta = frontHtml;

  const html = `<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<style>
@font-face { font-family: "Noto Sans RU"; src: url("NotoSans-Regular.ttf"); font-weight: 400; }
@font-face { font-family: "Noto Sans RU"; src: url("NotoSans-Bold.ttf"); font-weight: 700; }
@font-face { font-family: "Noto Sans RU"; src: url("NotoSans-Italic.ttf"); font-weight: 400; font-style: italic; }

:root {
  --accent: #b3402c;
  --accent-light: #dcae9c;
  --ink: #232830;
  --muted: #5b6472;
  --panel: #f7f2ec;
  --code-bg: #f6f7f9;
  --line: #e2e4e8;
}

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: Georgia, "Times New Roman", serif;
  font-size: 10.4pt;
  line-height: 1.55;
  color: var(--ink);
}
p { margin: 0 0 0.55em; }
ul, ol { margin: 0.2em 0 0.7em; padding-left: 1.5em; }
li { margin: 0.18em 0; }
strong { color: #14171c; }
a { color: var(--accent); text-decoration: none; }

/* ---------- cover ---------- */
.cover {
  position: relative;
  page-break-after: always;
  min-height: 242mm;
  background: #18222e;
  color: #fff;
  border-radius: 10px;
  padding: 34mm 22mm 22mm 22mm;
  display: flex;
  flex-direction: column;
}
.cover::before {
  content: "";
  position: absolute;
  top: 24mm; left: 22mm; right: 22mm;
  border-top: 1px solid rgba(255,255,255,0.28);
}
.cover .overline {
  font-family: "Noto Sans RU", "Segoe UI", sans-serif;
  font-size: 9pt; letter-spacing: 0.32em;
  color: var(--accent-light);
  text-transform: uppercase;
}
.cover h1 {
  font-family: "Noto Sans RU", "Segoe UI", sans-serif;
  font-weight: 700;
  font-size: 40pt; line-height: 1.08;
  margin: 10mm 0 0 0;
}
.cover .subtitle {
  font-size: 15pt; color: #d9c9c2;
  margin-top: 7mm; max-width: 150mm;
}
.cover .bar {
  width: 34mm; height: 2.6mm; border-radius: 2mm;
  background: linear-gradient(90deg, #d2643d, var(--accent));
  margin: 8mm 0 0 0;
}
.cover .frontmatter {
  margin-top: auto;
}
.cover .frontmatter blockquote {
  background: rgba(255,255,255,0.06);
  border-left: 3px solid var(--accent);
  border-radius: 0 6px 6px 0;
  color: #e8eef5;
  margin: 3mm 0 0 0; padding: 4mm 6mm;
  font-size: 9.6pt;
}
.cover .frontmatter blockquote strong { color: #ffd9c8; }
.cover .cover-foot {
  margin-top: 8mm;
  font-family: "Noto Sans RU", "Segoe UI", sans-serif;
  font-size: 8.5pt; color: #93a1b3;
  border-top: 1px solid rgba(255,255,255,0.2);
  padding-top: 4mm;
}

/* ---------- TOC ---------- */
.toc { page-break-after: always; }
.toc-title {
  font-family: "Noto Sans RU", "Segoe UI", sans-serif;
  font-size: 22pt; font-weight: 700;
  color: var(--ink);
  border-bottom: 3px solid var(--accent);
  padding-bottom: 0.25em;
  margin: 0 0 0.6em 0;
}
.toc ol { list-style: none; padding: 0; margin: 0; }
.toc li { margin: 0.42em 0; }
.toc a { color: var(--ink); display: flex; align-items: baseline; gap: 10px; }
.toc-num {
  font-family: "Noto Sans RU", "Segoe UI", sans-serif;
  font-weight: 700; color: #fff;
  background: var(--accent);
  border-radius: 5px;
  padding: 0.05em 0.55em;
  font-size: 9.5pt; flex: 0 0 auto;
}
.toc-num-muted { background: #98a1ad; }

/* ---------- headings ---------- */
h2 {
  font-family: "Noto Sans RU", "Segoe UI", sans-serif;
  font-weight: 700;
  font-size: 17.5pt;
  color: #1d2431;
  page-break-before: always;
  border-bottom: 2.5px solid var(--accent);
  padding-bottom: 0.28em;
  margin: 0 0 0.55em 0;
  line-height: 1.25;
}
h2:first-of-type { page-break-before: auto; }
h3 {
  font-family: "Noto Sans RU", "Segoe UI", sans-serif;
  font-weight: 700;
  font-size: 12.6pt;
  color: #7a2c1a;
  margin: 1.15em 0 0.35em 0;
  page-break-after: avoid;
}
h4 {
  font-family: "Noto Sans RU", "Segoe UI", sans-serif;
  font-weight: 700;
  font-size: 10.8pt;
  color: var(--ink);
  margin: 1em 0 0.3em 0;
}

/* ---------- blockquotes / callouts ---------- */
blockquote {
  background: var(--panel);
  border-left: 4px solid var(--accent-light);
  border-radius: 0 6px 6px 0;
  margin: 0.8em 0;
  padding: 0.55em 0.95em;
  color: #373a42;
  page-break-inside: avoid;
}
blockquote p { margin: 0.28em 0; font-size: 0.98em; }
blockquote > p:first-child > strong {
  font-family: "Noto Sans RU", "Segoe UI", sans-serif;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-size: 0.83em;
  color: var(--accent);
  display: inline-block;
}

/* ---------- code ---------- */
.codeblock {
  margin: 0.7em 0;
  page-break-inside: avoid;
}
.code-lang {
  font-family: "Noto Sans RU", "Segoe UI", sans-serif;
  font-size: 7.4pt; letter-spacing: 0.14em; text-transform: uppercase;
  color: #8a93a3;
  padding: 0.18em 0.7em;
  background: #eef0f3;
  border: 1px solid var(--line);
  border-bottom: none;
  border-radius: 5px 5px 0 0;
}
.codeblock pre {
  margin: 0;
  background: var(--code-bg);
  border: 1px solid var(--line);
  border-radius: 0 0 5px 5px;
  padding: 0.7em 0.85em;
  overflow: hidden;
}
.codeblock pre code {
  font-family: Consolas, "Cascadia Mono", "Courier New", monospace;
  font-size: 8.35pt;
  line-height: 1.42;
  color: #26303c;
  white-space: pre-wrap;
  word-break: break-word;
}
code {
  font-family: Consolas, "Cascadia Mono", "Courier New", monospace;
  font-size: 0.92em;
  background: #eef0f3;
  border-radius: 3px;
  padding: 0.03em 0.28em;
  color: #7a2c1a;
}
pre code { background: none; padding: 0; color: #26303c; }

/* hljs github-ish overrides */
.hljs-keyword, .hljs-selector-tag, .hljs-literal, .hljs-section, .hljs-doctag { color: #cf222e; }
.hljs-string, .hljs-attr, .hljs-attribute, .hljs-template-variable, .hljs-addition { color: #0a3069; }
.hljs-title, .hljs-name, .hljs-built_in { color: #8250df; }
.hljs-comment, .hljs-quote { color: #6e7781; font-style: italic; }
.hljs-number, .hljs-symbol, .hljs-bullet, .hljs-meta { color: #0550ae; }
.hljs-params, .hljs-variable, .hljs-regexp { color: #953800; }

/* ---------- tables ---------- */
table {
  border-collapse: collapse;
  margin: 0.7em 0;
  width: 100%;
  font-size: 9.2pt;
  page-break-inside: avoid;
}
th, td {
  border: 1px solid var(--line);
  padding: 0.35em 0.6em;
  text-align: left;
  vertical-align: top;
}
th { background: #f0e7de; font-family: "Noto Sans RU", "Segoe UI", sans-serif; font-weight: 700; color: #5b2c1b; }

/* ---------- misc ---------- */
hr {
  border: none;
  border-top: 1px solid var(--line);
  margin: 1.6em 0;
  page-break-after: avoid;
}
strong code { color: inherit; }
</style>
</head>
<body>

<div class="cover">
  <div class="overline">${coverOverline}</div>
  <h1>«Скажи домашку»</h1>
  <p class="subtitle">${escapeHtml(coverSub)}</p>
  <div class="bar"></div>
  <div class="frontmatter">${coverMeta}</div>
  <div class="cover-foot">Учебник по проекту <b>alice-homework</b> · 14 глав · ${h2s.length} разделов · код из репозитория без упрощений</div>
</div>

${tocHtml}

${restHtml}

</body>
</html>`;

  fs.writeFileSync(path.join(HERE, "book.html"), html, "utf8");
  console.log("html written, chapters:", h2s.length);

  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: "new",
    args: ["--no-sandbox", "--disable-gpu"],
  });
  const page = await browser.newPage();
  await page.goto(`file://${path.join(HERE, "book.html").replace(/\\/g, "/")}`, {
    waitUntil: "networkidle0",
  });
  await page.emulateMediaType("print");

  await page.pdf({
    path: OUT_PDF,
    format: "A4",
    printBackground: true,
    displayHeaderFooter: true,
    margin: { top: "13mm", bottom: "14mm", left: "15mm", right: "15mm" },
    footerTemplate:
      `<div style="width:100%; font-size:7pt; font-family:Georgia,serif; color:#8b93a3; padding:0 15mm; display:flex; justify-content:space-between;">
         <span>Учебник по проекту «Скажи домашку»</span>
         <span class="pageNumber"></span>
       </div>`,
    headerTemplate: `<span></span>`,
  });

  // optional visual preview of cover + first chapter page: PREVIEW=1 node build.js
  if (OUT_PREVIEW) {
    const p1 = await browser.newPage();
    await p1.setViewport({ width: 794, height: 1123, deviceScaleFactor: 1.4 });
    await p1.goto(`file://${path.join(HERE, "book.html").replace(/\\/g, "/")}`, { waitUntil: "networkidle0" });
    await p1.emulateMediaType("print");
    await p1.screenshot({ path: path.join(HERE, "cover.png"), clip: { x: 0, y: 0, width: 794, height: 1123 } });
    await p1.evaluate(() => { const el = document.getElementById("ch-1"); if (el) el.scrollIntoView({block:"start"}); });
    await new Promise(r => setTimeout(r, 300));
    await p1.screenshot({ path: OUT_PREVIEW, clip: { x: 0, y: 0, width: 794, height: 1123 } });
  }

  await browser.close();
  console.log("pdf written:", OUT_PDF);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});