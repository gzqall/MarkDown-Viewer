/* ═══════════════════════════════════════════════════════════════════════════
   Markdown Viewer — Renderer Application Script (QWebChannel version)
   ═══════════════════════════════════════════════════════════════════════════ */

// ─── State ────────────────────────────────────────────────────────────────
const state = {
  theme: 'dark',
  zoom: 1.0,
  searchVisible: false,
  searchResults: [],
  searchIndex: -1,
  bridge: null,
  currentFile: null,
  files: {},        // path -> { content, scrollPos, heading }
  currentPath: null,
  _fileOrder: [],   // LRU order for pruning
};

const MAX_TRACKED_FILES = 50;

// Prune oldest files when over limit — keep only the most recent MAX_TRACKED_FILES
function _pruneFiles() {
  const keys = Object.keys(state.files);
  if (keys.length <= MAX_TRACKED_FILES) return;
  // Sort by LRU order: _fileOrder tracks most recently used
  const toRemove = keys.slice(0, keys.length - MAX_TRACKED_FILES);
  toRemove.forEach((k) => {
    delete state.files[k];
    const idx = state._fileOrder.indexOf(k);
    if (idx !== -1) state._fileOrder.splice(idx, 1);
  });
}

function _touchFile(path) {
  // Move to end of LRU list
  const idx = state._fileOrder.indexOf(path);
  if (idx !== -1) state._fileOrder.splice(idx, 1);
  state._fileOrder.push(path);
}

// ─── DOM Shortcuts ────────────────────────────────────────────────────────
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const dom = {};

function cacheDOM() {
  dom.preview      = $('#preview');
  dom.dropOverlay  = $('#drop-overlay');
  dom.loading      = $('#loading-indicator');
  dom.content      = $('#content');
  dom.searchBar    = $('#search-bar');
  dom.searchInput  = $('#search-input');
  dom.searchCount  = $('#search-count');
  dom.tocSidebar   = $('#toc-sidebar');
  dom.tocContent   = $('#toc-content');
}

// ─── Markdown-it Setup ────────────────────────────────────────────────────
let md = null;

function initMarkdownIt() {
  if (typeof markdownit === 'undefined') {
    console.error('markdown-it not loaded');
    return;
  }

  md = markdownit({
    html: true,
    linkify: true,
    typographer: true,
    breaks: false,
    langPrefix: 'language-',
    highlight(str, lang) {
      if (lang && hljs && hljs.getLanguage(lang)) {
        try {
          const html = hljs.highlight(str, {
            language: lang,
            ignoreIllegals: true,
          }).value;
          return `<pre class="hljs"><code class="language-${lang}">${html}</code></pre>`;
        } catch (_) {}
      }
      return `<pre class="hljs"><code>${escapeHtml(str)}</code></pre>`;
    },
  });

  // Plugins
  if (typeof markdownitEmoji !== 'undefined') md.use(markdownitEmoji, { shortcuts: {} });
  if (typeof markdownitSub !== 'undefined') md.use(markdownitSub);
  if (typeof markdownitSup !== 'undefined') md.use(markdownitSup);
  if (typeof markdownitMark !== 'undefined') md.use(markdownitMark);
  if (typeof markdownitFootnote !== 'undefined') md.use(markdownitFootnote);
  if (typeof markdownitTaskLists !== 'undefined') {
    md.use(markdownitTaskLists, { enabled: true, label: true, labelAfter: true });
  }
  if (typeof markdownitContainer !== 'undefined') {
    // Custom note containers
    [
      { name: 'info', icon: 'ℹ️' },
      { name: 'warning', icon: '⚠️' },
      { name: 'danger', icon: '🚫' },
      { name: 'success', icon: '✅' },
      { name: 'tip', icon: '💡' },
    ].forEach(({ name, icon }) => {
      md.use(markdownitContainer, name, {
        render(tokens, idx) {
          const t = tokens[idx];
          if (t.nesting === 1) {
            const title = t.info.trim().slice(name.length).trim() || name.toUpperCase();
            return `<div class="custom-block ${name}">\n<div class="custom-block-title">${icon} ${title}</div>\n<div class="custom-block-body">\n`;
          }
          return '</div>\n</div>\n';
        },
      });
    });
  }

  // ─── Wiki Link Plugin [[link]] ────────────────────────────────────
  md.use(function wikiLinkPlugin(md) {
    // Match [[link]] or [[link|display]]
    const pattern = /\[\[([^\]|]+)(?:\|([^\]]*))?\]\]/;
    function wikiLink(state, silent) {
      var pos = state.pos, max = state.posMax;
      if (state.src.charCodeAt(pos) !== 0x5B) return false; // '['
      if (pos + 1 >= max) return false;
      if (state.src.charCodeAt(pos + 1) !== 0x5B) return false; // second '['

      var match = state.src.slice(pos).match(pattern);
      if (!match) return false;

      var link = match[1].trim();
      var display = (match[2] || link).trim();
      var token;

      if (!silent) {
        token = state.push('wiki_link_open', 'a', 1);
        token.attrs = [['href', '#' + link], ['class', 'wiki-link'], ['data-wiki', link]];
        token.markup = 'wiki';

        token = state.push('text', '', 0);
        token.content = display;

        token = state.push('wiki_link_close', 'a', -1);
        token.markup = 'wiki';
      }

      state.pos += match[0].length;
      return true;
    }

    md.inline.ruler.push('wiki_link', wikiLink);
  });
  const defaultFence = md.renderer.rules.fence;
  md.renderer.rules.fence = function (tokens, idx, options, env, self) {
    const token = tokens[idx];
    const info = token.info.trim();
    const parts = info.split(/\s+/);
    const lang = parts[0];
    const content = token.content;

    if (lang === 'mermaid') {
      return `<div class="mermaid-wrapper"><div class="mermaid">${content}</div></div>`;
    }

    if (lang === 'echarts') {
      try {
        JSON.parse(content);
        return `<div class="echarts-wrapper"><div class="echarts-chart" data-echarts='${content.replace(/'/g, '&#39;')}'></div></div>`;
      } catch (_) {
        return `<pre class="hljs"><code>${escapeHtml(content)}</code></pre>`;
      }
    }

    // Filename annotation
    const filename = parts.length > 1 ? parts.slice(1).join(' ') : null;
    if (filename) {
      const rendered = defaultFence(tokens, idx, options, env, self);
      return `<div class="code-block-with-filename"><div class="code-filename">${filename}</div>${rendered}</div>`;
    }

    return defaultFence(tokens, idx, options, env, self);
  };
}

