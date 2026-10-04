import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { spawn } from 'child_process';
import { registerAtmlDebugger } from './atmlDebug';

let outputChannel: vscode.OutputChannel;
let diagnosticCollection: vscode.DiagnosticCollection;
let statusBarItem: vscode.StatusBarItem;

const ATML_TAGS = [
  'atml', 'stage', 'scene', 'actor', 'part', 'draw', 'pixel',
  'key', 'animate', 'tween', 'timeline', 'clip', 'transition',
  'loop', 'trigger', 'camera', 'use'
];

const ATML_ATTRS = [
  'fps', 'dur', 'duration', 'delay', 'ease', 'easing', 'loop', 'target',
  'targets', 'at', 'from', 'to', 'morph', 'follow', 'anchor', 'shape',
  'fill', 'stroke', 'stroke-width', 'x', 'y', 'cx', 'cy', 'r', 'rx', 'ry',
  'width', 'height', 'd', 'points', 'text', 'font', 'font-size', 'opacity',
  'rotate', 'scale', 'translate', 'href', 'src', 'id', 'class', 'name',
  'value', 'count', 'repeat', 'mode', 'direction', 'trigger', 'on',
  'event', 'when', 'play'
];

const ATML_SUGAR_ATTRS = [
  'a-fade', 'a-slide', 'a-bounce', 'a-spin', 'a-float', 'a-morph'
];

const EASINGS = [
  'linear', 'ease', 'ease-in', 'ease-out', 'ease-in-out',
  'bounce', 'elastic', 'spring', 'smooth', 'step'
];

const SHAPES = ['rect', 'circle', 'path', 'text', 'ellipse', 'line', 'polygon'];

const TAG_DOCS: Record<string, string> = {
  atml: 'Root ATML document. Attributes: `fps` (default frame rate).',
  stage: 'Canvas. Attributes: `width`, `height`.',
  scene: 'A scene / shot. Attributes: `dur` (e.g. `3s`).',
  actor: 'Drawable entity. Attributes: `id`, `shape` (rect|circle|path|text), geometry (`x y width height`, `cx cy r`, `d`), `fill`, `stroke`.',
  part: 'Sub-actor attached to an actor. Attributes: `id`, `shape`, `anchor`.',
  draw: 'Stroke-on animation. Attributes: `target`, `dur`, `ease`.',
  pixel: 'Single pixel cell. Attributes: `x`, `y`, `fill`.',
  key: 'Keyframe inside `<animate>`. Attributes: `at` (`0%`–`100%`) plus any animatable property.',
  animate: 'Keyframe animation. Attributes: `target`, `dur`, `ease`, `loop`, `delay`.',
  tween: 'Single-property interpolation. Attributes: `target`, `from`, `to`, `dur`, `ease`.',
  timeline: 'Container sequencing `<clip>` children.',
  clip: 'Timed slot in a timeline. Attributes: `at`, `dur`.',
  transition: 'Reusable named transition. Attributes: `id`, `dur`, `ease`.',
  loop: 'Repeat a block. Attributes: `count` / `repeat`.',
  trigger: 'Event hook. Attributes: `on` (e.g. `click`), `target`, `play`.',
  camera: 'Camera move. Attributes: `follow`, `dur`, `ease`.',
  use: 'Apply a named transition. Attributes: `target`, `transition`.'
};

const ATTR_DOCS: Record<string, string> = {
  fps: 'Frames per second, e.g. `fps="12"`.',
  dur: 'Duration with units, e.g. `dur="2s"`, `dur="500ms"`.',
  delay: 'Start delay, e.g. `delay="0.5s"`.',
  ease: 'Easing: linear, ease, ease-in, ease-out, ease-in-out, bounce, elastic, spring, smooth, step.',
  at: 'Keyframe position (`0%`–`100%`) or clip offset (`0s`).',
  from: 'Tween start value.',
  to: 'Tween end value.',
  morph: 'Morph target id (`a-morph` / `morph` attr).',
  follow: 'Camera follow target id.',
  anchor: 'Part anchor point (e.g. `center`, `left`).',
  shape: 'Actor shape: rect | circle | path | text | ellipse | line | polygon.',
  fill: 'Fill color, e.g. `fill="#7C3AED"`.',
  loop: 'Repeat animation (`loop="true"` or count).'
};

