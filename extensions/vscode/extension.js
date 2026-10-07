const vscode = require("vscode");
const {execFile} = require("node:child_process");
function run(prompt, cwd) {
  return new Promise((resolve,reject)=>{
    execFile("jarvis", [prompt], {cwd, maxBuffer: 1024*1024}, (error, stdout, stderr)=>{
      if(error) reject(new Error(stderr || error.message)); else resolve(stdout);
    });
  });
}
function activate(context) {
  const selection = vscode.commands.registerCommand("jarvis.runSelection", async ()=>{
    const editor=vscode.window.activeTextEditor;
    if(!editor) return;
    const text=editor.document.getText(editor.selection);
    const prompt=`Review the selected code and propose a safe fix:\n\n${text}`;
    try { const result=await run(prompt, editor.document.uri.fsPath); vscode.window.showInformationMessage(result.slice(0,500)); }
    catch(e) { vscode.window.showErrorMessage(String(e)); }
  });
  const workspace = vscode.commands.registerCommand("jarvis.runWorkspace", async ()=>{
    const cwd=vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if(!cwd) return vscode.window.showErrorMessage("Open a workspace first.");
    try { const result=await run("Review this repository and identify the highest-impact safe improvement.", cwd); vscode.window.showInformationMessage(result.slice(0,500)); }
    catch(e) { vscode.window.showErrorMessage(String(e)); }
  });
  context.subscriptions.push(selection, workspace);
}
exports.activate=activate;
function deactivate(){}
exports.deactivate=deactivate;