// ─── KaTeX Math Rendering ────────────────────────────────────────────────
function renderMath() {
  if (typeof katex === 'undefined' || typeof renderMathInElement === 'undefined') return;
  try {
    renderMathInElement(dom.preview, {
      delimiters: [
        { left: '$$', right: '$$', display: true },
        { left: '$', right: '$', display: false },
      ],
      throwOnError: false,
      errorColor: 'var(--danger)',
    });
  } catch (e) {
    console.warn('KaTeX error:', e);
  }
}

// ─── Rendering ────────────────────────────────────────────────────────────
function hideLoading() {
  clearTimeout(state._loadingTimeout);
  if (dom.loading) dom.loading.classList.add('hidden');
}

function showLoading() {
  if (dom.loading) dom.loading.classList.remove('hidden');
  if (dom.dropOverlay) dom.dropOverlay.classList.add('hidden');

  // Safety timeout: force-hide loading after 5 seconds no matter what
  clearTimeout(state._loadingTimeout);
  state._loadingTimeout = setTimeout(hideLoading, 5000);
}

function renderContent(markdown) {
  showLoading();

  requestAnimationFrame(() => {
    try {
      disposeECharts();

      // Guard against missing markdown-it
      if (!md || typeof md.render !== 'function') {
        dom.preview.innerHTML = `<div class="custom-block danger"><div class="custom-block-title">\u{1F6AB} Render Error</div><div class="custom-block-body"><p>Markdown-it not initialized</p></div></div>`;
        hideLoading();
        return;
      }

      const html = md.render(markdown);
      dom.preview.innerHTML = html;

      requestAnimationFrame(() => {
        try {
          postProcessContent();
          renderMath();
          renderMermaid();
          renderECharts();
          // Restore scroll position from saved state
          if (state.currentPath && state.files[state.currentPath]) {
            dom.content.scrollTop = state.files[state.currentPath].scrollPos || 0;
          }
          // 在 postProcessContent 给标题赋完 id 后，重建左侧目录并刷新高亮。
          // 之前 buildTOC 在 renderContent 之前跑，拿到的 h.id 多为空，点击/跳转失效。
          if (dom.tocSidebar.style.display !== 'none') {
            buildTOC();
            updateActiveTOCItem();
          }
        } finally {
          hideLoading();
        }
      });
    } catch (err) {
      dom.preview.innerHTML = `<div class="custom-block danger"><div class="custom-block-title">\u{1F6AB} Render Error</div><div class="custom-block-body"><p>${escapeHtml(err.message)}</p></div></div>`;
      hideLoading();
      console.error('Render error:', err);
    }
  });
}

// Extra safety: schedule a periodic check to auto-hide the loading indicator
// if it's been visible for more than 10 seconds (catches edge cases)
function setupLoadingWatchdog() {
  setInterval(function() {
    if (dom.loading && !dom.loading.classList.contains('hidden')) {
      // Check if the loading has been visible 'too long' — but only if
      // content has already been rendered (i.e., preview is non-empty)
      if (dom.preview && dom.preview.innerHTML.length > 0) {
        hideLoading();
      }
    }
  }, 3000);
}

