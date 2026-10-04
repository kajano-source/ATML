import { DebugSession, InitializedEvent, OutputEvent, TerminatedEvent } from '@vscode/debugadapter';
import type { DebugProtocol } from '@vscode/debugprotocol';
import { ChildProcess, spawn } from 'node:child_process';
import * as vscode from 'vscode';
import { resolveCompilerPath } from './extension';

interface AtmlLaunchArgs extends DebugProtocol.LaunchRequestArguments {
  file?: string;
  fps?: number;
  noBrowser?: boolean;
}

function runCompiler(cmd: string, args: string[], cwd: string,
  onOutput: (line: string) => void): Promise<number> {
  return new Promise((resolve) => {
    let child: ChildProcess;
    try {
      child = spawn(cmd, args, { cwd, shell: false });
    } catch (err) {
      onOutput(`Failed to start compiler (${cmd}): ${String(err)}\n`);
      resolve(1);
      return;
    }
    child.stdout?.on('data', (d: Buffer) => onOutput(d.toString()));
    child.stderr?.on('data', (d: Buffer) => onOutput(d.toString()));
    child.on('error', (err) => {
      onOutput(`Failed to start compiler (${cmd}): ${err.message}\n`);
      resolve(1);
    });
    child.on('close', (code) => resolve(code ?? 1));
  });
}

export class AtmlDebugSession extends DebugSession {
  public constructor() {
    super();
    this.setDebuggerLinesStartAt1(true);
    this.setDebuggerColumnsStartAt1(true);
  }

  protected initializeRequest(response: DebugProtocol.InitializeResponse): void {
    response.body = response.body ?? {};
    response.body.supportsConfigurationDoneRequest = false;
    response.body.supportTerminateDebuggee = false;
    this.sendResponse(response);
    this.sendEvent(new InitializedEvent());
  }

  protected launchRequest(response: DebugProtocol.LaunchResponse,
    args: DebugProtocol.LaunchRequestArguments): void {
    void this.doLaunch(response, args as AtmlLaunchArgs);
  }

  private async doLaunch(response: DebugProtocol.LaunchResponse,
    args: AtmlLaunchArgs): Promise<void> {
    const file = (args.file && args.file.trim().length > 0)
      ? args.file
      : vscode.window.activeTextEditor?.document.fileName;
    if (!file) {
      this.sendEvent(new OutputEvent('ATML: no file to run (open an .atml file first).\n', 'stderr'));
      this.sendEvent(new TerminatedEvent());
      this.sendResponse(response);
      return;
    }
    const compiler = resolveCompilerPath();
    const isScript = compiler.endsWith('.py');
    if (!isScript) {
      const fs = await import('node:fs');
      if (compiler === 'atml') {
        const { execFileSync } = await import('node:child_process');
        try {
          execFileSync(compiler, ['--version'], { stdio: 'ignore' });
        } catch {
          this.sendEvent(new OutputEvent(
            'ATML: compiler not found. Install it (python3 installer/cli_install.py --yes) ' +
            'or set the "atml.compilerPath" setting.\n', 'stderr'));
          void vscode.window.showErrorMessage(
            'ATML: compiler not found on PATH. Run the installer or set "atml.compilerPath".');
          this.sendEvent(new TerminatedEvent());
          this.sendResponse(response);
          return;
        }
      } else if (!fs.existsSync(compiler)) {
        this.sendEvent(new OutputEvent(
          `ATML: compiler not found at ${compiler}.\n`, 'stderr'));
        void vscode.window.showErrorMessage(
          `ATML: compiler not found at ${compiler}. Set "atml.compilerPath".`);
        this.sendEvent(new TerminatedEvent());
        this.sendResponse(response);
        return;
      }
    }
    const runArgs = isScript
      ? [compiler, 'run', file]
      : ['run', file];
    const cmd = isScript ? 'python3' : compiler;
    if (typeof args.fps === 'number' && args.fps > 0) {
      runArgs.push('--fps', String(args.fps));
    }
    if (args.noBrowser === true) {
      runArgs.push('--no-browser');
    }
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? process.cwd();
    this.sendEvent(new OutputEvent(`ATML debug: ${cmd} ${runArgs.join(' ')}\n`));
    const code = await runCompiler(cmd, runArgs, workspaceRoot,
      (line) => this.sendEvent(new OutputEvent(line)));
    if (code !== 0) {
      this.sendEvent(new OutputEvent(`ATML run failed (exit ${code}).\n`, 'stderr'));
      void vscode.window.showErrorMessage(
        `ATML run failed (exit ${code}) — see Debug Console for details.`);
    } else {
      void vscode.window.showInformationMessage('ATML: opened in your browser.');
    }
    this.sendEvent(new TerminatedEvent());
    this.sendResponse(response);
  }
}

export function registerAtmlDebugger(context: vscode.ExtensionContext): void {
  context.subscriptions.push(
    vscode.debug.registerDebugAdapterDescriptorFactory('atml', {
      createDebugAdapterDescriptor: () => {
        return new vscode.DebugAdapterInlineImplementation(new AtmlDebugSession());
      }
    })
  );
}
