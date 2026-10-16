// Run the actual TypeScript translator without introducing a frontend test framework.
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const assert = require('node:assert/strict');
const ts = require('../frontend/node_modules/typescript');
const filename = path.resolve(__dirname, '../frontend/src/i18n.tsx');
const source = fs.readFileSync(filename, 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {
  module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true
}}).outputText;
const runtime = new Module(filename, module);
runtime.filename = filename;
runtime.paths = Module._nodeModulePaths(path.dirname(filename));
runtime._compile(compiled, filename);
const {translate: t, isLocale} = runtime.exports;
assert.equal(t('en-US', '照片图库'), 'Photo library');
assert.equal(t('zh-TW', '照片图库'), '相片圖庫');
assert.equal(t('en-US', '{0}的相册', ['小明']), "小明's album");
assert.equal(t('zh-TW', '{0}的相册', ['小明']), '小明的相簿');
assert.equal(t('en-US', '已导入 48 张照片，可以浏览或开始识别。'), 'Imported 48 photos. Browse them or start recognition.');
assert.equal(t('en-US', '整理完成：48 张，2 张失败，缓存命中 5 次。'), 'Sorting complete: 48 photos, 2 failed, 5 cache hits.');
assert.equal(t('en-US', '导出完成：2 个人物照片关联'), 'Export complete: 2 person-photo links');
assert.equal(t('en-US', '请选择已有的本地 ONNX 权重：D:\\旅行\\模型.onnx'), 'Choose an existing local ONNX model: D:\\旅行\\模型.onnx');
assert.equal(t('zh-CN', 'Settings saved.'), '设置已保存。');
assert.equal(t('en-US', '儲存設定'), 'Save settings');
assert.equal(t('en-US', 'unknown runtime error: 小明.jpg'), 'unknown runtime error: 小明.jpg');
assert.equal(isLocale('en-US'), true);
assert.equal(isLocale('fr-FR'), false);
// Check every top-level UI component without matching implementation text.
const catalogues = ['en-US', 'zh-TW'].map(locale => require('../frontend/src/locales/' + locale + '.json'));
for (const name of fs.readdirSync(path.resolve(__dirname, '../frontend/src')).filter(name => name.endsWith('.tsx'))) {
 const app = ts.createSourceFile(name, fs.readFileSync(path.resolve(__dirname, '../frontend/src', name), 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
 function visit(node) {
  if (ts.isCallExpression(node) && node.expression.getText(app) === 't' && ts.isStringLiteral(node.arguments[0])) {
   for (const catalogue of catalogues) assert.ok(node.arguments[0].text in catalogue, 'Missing translation: ' + node.arguments[0].text);
  }
  ts.forEachChild(node, visit);
 }
 visit(app);
}
console.log('Localization checks passed for all UI components.');