// ─── Mermaid ──────────────────────────────────────────────────────────────
function renderMermaid() {
  if (typeof mermaid === 'undefined') return;
  const els = document.querySelectorAll('.mermaid');
  if (!els.length) return;

  mermaid.initialize({
    startOnLoad: false,
    theme: state.theme === 'dark' ? 'dark' : 'default',
    securityLevel: 'loose',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  });

  els.forEach((el, i) => {
    if (!el.id) el.id = `mermaid-${Date.now()}-${i}`;
    // 保存原始源码到 data-mermaid-src，主题切换重渲时还原，
    // 否则 mermaid 看到已渲染的 <svg> 会失败/乱画。
    const stored = el.getAttribute('data-mermaid-src');
    if (stored !== null) {
      el.removeAttribute('data-processed');
      el.innerHTML = stored;
    } else if (el.textContent.trim()) {
      el.setAttribute('data-mermaid-src', el.textContent);
    }
    try {
      mermaid.run({ nodes: [el], suppressErrors: true });
    } catch (e) {
      console.warn('Mermaid error:', e);
    }
  });
}

// ─── ECharts ──────────────────────────────────────────────────────────────
function renderECharts() {
  if (typeof echarts === 'undefined') return;
  const charts = document.querySelectorAll('.echarts-chart');
  charts.forEach((el) => {
    try {
      const options = JSON.parse(el.getAttribute('data-echarts'));
      const chart = echarts.init(el, state.theme === 'dark' ? 'dark' : undefined);
      chart.setOption(options);
      const ro = new ResizeObserver(() => chart.resize());
      ro.observe(el);
      el._chart = chart;
      el._resizeObserver = ro;
    } catch (e) {
      el.innerHTML = `<pre style="color:var(--danger);background:transparent;border:none">ECharts Error: ${e.message}</pre>`;
    }
  });
}

function disposeECharts() {
  document.querySelectorAll('.echarts-chart').forEach((el) => {
    if (el._chart) {
      el._resizeObserver?.disconnect();
      el._chart.dispose();
      el._chart = null;
    }
  });
}

// ─── Table of Contents ────────────────────────────────────────────────────
function buildTOC() {
  const headings = dom.preview.querySelectorAll('h1, h2, h3, h4, h5, h6');
  const container = dom.tocContent;
  container.innerHTML = '';

  if (!headings.length) {
    container.innerHTML = '<div style="padding:12px;color:#6c7086;font-size:13px;">No headings</div>';
    return;
  }

  headings.forEach((h) => {
    const level = parseInt(h.tagName[1], 10);
    const text = (h.textContent || '').replace(/¶\s*$/, '').trim();
    const id = h.id;
    if (!text) return;

    const link = document.createElement('a');
    link.className = 'toc-item';
    link.style.paddingLeft = `${12 + (level - 1) * 16}px`;
    link.textContent = text;
    link.href = '#';
    link.setAttribute('data-href', '#' + (id || ''));
    link.addEventListener('click', (e) => {
      e.preventDefault();
      if (id) {
        // 滚动到对应标题；保留一个偏移让标题不至于贴在最顶端
        const target = document.getElementById(id);
        if (target) {
          dom.content.scrollTo({
            top: Math.max(0, target.offsetTop - 12),
            behavior: 'smooth',
          });
          container.querySelectorAll('.toc-item').forEach((t) => t.classList.remove('active'));
          link.classList.add('active');
        }
      }
    });
    container.appendChild(link);
  });
}

// ─── Search ───────────────────────────────────────────────────────────────
function toggleSearch() {
  state.searchVisible = !state.searchVisible;
  dom.searchBar.style.display = state.searchVisible ? 'flex' : 'none';
  if (state.searchVisible) {
    dom.searchInput.focus();
    dom.searchInput.select();
  } else {
    clearSearchHighlights();
  }
}

function performSearch() {
  const query = dom.searchInput.value.trim().toLowerCase();
  // 相同查询不重复扫描（防止 input 防抖重复跑、且回车跳转时无需重算）
  if (query === state._lastSearchQuery) {
    return;
  }
  state._lastSearchQuery = query;
  clearSearchHighlights();
  state.searchResults = [];
  state.searchIndex = -1;

  if (!query) {
    dom.searchCount.textContent = '';
    return;
  }

  const matches = [];
  const walker = document.createTreeWalker(dom.preview, NodeFilter.SHOW_TEXT, null, false);
  let node;
  while ((node = walker.nextNode())) {
    const text = node.textContent.toLowerCase();
    let pos = 0;
    while ((pos = text.indexOf(query, pos)) !== -1) {
      matches.push({ node, offset: pos, length: query.length });
      pos += query.length;
    }
  }

  if (!matches.length) {
    dom.searchCount.textContent = '0/0';
    return;
  }

  state.searchResults = matches;

  // Safe highlight: split text nodes at match boundaries and wrap in <mark>
  // Process in reverse offset order so earlier splits don't break later positions
  matches.slice().reverse().forEach((match) => {
    const textNode = match.node;
    const parent = textNode.parentNode;
    if (!parent) return;

    // Split after the match
    const after = textNode.splitText(match.offset + match.length);
    // Split at the match start — now `textNode` contains only the matched text
    const mid = textNode.splitText(match.offset);
    // `mid` is now the text node containing just the matched text

    const mark = document.createElement('mark');
    mark.className = 'search-highlight';
    parent.replaceChild(mark, mid);
    mark.appendChild(mid);
  });

  goToSearchResult(0);
}