export function resolveCompilerPath(): string {
  const configured = vscode.workspace.getConfiguration('atml').get<string>('compilerPath', '');
  if (configured && configured.trim().length > 0) {
    return configured.trim();
  }
  const candidates: string[] = [];
  const extDir = path.join(__dirname, '..');
  candidates.push(
    path.join(extDir, 'compiler', 'atmlc.py'),
    path.join(extDir, '..', 'compiler', 'atmlc.py')
  );
  const wsRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (wsRoot) {
    candidates.push(path.join(wsRoot, 'compiler', 'atmlc.py'));
  }
  // User-level installs (GUI-launched VS Code often lacks ~/.local/bin on PATH).
  const home = process.env.HOME ?? process.env.USERPROFILE ?? '';
  if (home) {
    candidates.push(path.join(home, '.local', 'bin', 'atml'));
    candidates.push(path.join(home, '.local', 'share', 'atml', 'compiler', 'atmlc.py'));
  }
  const localAppData = process.env.LOCALAPPDATA ?? '';
  if (localAppData) {
    candidates.push(path.join(localAppData, 'ATML', 'atml.cmd'));
    candidates.push(path.join(localAppData, 'ATML', 'compiler', 'atmlc.py'));
  }
  for (const candidate of candidates) {
    if (candidate && fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return 'atml';
}

function buildCommand(file: string, outFile: string): { cmd: string; args: string[] } {
  const compiler = resolveCompilerPath();
  if (compiler.endsWith('.py')) {
    return { cmd: 'python3', args: [compiler, 'build', file, '-o', outFile] };
  }
  return { cmd: compiler, args: ['build', file, '-o', outFile] };
}

function publishCommand(file: string, outDir: string): { cmd: string; args: string[] } {
  const compiler = resolveCompilerPath();
  if (compiler.endsWith('.py')) {
    return { cmd: 'python3', args: [compiler, 'publish', file, '-o', outDir] };
  }
  return { cmd: compiler, args: ['publish', file, '-o', outDir] };
}

function runBuildProcess(cmd: string, args: string[], cwd: string): Promise<{ code: number; output: string }> {
  return new Promise((resolve) => {
    outputChannel.appendLine(`$ ${cmd} ${args.join(' ')}`);
    const child = spawn(cmd, args, { cwd, shell: false });
    let output = '';
    child.stdout?.on('data', (d: Buffer) => {
      const s = d.toString();
      output += s;
      outputChannel.append(s);
    });
    child.stderr?.on('data', (d: Buffer) => {
      const s = d.toString();
      output += s;
      outputChannel.append(s);
    });
    child.on('error', (err) => {
      const msg = `Failed to start compiler (${cmd}): ${err.message}\n`;
      outputChannel.append(msg);
      resolve({ code: 1, output: output + msg });
    });
    child.on('close', (code) => {
      resolve({ code: code ?? 1, output });
    });
  });
}

function parseDiagnostics(output: string): vscode.Diagnostic[] {
  // Matches file:line[:col]: message
  const diagnostics: vscode.Diagnostic[] = [];
  const re = /([^\s:]+\.atml):(\d+)(?::(\d+))?\s*[:\-]\s*(.+)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(output)) !== null) {
    const line = Math.max(0, parseInt(m[2], 10) - 1);
    const col = m[3] ? Math.max(0, parseInt(m[3], 10) - 1) : 0;
    const range = new vscode.Range(line, col, line, col + 1);
    diagnostics.push(new vscode.Diagnostic(range, m[4].trim(), vscode.DiagnosticSeverity.Error));
  }
  return diagnostics;
}

async function buildActiveFile(returnHtmlPath = false): Promise<string | undefined> {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== 'atml') {
    void vscode.window.showWarningMessage('ATML: open an .atml file first.');
    return undefined;
  }
  const doc = editor.document;
  await doc.save();
  const file = doc.fileName;
  const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath
    ?? path.dirname(file);
  const distDir = path.join(path.dirname(file), 'dist');
  try {
    fs.mkdirSync(distDir, { recursive: true });
  } catch {
    // ignore
  }
  const base = path.basename(file, path.extname(file));
  const outFile = path.join(distDir, `${base}.html`);
  const { cmd, args } = buildCommand(file, outFile);
  outputChannel.show(true);
  outputChannel.appendLine(`ATML build: ${file} -> ${outFile}`);
  const result = await runBuildProcess(cmd, args, workspaceRoot);
  const diags = parseDiagnostics(result.output);
  diagnosticCollection.set(doc.uri, diags);
  if (result.code === 0 && fs.existsSync(outFile)) {
    void vscode.window.showInformationMessage(`ATML: built ${path.basename(outFile)}`);
    if (returnHtmlPath) {
      return outFile;
    }
    return outFile;
  }
  if (result.code !== 0 && !fs.existsSync(outFile)) {
    void vscode.window.showErrorMessage('ATML build failed — see Output > ATML.');
  } else if (fs.existsSync(outFile)) {
    // Compiler may have written output despite nonzero code; still surface path.
    if (returnHtmlPath) {
      return outFile;
    }
    return outFile;
  }
  return undefined;
}

