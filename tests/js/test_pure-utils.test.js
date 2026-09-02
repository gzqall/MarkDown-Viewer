/* 前端纯函数单元测试（node 内置 test runner）。
   运行：npm test
   覆盖从 app.js 抽到 pure-utils.js 的纯逻辑：slug/escapeHtml/dedupeId/
   resolveImageUrl/wikiLinkCandidates/generateTOC。
*/

const { test } = require('node:test');
const assert = require('node:assert/strict');
const {
  escapeHtml, slugify, dedupeId, resolveImageUrl,
  wikiLinkCandidates, generateTOC,
} = require('../../renderer/pure-utils.js');

// ─── escapeHtml ─────────────────────────────────────────────────────────
test('escapeHtml escapes & < > " \'', () => {
  // 'e' 里的两个单引号都转成 &#39;
  assert.equal(escapeHtml('a < b & c > "d" \'e\''),
    'a &lt; b &amp; c &gt; &quot;d&quot; &#39;e&#39;');
});

test('escapeHtml handles non-string input', () => {
  assert.equal(escapeHtml(42), '42');
});

test('escapeHtml leaves plain text unchanged', () => {
  assert.equal(escapeHtml('hello world'), 'hello world');
});

// ─── slugify ────────────────────────────────────────────────────────────
test('slugify lowercases and separates non-word by dash', () => {
  assert.equal(slugify('Hello World'), 'hello-world');
});

test('slugify keeps CJK characters', () => {
  assert.equal(slugify('你好 World'), '你好-world');
});

test('slugify trims leading/trailing dashes', () => {
  assert.equal(slugify('!!!hello'), 'hello');
  assert.equal(slugify('hello!!!'), 'hello');
});

test('slugify empty returns empty', () => {
  assert.equal(slugify(''), '');
  assert.equal(slugify(null), '');
});

test('slugify all-special-chars returns empty then dedupe to heading', () => {
  assert.equal(slugify('!!!???'), '');
});

// ─── dedupeId ───────────────────────────────────────────────────────────
test('dedupeId returns id when not used', () => {
  const used = new Set();
  assert.equal(dedupeId('hello', used), 'hello');
  assert.ok(used.has('hello'));
});

test('dedupeId appends -2 -3 for duplicates', () => {
  const used = new Set();
  assert.equal(dedupeId('hello', used), 'hello');
  assert.equal(dedupeId('hello', used), 'hello2');
  assert.equal(dedupeId('hello', used), 'hello3');
});

test('dedupeId empty id becomes "heading"', () => {
  const used = new Set();
  assert.equal(dedupeId('', used), 'heading');
});

// ─── resolveImageUrl ─────────────────────────────────────────────────────
test('resolveImageUrl rewrites relative path to file:// URL', () => {
  const r = resolveImageUrl('pic.png', 'C:\\docs\\note');
  assert.equal(r, 'file:///C:/docs/note/pic.png');
});

test('resolveImageUrl strips leading ./', () => {
  const r = resolveImageUrl('./pic.png', '/home/u');
  assert.equal(r, 'file:///home/u/pic.png');
});

test('resolveImageUrl null for http URLs', () => {
  assert.equal(resolveImageUrl('http://a.com/x.png', 'dir'), null);
  assert.equal(resolveImageUrl('https://a.com/x.png', 'dir'), null);
});

test('resolveImageUrl null for file/data/blob/# URLs', () => {
  assert.equal(resolveImageUrl('file:///x', 'dir'), null);
  assert.equal(resolveImageUrl('data:image/png;base64,xx', 'dir'), null);
  assert.equal(resolveImageUrl('#anchor', 'dir'), null);
});

test('resolveImageUrl null for Windows absolute paths', () => {
  assert.equal(resolveImageUrl('C:\\img\\p.png', 'dir'), null);
  assert.equal(resolveImageUrl('D:/abs/p.png', 'dir'), null);
});

test('resolveImageUrl null for protocol-relative //', () => {
  assert.equal(resolveImageUrl('//cdn.com/x.png', 'dir'), null);
});

test('resolveImageUrl null for empty src', () => {
  assert.equal(resolveImageUrl('', 'dir'), null);
  assert.equal(resolveImageUrl(null, 'dir'), null);
});

// ─── wikiLinkCandidates ─────────────────────────────────────────────────
test('wikiLinkCandidates builds 4 paths with extensions', () => {
  const cs = wikiLinkCandidates('note', 'C:\\wiki');
  assert.deepEqual(cs, [
    'C:/wiki/note.md',
    'C:/wiki/note.markdown',
    'C:/wiki/note.mdx',
    'C:/wiki/note',
  ]);
});

test('wikiLinkCandidates handles forward-slash dir', () => {
  const cs = wikiLinkCandidates('foo', '/home/u');
  assert.deepEqual(cs, [
    '/home/u/foo.md',
    '/home/u/foo.markdown',
    '/home/u/foo.mdx',
    '/home/u/foo',
  ]);
});

// ─── generateTOC ─────────────────────────────────────────────────────────
test('generateTOC empty returns placeholder', () => {
  assert.equal(generateTOC([]), '<p style="color:var(--text-muted)">(no headings)</p>');
  assert.equal(generateTOC(null), '<p style="color:var(--text-muted)">(no headings)</p>');
});

test('generateTOC builds nested list by level', () => {
  const hs = [
    { level: 1, text: 'Intro', id: 'intro' },
    { level: 2, text: 'Details', id: 'details' },
    { level: 3, text: 'Deep', id: 'deep' },
  ];
  const html = generateTOC(hs);
  assert.ok(html.includes('<div class="table-of-contents"><ul>'));
  assert.ok(html.includes('margin-left:0px'));
  assert.ok(html.includes('margin-left:16px'));
  assert.ok(html.includes('margin-left:32px'));
  assert.ok(html.includes('href="#intro"'));
});

test('generateTOC skips entries without text or id', () => {
  const hs = [
    { level: 1, text: 'Keep', id: 'keep' },
    { level: 2, text: '', id: 'empty' },
    { level: 2, text: 'NoId', id: '' },
  ];
  const html = generateTOC(hs);
  assert.ok(html.includes('href="#keep"'));
  assert.ok(!html.includes('href="#empty"'));
  assert.ok(!html.includes('href="#"'));
});

test('generateTOC strips trailing # from text', () => {
  const hs = [{ level: 1, text: 'Title #', id: 'title' }];
  assert.ok(generateTOC(hs).includes('>Title</a>'));
});