function goToSearchResult(index) {
  if (!state.searchResults.length) return;
  state.searchIndex = (index + state.searchResults.length) % state.searchResults.length;
  dom.searchCount.textContent = `${state.searchIndex + 1}/${state.searchResults.length}`;

  const highlights = $$('.search-highlight');
  highlights.forEach((h, i) => {
    h.style.background = i === state.searchIndex ? '#f9e2af' : '#f9e2af66';
    h.style.color = i === state.searchIndex ? '#0f1a24' : '';
  });

  highlights[state.searchIndex]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function clearSearchHighlights() {
  $$('.search-highlight').forEach((h) => {
    const parent = h.parentNode;
    if (parent) {
      // Replace the <mark> with its text content, merging adjacent text nodes
      parent.replaceChild(document.createTextNode(h.textContent), h);
      parent.normalize();
    }
  });
  state.searchResults = [];
  state.searchIndex = -1;
  dom.searchCount.textContent = '';
}

// ─── Search wiring (input + 按钮) ────────────────────────────────────────
// 之前 performSearch 定义了却从未被调用：input 不搜、回车/按钮都失效。
// 这里把 input 事件（带防抖）和 上一个/下一个/关闭 三个按钮接上。
function setupSearch() {
  let t = null;
  dom.searchInput.addEventListener('input', () => {
    clearTimeout(t);
    t = setTimeout(performSearch, 100);
  });
  $('#btn-search-prev')?.addEventListener('click', (e) => {
    e.preventDefault();
    goToSearchResult(state.searchIndex - 1);
  });
  $('#btn-search-next')?.addEventListener('click', (e) => {
    e.preventDefault();
    goToSearchResult(state.searchIndex + 1);
  });
  $('#btn-search-close')?.addEventListener('click', (e) => {
    e.preventDefault();
    toggleSearch();
  });
}

// ─── Zoom ─────────────────────────────────────────────────────────────────
function zoomIn() { state.zoom = Math.min(state.zoom + 0.1, 2.0); applyZoom(); }
function zoomOut() { state.zoom = Math.max(state.zoom - 0.1, 0.5); applyZoom(); }
function zoomReset() { state.zoom = 1.0; applyZoom(); }
function applyZoom() { dom.preview.style.fontSize = `${state.zoom}rem`; }

// ─── Post-processing (heading anchors + [[toc]]) ─────────────────────────
function postProcessContent() {
  const article = dom.preview;

  // 1. Add slug IDs and anchor links to all headings
  const headings = article.querySelectorAll('h1, h2, h3, h4, h5, h6');
  const usedIds = new Set();
  headings.forEach((h) => {
    const text = h.textContent.replace(/¶\s*$/, '').trim();
    if (!text) return;
    let id = (typeof _pureSlugify === 'function') ? _pureSlugify(text) : text.toLowerCase().replace(/[^\w一-鿿]+/g, '-').replace(/^-+|-+$/g, '');
    if (!id) id = 'heading';
    id = (typeof _pureDedupeId === 'function') ? _pureDedupeId(id, usedIds) : (() => {
      let suffix = '';
      while (usedIds.has(id + suffix)) suffix = suffix ? (parseInt(suffix.slice(1)) + 1).toString() : '2';
      const f = id + suffix; usedIds.add(f); return f;
    })();

    h.id = id;

    // Add anchor link
    const anchor = document.createElement('a');
    anchor.className = 'heading-anchor';
    anchor.href = `#${id}`;
    anchor.textContent = '#';
    anchor.setAttribute('aria-hidden', 'true');
    anchor.style.cssText = 'display:none;margin-left:6px;font-size:0.7em;color:var(--accent);text-decoration:none;opacity:0.5;';
    h.addEventListener('mouseenter', () => { anchor.style.display = 'inline'; });
    h.addEventListener('mouseleave', () => { anchor.style.display = ''; });
    h.insertBefore(anchor, h.firstChild);
  });

  // 2. Replace [[toc]] with auto-generated TOC
  const tocMarkers = article.querySelectorAll('p, div');
  tocMarkers.forEach((el) => {
    if (el.textContent.trim() === '[[toc]]') {
      const tocHtml = generateTOC(headings);
      const wrapper = document.createElement('div');
      wrapper.innerHTML = tocHtml;
      el.replaceWith(wrapper);
    }
  });

  // 3. Resolve relative image URLs against the current .md file's directory.
  //    The base URL passed to setHtml() is the renderer directory, so a bare
  //    ![](pic.png) would otherwise resolve to .../renderer/pic.png (404).
  //    We re-root each relative src to the markdown file's directory.
  resolveImageSrcs(article);

  // 4. 代码块一键复制按钮
  setupCodeCopyButtons(article);

  // 5. 可折叠章节（标题折叠后续兄弟节点）+ 代码块折叠
  setupCollapsibleSections(article);
}

// ─── 代码块复制按钮 ─────────────────────────────────────────────────────
function setupCodeCopyButtons(root) {
  root.querySelectorAll('pre > code').forEach((code) => {
    const pre = code.parentElement;
    if (pre.querySelector('.code-copy-btn')) return;  // 防止重复绑定
    const btn = document.createElement('button');
    btn.className = 'code-copy-btn';
    btn.type = 'button';
    btn.textContent = '复制';
    btn.setAttribute('aria-label', '复制代码');
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      const text = code.textContent || '';
      try {
        await navigator.clipboard.writeText(text);
        btn.textContent = '已复制 ✓';
      } catch {
        // clipboard API 在某些 file:// 上下文不可用，回退到 execCommand
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.cssText = 'position:fixed;opacity:0';
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand('copy'); btn.textContent = '已复制 ✓'; }
        catch { btn.textContent = '复制失败'; }
        ta.remove();
      }
      // 1.5s 后还原文案
      clearTimeout(btn._t);
      btn._t = setTimeout(() => { btn.textContent = '复制'; }, 1500);
    });
    pre.appendChild(btn);
  });
}