async function publishActiveFile(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== 'atml') {
    void vscode.window.showWarningMessage('ATML: open an .atml file first.');
    return;
  }
  const doc = editor.document;
  await doc.save();
  const file = doc.fileName;
  const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath
    ?? path.dirname(file);
  const outDir = path.join(path.dirname(file), 'dist');
  const { cmd, args } = publishCommand(file, outDir);
  outputChannel.show(true);
  outputChannel.appendLine(`ATML publish: ${file} -> ${outDir}/`);
  const result = await runBuildProcess(cmd, args, workspaceRoot);
  const diags = parseDiagnostics(result.output);
  diagnosticCollection.set(doc.uri, diags);
  if (result.code === 0) {
    void vscode.window.showInformationMessage('ATML: published to dist/ (index.html + assets).');
  } else {
    void vscode.window.showErrorMessage('ATML publish failed — see Output > ATML.');
  }
}

async function runInBrowser(): Promise<void> {
  const htmlPath = await buildActiveFile(true);
  if (!htmlPath) {
    return;
  }
  outputChannel.appendLine(`ATML run in browser: ${htmlPath}`);
  const opener = process.platform === 'win32'
    ? { cmd: 'cmd', args: ['/c', 'start', '', htmlPath] }
    : process.platform === 'darwin'
      ? { cmd: 'open', args: [htmlPath] }
      : { cmd: 'xdg-open', args: [htmlPath] };
  const { execFile } = await import('node:child_process');
  execFile(opener.cmd, opener.args, (err) => {
    if (err) {
      void vscode.window.showErrorMessage(
        `ATML: could not open a browser (${err.message}). File is at ${htmlPath}`);
      return;
    }
    void vscode.window.showInformationMessage('ATML: opened in your browser.');
  });
}

async function previewActiveFile(): Promise<void> {
  const htmlPath = await buildActiveFile(true);
  if (!htmlPath) {
    return;
  }
  // Prefer Simple Browser if available, else fall back to an embedded webview.
  try {
    await vscode.commands.executeCommand('simpleBrowser.show', vscode.Uri.file(htmlPath).toString());
    return;
  } catch {
    // fall through to webview
  }
  const panel = vscode.window.createWebviewPanel(
    'atmlPreview',
    `ATML Preview: ${path.basename(htmlPath)}`,
    vscode.ViewColumn.Beside,
    { enableScripts: true }
  );
  let html: string;
  try {
    html = fs.readFileSync(htmlPath, 'utf8');
  } catch (err) {
    html = `<html><body><pre>Could not read built file: ${String(err)}</pre></body></html>`;
  }
  panel.webview.html = html;
}

