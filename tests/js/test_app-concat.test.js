/* 回归测试：pure-utils.js 与 app.js 必须在同一 JS 全局作用域下共存。

   背景 Bug（2026-08-29）：index.html 先加载 pure-utils.js，再加载 app.js。
   pure-utils.js 顶层声明了 `function escapeHtml`；app.js 顶层又用
   `const escapeHtml = ...` 重名声明 → SyntaxError: Identifier 'escapeHtml'
   has already been declared → 整个 app.js 无法解析 → window._openFile 未定义
   → Python 端 window._openFile(...) 静默失效 → 所有 md 文件都"打不开"（tab
   开了但预览空白）。

   修复：app.js 的 fallback 声明改用 `var escapeHtml`（var 与 function 重名合法）。

   本测试把两个文件合并进同一个 vm.Script 编译并执行，直接复现该作用域，
   防止未来再加顶层 const/let 与 pure-utils 全局函数重名时漏网。

   运行：npm test
*/
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const R = (...p) => path.join(__dirname, '..', '..', 'renderer', ...p);

// 最小浏览器环境桩：只够 app.js 顶层执行（不触发 init 的 DOM 渲染路径）。
function makeContext() {
  const noop = () => {};
  const fakeElement = { textContent: '', innerHTML: '', appendChild: noop };
  return {
    window: {},
    document: {
      readyState: 'loading',
      addEventListener: noop,
      createElement: () => ({ ...fakeElement }),
    },
    console: { log: noop, error: noop, warn: noop },
    setTimeout: noop, clearTimeout: noop,
    setInterval: noop, clearInterval: noop,
    requestAnimationFrame: noop,
    // 注意：不提供 module，pure-utils 会走 window 挂载分支
  };
}

test('pure-utils.js + app.js 合并可编译（无重名 SyntaxError）', () => {
  const pureUtils = fs.readFileSync(R('pure-utils.js'), 'utf8');
  const app = fs.readFileSync(R('app.js'), 'utf8');
  assert.doesNotThrow(
    () => new vm.Script(pureUtils + '\n' + app),
    'pure-utils.js + app.js 合并编译失败（顶层重名冲突）'
  );
});

test('执行后 window._openFile 已定义（渲染入口可用）', () => {
  const ctx = makeContext();
  vm.createContext(ctx);
  const pureUtils = fs.readFileSync(R('pure-utils.js'), 'utf8');
  const app = fs.readFileSync(R('app.js'), 'utf8');
  vm.runInContext(pureUtils + '\n' + app, ctx);
  assert.equal(typeof ctx.window._openFile, 'function', 'window._openFile 未定义');
  assert.equal(typeof ctx.window._pureEscapeHtml, 'function', 'pure-utils 未挂到 window');
  // 顶层全局函数名共存且可用（pure-utils 的 function escapeHtml 仍可被调用）
  assert.equal(typeof ctx.escapeHtml, 'function', '全局 escapeHtml 不可用');
});

test('在浏览器全局命名下重复声明的函数都能被覆盖而非报错', () => {
  // 直接验证 var + function 同名的合法性（修复所依赖的语义）
  const script = new vm.Script(
    'function f(){return 1} var f = (typeof f === "function") ? f : () => 2; globalThis.__f = typeof f;'
  );
  const ctx = { globalThis: {} };
  vm.createContext(ctx);
  script.runInContext(ctx);
  assert.equal(ctx.globalThis.__f, 'function');
});