// ─── 可折叠章节 + 代码块折叠 ───────────────────────────────────────────
function setupCollapsibleSections(root) {
  // (a) 标题折叠：点击标题左侧箭头，切换其后兄弟节点显隐，
  //     直到遇到同级或更高级标题为止。
  root.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach((h) => {
    if (h.querySelector('.collapse-toggle')) return;
    const toggle = document.createElement('span');
    toggle.className = 'collapse-toggle';
    toggle.textContent = '▾';
    toggle.title = '折叠/展开';
    h.insertBefore(toggle, h.firstChild);
    toggle.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const level = parseInt(h.tagName[1], 10);
      let sib = h.nextElementSibling;
      const collapsed = toggle.classList.toggle('collapsed');
      toggle.textContent = collapsed ? '▸' : '▾';
      while (sib) {
        // 遇到同级/更高级标题 → 停止
        const m = sib.tagName && sib.tagName.match(/^H([1-6])$/);
        if (m && parseInt(m[1], 10) <= level) break;
        sib.classList.toggle('collapsed-section', collapsed);
        sib.style.display = collapsed ? 'none' : '';
        sib = sib.nextElementSibling;
      }
    });
  });

  // (b) 代码块折叠：长代码块（>20 行）显示“折叠/展开”按钮，折叠时只露首行
  root.querySelectorAll('pre').forEach((pre) => {
    if (pre.querySelector('.code-collapse-btn')) return;
    const code = pre.querySelector('code');
    if (!code) return;
    const lines = code.textContent.split('\n').length;
    if (lines < 20) return;  // 短代码不折
    const btn = document.createElement('button');
    btn.className = 'code-collapse-btn';
    btn.type = 'button';
    btn.textContent = '折叠';
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const folded = pre.classList.toggle('code-folded');
      btn.textContent = folded ? '展开' : '折叠';
    });
    pre.appendChild(btn);
  });
}

function resolveImageSrcs(root) {
  const dir = state.currentFile ? state.currentFile.dir : '';
  if (!dir) return;
  const abs = (typeof _pureResolveImageUrl === 'function') ? _pureResolveImageUrl : null;
  root.querySelectorAll('img[src]').forEach((img) => {
    const a = abs ? abs(img.getAttribute('src'), dir) : null;
    if (a) img.src = a;
  });
}