function updateStatusBar(editor: vscode.TextEditor | undefined): void {
  if (!editor || editor.document.languageId !== 'atml') {
    statusBarItem.hide();
    return;
  }
  const text = editor.document.getText();
  const m = text.match(/fps\s*=\s*["']?(\d+)/i);
  const fallback = vscode.workspace.getConfiguration('atml').get<number>('defaultFps', 12);
  const fps = m ? m[1] : String(fallback ?? 12);
  statusBarItem.text = `$(pulse) ATML ${fps}fps`;
  statusBarItem.tooltip = 'ATML frame rate (from fps attribute or atml.defaultFps)';
  statusBarItem.command = 'atml.build';
  statusBarItem.show();
}

export function activate(context: vscode.ExtensionContext): void {
  outputChannel = vscode.window.createOutputChannel('ATML');
  diagnosticCollection = vscode.languages.createDiagnosticCollection('atml');
  context.subscriptions.push(outputChannel, diagnosticCollection);
  registerAtmlDebugger(context);

  statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  context.subscriptions.push(statusBarItem);
  updateStatusBar(vscode.window.activeTextEditor);

  context.subscriptions.push(
    vscode.commands.registerCommand('atml.build', () => buildActiveFile(false)),
    vscode.commands.registerCommand('atml.preview', () => previewActiveFile()),
    vscode.commands.registerCommand('atml.publish', () => publishActiveFile()),
    vscode.commands.registerCommand('atml.run', () => runInBrowser()),
    vscode.window.onDidChangeActiveTextEditor((e) => updateStatusBar(e)),
    vscode.workspace.onDidSaveTextDocument((doc) => {
      if (doc.languageId !== 'atml') {
        return;
      }
      const auto = vscode.workspace.getConfiguration('atml').get<boolean>('autoBuildOnSave', false);
      if (auto) {
        void buildActiveFile(false);
      }
      updateStatusBar(vscode.window.activeTextEditor);
    }),
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration('atml.defaultFps')) {
        updateStatusBar(vscode.window.activeTextEditor);
      }
    })
  );

  context.subscriptions.push(
    vscode.languages.registerHoverProvider('atml', {
      provideHover(doc, pos) {
        const range = doc.getWordRangeAtPosition(pos, /[a-zA-Z][a-zA-Z0-9-]*/);
        if (!range) {
          return undefined;
        }
        const word = doc.getText(range);
        if (TAG_DOCS[word]) {
          return new vscode.Hover(new vscode.MarkdownString(`**\`<${word}>\`** — ${TAG_DOCS[word]}`));
        }
        if (ATTR_DOCS[word]) {
          return new vscode.Hover(new vscode.MarkdownString(`**\`${word}=\`** — ${ATTR_DOCS[word]}`));
        }
        if (ATML_SUGAR_ATTRS.includes(word)) {
          return new vscode.Hover(new vscode.MarkdownString(`**\`${word}\`** — sugar shorthand animation attribute.`));
        }
        if (EASINGS.includes(word)) {
          return new vscode.Hover(new vscode.MarkdownString(`**\`${word}\`** — ATML easing function.`));
        }
        return undefined;
      }
    }),
    vscode.languages.registerCompletionItemProvider('atml', {
      provideCompletionItems(doc, pos) {
        const line = doc.lineAt(pos.line).text.slice(0, pos.character);
        const items: vscode.CompletionItem[] = [];
        const tagMatch = /<\s*([a-zA-Z]*)$/.exec(line);
        if (tagMatch) {
          for (const tag of ATML_TAGS) {
            const item = new vscode.CompletionItem(tag, vscode.CompletionItemKind.Class);
            item.detail = `ATML <${tag}>`;
            item.documentation = TAG_DOCS[tag] ?? '';
            items.push(item);
          }
          return items;
        }
        const attrContext = /<\s*[a-zA-Z][a-zA-Z0-9-]*\s+[^<>]*$/.exec(line);
        if (attrContext) {
          for (const attr of [...ATML_ATTRS, ...ATML_SUGAR_ATTRS]) {
            const item = new vscode.CompletionItem(attr, vscode.CompletionItemKind.Property);
            item.detail = `ATML @${attr}`;
            item.documentation = ATTR_DOCS[attr] ?? (attr.startsWith('a-') ? 'Sugar shorthand animation attribute.' : '');
            items.push(item);
          }
          return items;
        }
        const valueMatch = /(ease|easing|shape)\s*=\s*["']?([a-zA-Z-]*)$/.exec(line);
        if (valueMatch) {
          const kind = valueMatch[1];
          const values = kind === 'shape' ? SHAPES : EASINGS;
          for (const v of values) {
            const item = new vscode.CompletionItem(v, vscode.CompletionItemKind.Value);
            item.detail = `ATML ${kind}`;
            items.push(item);
          }
          return items;
        }
        return undefined;
      }
    }),
    vscode.languages.registerDocumentFormattingEditProvider('atml', {
      provideDocumentFormattingEdits(doc) {
        // Pass-through formatter: normalize line endings + trailing whitespace
        // without reformatting ATML semantics. Full pretty-printing is out of scope.
        const edits: vscode.TextEdit[] = [];
        for (let i = 0; i < doc.lineCount; i++) {
          const line = doc.lineAt(i);
          const trimmed = line.text.replace(/[ \t]+$/u, '');
          if (trimmed !== line.text) {
            edits.push(vscode.TextEdit.replace(line.range, trimmed));
          }
        }
        return edits;
      }
    })
  );

  outputChannel.appendLine('ATML extension activated.');
}

export function deactivate(): void {
  // No async teardown required.
}
