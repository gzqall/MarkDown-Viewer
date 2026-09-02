/* ═══════════════════════════════════════════════════════════════════════════
   Markdown Viewer — 纯函数工具集（可被 node 单元测试直接 import）
   ═══════════════════════════════════════════════════════════════════════════

   这些函数原本内联在 app.js 里。抽出来是因为：
   1. 它们是纯函数（无 DOM/无副作用），适合 node 单元测试覆盖回归。
   2. app.js 通过 <script> 标签加载，不是 ES module；这里同时导出
      CommonJS（module.exports）和挂到全局 window 对象，两种引用方式都兼容。
   ═══════════════════════════════════════════════════════════════════════════ */

// ─── HTML 转义 ──────────────────────────────────────────────────────────
function escapeHtml(str) {
  // 用 DOM 构造能天然转义；但纯函数场景（node 无 DOM）退化为字符串替换。
  // 与 app.js 原实现行为一致：&, <, >, ", '
  if (typeof document !== 'undefined') {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
  }
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// ─── 标题 slug 生成 ───────────────────────────────────────────────────────
/** 把标题文本转成 url-safe 的 id。中文/字母数字保留，其余变 -，首尾 - 去掉。
 *  与 app.js postProcessContent 内的 slug 逻辑一致。 */
function slugify(text) {
  if (!text) return '';
  return text
    .toLowerCase()
    .replace(/[^\w一-鿿]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

/** 为重复标题加后缀去重。返回带后缀的唯一 id。
 *  usedIds 会被修改（加入新 id）。 */
function dedupeId(id, usedIds) {
  if (!id) id = 'heading';
  let suffix = '';
  while (usedIds.has(id + suffix)) {
    // 第一次冲突用 '2'，之后递增数字部分
    suffix = suffix === '' ? '2' : (parseInt(suffix, 10) + 1).toString();
  }
  const finalId = id + suffix;
  usedIds.add(finalId);
  return finalId;
}

// ─── 相对图片 URL 解析 ─────────────────────────────────────────────────────
/** 给定 markdown 文件目录 dir 和 <img src> 原始值，返回重扎根后的 file:// URL。
 *  已是绝对 URL（http/file/data/blob/#）或 Windows 绝对路径的，原样返回 null。
 *  与 app.js resolveImageSrcs 内的 abs() 一致。 */
function resolveImageUrl(src, dir) {
  if (!src) return null;
  if (/^(https?:|file:|data:|blob:|#)/i.test(src)) return null;
  if (/^[A-Za-z]:[\\\/]/.test(src)) return null;          // Windows abs
  if (src.startsWith('//')) return null;
  // 规范化 dir：反斜杠转正斜杠、去首尾多余斜杠；
  // POSIX 绝对路径（/home/u）的前导 / 要去掉，否则 file:/// + /home → file:////
  let d = String(dir).replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
  return 'file:///' + d + '/' + src.replace(/^\.\//, '');
}

// ─── [[wiki link]] 候选路径 ──────────────────────────────────────────────
/** 给定 wiki 目标名和当前文件目录，生成候选文件路径数组。
 *  与 app.js setupWikiLinks 的候选生成逻辑一致。 */
function wikiLinkCandidates(wiki, dir) {
  const names = [wiki + '.md', wiki + '.markdown', wiki + '.mdx', wiki];
  return names.map((c) => (dir + '/' + c).replace(/\\/g, '/'));
}

// ─── TOC HTML 生成 ────────────────────────────────────────────────────────
/** 从 headings 数组 [{level, text, id}] 生成目录 HTML。
 *  与 app.js generateTOC 一致。 */
function generateTOC(headings) {
  if (!headings || !headings.length) {
    return '<p style="color:var(--text-muted)">(no headings)</p>';
  }
  let html = '<div class="table-of-contents"><ul>';
  headings.forEach((h) => {
    const level = h.level;
    const text = (h.text || '').replace(/#\s*$/, '').trim();
    if (!text || !h.id) return;
    html += `<li style="margin-left:${(level - 1) * 16}px;list-style:none">`;
    html += `<a href="#${h.id}">${text}</a></li>`;
  });
  html += '</ul></div>';
  return html;
}

// ─── 导出（CommonJS + 浏览器全局）──────────────────────────────────────────
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    escapeHtml,
    slugify,
    dedupeId,
    resolveImageUrl,
    wikiLinkCandidates,
    generateTOC,
  };
}
if (typeof window !== 'undefined') {
  Object.assign(window, {
    _pureEscapeHtml: escapeHtml,
    _pureSlugify: slugify,
    _pureDedupeId: dedupeId,
    _pureResolveImageUrl: resolveImageUrl,
    _pureWikiLinkCandidates: wikiLinkCandidates,
    _pureGenerateTOC: generateTOC,
  });
}