// generateTOC 接受 [{level,text,id}]；postProcessContent 传的是 DOM headings，
// 这里做一层适配。
function generateTOC(headings) {
  const arr = Array.from(headings).map((h) => ({
    level: parseInt(h.tagName[1], 10),
    text: h.textContent.replace(/#\s*$/, '').trim(),
    id: h.id,
  }));
  return (typeof _pureGenerateTOC === 'function')
    ? _pureGenerateTOC(arr)
    : _fallbackTOC(arr);
}

function _fallbackTOC(headings) {
  if (!headings.length) return '<p style="color:var(--text-muted)">(no headings)</p>';
  let html = '<div class="table-of-contents"><ul>';
  headings.forEach((h) => {
    if (!h.text || !h.id) return;
    html += `<li style="margin-left:${(h.level - 1) * 16}px;list-style:none">`;
    html += `<a href="#${h.id}">${h.text}</a></li>`;
  });
  html += '</ul></div>';
  return html;
}

// ─── TOC Toggle (in-webview sidebar) ─────────────────────────────────────
function toggleTOC() {
  const sidebar = dom.tocSidebar;
  const isHidden = sidebar.style.display === 'none';
  sidebar.style.display = isHidden ? 'block' : 'none';
  if (isHidden) {
    buildTOC();
    updateActiveTOCItem();  // 立即高亮当前章节
  }
}

// ─── TOC Scroll-Spy ───────────────────────────────────────────────────────
// 监听内容滚动，自动高亮左侧目录中当前可见章节，便于快速跳转浏览。
let _tocSpyReady = false;
function setupTOCScrollSpy() {
  if (_tocSpyReady) return;
  _tocSpyReady = true;
  // 滚动节流：rAF 合并连续滚动事件
  let ticking = false;
  dom.content?.addEventListener('scroll', () => {
    if (!ticking) {
      ticking = true;
      requestAnimationFrame(() => { updateActiveTOCItem(); ticking = false; });
    }
  }, { passive: true });
}

function updateActiveTOCItem() {
  if (dom.tocSidebar.style.display === 'none') return;
  const headings = Array.from(dom.preview.querySelectorAll('h1, h2, h3, h4, h5, h6'));
  if (!headings.length) return;

  // 找到当前滚动视口顶部之上（留 80px 缓冲）最后一个已滚过的标题
  const scrollY = dom.content.scrollTop;
  const threshold = 80;
  let active = null;
  for (const h of headings) {
    // offsetTop 相对 offsetParent；content 是滚动容器
    if (h.offsetTop - threshold <= scrollY) active = h;
    else break;
  }
  // 没滚到任何标题（页面顶端）→ 高亮第一个
  if (!active) active = headings[0];
  const activeId = active.id;

  dom.tocContent.querySelectorAll('.toc-item').forEach((item) => {
    item.classList.toggle('active', item.getAttribute('data-href') === '#' + activeId);
  });

  // 把当前 active 项滚进目录侧栏可见区域
  const activeEl = dom.tocContent.querySelector('.toc-item.active');
  if (activeEl) {
    const cRect = dom.tocContent.getBoundingClientRect();
    const eRect = activeEl.getBoundingClientRect();
    if (eRect.top < cRect.top || eRect.bottom > cRect.bottom) {
      activeEl.scrollIntoView({ block: 'nearest' });
    }
  }
}

// ─── Theme ────────────────────────────────────────────────────────────────
function onThemeChanged() {
  // Re-render mermaid and echarts with new theme
  renderMermaid();
  renderECharts();
  // Update TOC colors
  buildTOC();
}

// ─── QWebChannel Bridge ───────────────────────────────────────────────────
function initBridge() {
  return new Promise((resolve) => {
    if (typeof QWebChannel !== 'undefined') {
      try {
        new QWebChannel(qt.webChannelTransport, (channel) => {
          state.bridge = channel.objects.bridge;
          if (state.bridge) {
            state.bridge.onPageReady();
          }
          resolve();
        });
      } catch(e) {
        resolve();
      }
    } else {
      console.log('[MD] QWebChannel not available');
      resolve();
    }
  });
}

// ─── Called from Python via runJavaScript() ───────────────────────────────
window._openFile = function (info) {
  const data = typeof info === 'string' ? JSON.parse(info) : info;

  // Save current file's scroll position
  if (state.currentPath && state.files[state.currentPath]) {
    state.files[state.currentPath].scrollPos = dom.content ? dom.content.scrollTop : 0;
  }

  // Update state
  state.currentFile = data;
  state.currentPath = data.path;

  // Init file tracking entry
  if (!state.files[data.path]) {
    state.files[data.path] = { content: '', scrollPos: 0, heading: '' };
  }
  state.files[data.path].content = data.content;
  _touchFile(data.path);
  _pruneFiles();

  // Hide drop overlay
  dom.dropOverlay.classList.add('hidden');

  // Render (TOC 会在 postProcessContent 赋完标题 id 后，于 renderContent 内重建)
  renderContent(data.content);
};

/** Restore scroll position after render (called from Python via runJS) */
window._restoreScroll = function (filePath) {
  const entry = state.files[filePath];
  if (entry && entry.scrollPos > 0 && dom.content) {
    requestAnimationFrame(() => {
      dom.content.scrollTop = entry.scrollPos;
    });
  }
};

/** Save scroll position for a file (called from Python before tab switch) */
window._saveScrollPos = function (filePath) {
  if (filePath && state.files[filePath] && dom.content) {
    state.files[filePath].scrollPos = dom.content.scrollTop;
    _touchFile(filePath);
  }
};

/** Get current file's scroll position (called from Python via runJS callback) */
window._getScrollPos = function () {
  return dom.content ? dom.content.scrollTop : 0;
};

window._fileChanged = function (info) {
  const data = typeof info === 'string' ? JSON.parse(info) : info;
  if (data.changed && state.currentFile) {
    state.currentFile.content = data.content;
    // Also update file tracking
    if (state.currentPath && state.files[state.currentPath]) {
      state.files[state.currentPath].content = data.content;
      _touchFile(state.currentPath);
    }
    renderContent(data.content);
  }
};

window._toggleSearch = toggleSearch;
window._buildTOC = buildTOC;
window._toggleTOC = toggleTOC;
window._zoomIn = zoomIn;
window._zoomOut = zoomOut;
window._zoomReset = zoomReset;
window._onThemeChanged = onThemeChanged;

/** Get full rendered HTML for export (called from Python) */
window._getExportHTML = function () {
  const content = dom.preview ? dom.preview.innerHTML : '';
  const theme = document.documentElement.getAttribute('data-theme') || 'dark';
  return JSON.stringify({ content, theme });
};

// ─── Keyboard shortcuts (when not handled by Qt menu) ────────────────────
document.addEventListener('keydown', (e) => {
  // If typing in search, handle search navigation
  if (e.target === dom.searchInput) {
    if (e.key === 'Escape') { toggleSearch(); return; }
    if (e.key === 'Enter') {
      e.preventDefault();
      // 回车前先确保当前输入已被搜索（防抖可能还没跑）
      const q = dom.searchInput.value.trim().toLowerCase();
      if (q !== state._lastSearchQuery) {
        performSearch();
      }
      if (e.shiftKey) goToSearchResult(state.searchIndex - 1);
      else goToSearchResult(state.searchIndex + 1);
      return;
    }
    return;
  }

  const ctrl = e.ctrlKey || e.metaKey;

  // Search (handled here even though Qt also has it)
  if (ctrl && e.key === 'f') {
    e.preventDefault();
    toggleSearch();
    return;
  }

  // These are handled by Qt menus primarily, but we provide JS fallback
  if (ctrl && e.key === 'o') { e.preventDefault(); /* handled by Qt */ }
  if (ctrl && e.key === 'r') { e.preventDefault(); /* handled by Qt */ }
  if (ctrl && e.key === 'b') { e.preventDefault(); /* handled by Qt */ }
});

// ─── Drag & Drop (handled by Qt — just prevent browser defaults) ────────
document.addEventListener('dragover', (e) => e.preventDefault());
document.addEventListener('drop', (e) => e.preventDefault());

// ─── Wiki Link Handler ──────────────────────────────────────────────────
function setupWikiLinks() {
  dom.preview.addEventListener('click', (e) => {
    const link = e.target.closest('.wiki-link');
    if (!link) return;
    e.preventDefault();
    const wiki = link.getAttribute('data-wiki');
    if (!wiki || !state.bridge || !state.currentPath) return;

    // Try to open the linked file in the same directory.
    // 把所有候选扩展名一次性交给 Python，由它打开第一个存在的文件，
    // 避免逐个尝试时弹出一串 "File not found" toast。
    const dir = state.currentFile ? state.currentFile.dir : '';
    if (!dir) return;
    const fullPaths = (typeof _pureWikiLinkCandidates === 'function')
      ? _pureWikiLinkCandidates(wiki, dir)
      : [wiki + '.md', wiki + '.markdown', wiki + '.mdx', wiki].map((c) => (dir + '/' + c).replace(/\\/g, '/'));
    state.bridge.openWikiLink(JSON.stringify(fullPaths));
  });
}

// ─── Image Lightbox ──────────────────────────────────────────────────────
function setupImageLightbox() {
  dom.preview.addEventListener('click', (e) => {
    const img = e.target.closest('img');
    if (!img || !img.src) return;
    // Ignore small/emoji-sized images
    if (img.naturalWidth < 32 && img.naturalHeight < 32) return;
    e.preventDefault();
    showLightbox(img.src, img.alt);
  });
}

// ─── Image Context Menu (right-click) ───────────────────────────────────
function setupImageContextmenu() {
  dom.preview.addEventListener('contextmenu', (e) => {
    const img = e.target.closest('img');
    if (!img || !img.src) return;
    // Ignore tiny/emoji-sized images
    if (img.naturalWidth < 32 && img.naturalHeight < 32) return;
    e.preventDefault();
    showImageContextMenu(img.src, img.alt, e.clientX, e.clientY);
  });
}

function showImageContextMenu(src, alt, x, y) {
  // Remove any existing menu
  document.querySelectorAll('.image-context-menu').forEach((m) => m.remove());

  const menu = document.createElement('div');
  menu.className = 'image-context-menu';
  menu.style.left = x + 'px';
  menu.style.top = y + 'px';

  const items = [
    { label: '🔍  View Original',     act: () => { showLightbox(src, alt); } },
    { label: '📂  Open Original File', act: () => { state.bridge?.openImage(src); } },
    { label: '📁  Show in Folder',    act: () => { state.bridge?.showImageInFolder(src); } },
    { label: '💾  Save Image As…',   act: () => { state.bridge?.saveImageAs(src); } },
    { label: '📋  Copy Image Address', act: () => {
        navigator.clipboard?.writeText(src);
        toastStatus('Copied image address');
      } },
  ];

  items.forEach((it) => {
    const item = document.createElement('div');
    item.className = 'image-context-menu-item';
    item.textContent = it.label;
    item.addEventListener('click', () => {
      closeMenus();
      try { it.act(); } catch (err) { console.warn('Image menu action failed:', err); }
    });
    menu.appendChild(item);
  });

  document.body.appendChild(menu);
  // Reposition if the menu overflows the viewport
  requestAnimationFrame(() => {
    const r = menu.getBoundingClientRect();
    if (r.right > window.innerWidth)  menu.style.left = Math.max(4, window.innerWidth - r.width - 4) + 'px';
    if (r.bottom > window.innerHeight) menu.style.top  = Math.max(4, window.innerHeight - r.height - 4) + 'px';
  });
}

// Close any open image context menu on a click elsewhere / Escape / scroll
function closeMenus() {
  document.querySelectorAll('.image-context-menu').forEach((m) => m.remove());
}
document.addEventListener('click', closeMenus, true);
document.addEventListener('scroll', closeMenus, true);
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeMenus(); }, true);

function toastStatus(msg) {
  // Lightweight in-page toast for actions that don't round-trip through Python
  let t = document.getElementById('__img_toast');
  if (!t) {
    t = document.createElement('div');
    t.id = '__img_toast';
    t.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%)' +
      ';background:rgba(0,0,0,0.8);color:#fff;padding:6px 14px;border-radius:6px' +
      ';font-size:13px;z-index:2000;pointer-events:none;opacity:0;transition:opacity .15s';
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.style.opacity = '1';
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.style.opacity = '0'; }, 1500);
}

function showLightbox(src, alt) {
  const overlay = document.createElement('div');
  overlay.className = 'lightbox-overlay';

  // 用 DOM API 构造，避免 src/alt 含引号或特殊字符时产生注入
  const backdrop = document.createElement('div');
  backdrop.className = 'lightbox-backdrop';

  const container = document.createElement('div');
  container.className = 'lightbox-container';

  const closeBtn = document.createElement('button');
  closeBtn.className = 'lightbox-close';
  closeBtn.title = 'Close (Esc)';
  closeBtn.textContent = '✕';

  const img = document.createElement('img');
  img.className = 'lightbox-image';
  img.src = src;                       // 赋属性而非拼字符串
  img.alt = alt || '';
  img.tabIndex = 0;                    // 可聚焦，用于接收 Esc

  const caption = document.createElement('div');
  caption.className = 'lightbox-caption';
  caption.textContent = alt || '';    // textContent 天然转义

  container.append(closeBtn, img, caption);
  overlay.append(backdrop, container);

  const close = () => overlay.remove();
  backdrop.addEventListener('click', close);
  closeBtn.addEventListener('click', close);
  img.addEventListener('click', close);
  overlay.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(); });
  img.addEventListener('wheel', (e) => {
    e.preventDefault();
    const scale = e.deltaY > 0 ? 0.9 : 1.1;
    const w = Math.max(100, Math.min(4000, (img.naturalWidth || img.width) * scale));
    img.style.width = w + 'px';
    img.style.height = 'auto';
  }, { passive: false });

  document.body.appendChild(overlay);
  img.focus();
}
// 纯函数从 pure-utils.js 引用（浏览器全局已挂），保持单一实现 + 可测试
// 注意：用 var 而非 const/let —— pure-utils.js 已在全局声明了 function escapeHtml，
// const/let 重名会直接 SyntaxError 让整个 app.js 无法解析（其他函数同理已由 pure-utils 提供）。
var escapeHtml = (typeof _pureEscapeHtml === 'function') ? _pureEscapeHtml : (str) => {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
};

// ─── Init ─────────────────────────────────────────────────────────────────
async function init() {
  cacheDOM();
  initMarkdownIt();

  // Check CDN libraries loaded
  if (typeof markdownit === 'undefined') {
    dom.preview.innerHTML = `
      <div class="custom-block danger" style="margin:40px">
        <div class="custom-block-title">⚠️ 加载失败</div>
        <div class="custom-block-body">
          <p>Markdown 渲染库加载失败，原因可能是：</p>
          <ul>
            <li>🛜 网络连接异常（CDN 被墙/超时）</li>
            <li>📦 本地 vendor 文件缺失</li>
          </ul>
          <p><strong>解决方法：</strong></p>
          <p>运行以下命令下载依赖库到本地：</p>
          <pre style="background:#233545;padding:12px;border-radius:6px;font-size:13px"><code>python download_libs.py</code></pre>
        </div>
      </div>`;
    dom.dropOverlay?.classList.add('hidden');
    dom.loading?.classList.add('hidden');
    return;
  }

  // Initialize mermaid
  if (typeof mermaid !== 'undefined') {
    mermaid.initialize({
      startOnLoad: false,
      theme: 'dark',
      securityLevel: 'loose',
    });
  }

  // Connect to QWebChannel
  await initBridge();

  // Start periodic loading watchdog
  setupLoadingWatchdog();

  // Set up image lightbox
  setupImageLightbox();

  // Set up image right-click menu (open / show in folder / save as / copy)
  setupImageContextmenu();

  // Set up wiki link navigation
  setupWikiLinks();

  // Set up search bar (input debounce + prev/next/close buttons)
  setupSearch();

  // Set up TOC scroll-spy (highlight current heading in sidebar)
  setupTOCScrollSpy();
}

// Start when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
