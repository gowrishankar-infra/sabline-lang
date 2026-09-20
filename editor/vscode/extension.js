// Sabline VS Code extension: syntax highlighting is declarative (see
// package.json); this file adds LIVE ERRORS by speaking the Language
// Server Protocol to `sabline lsp` directly - no npm dependencies, so
// the folder-copy install keeps working.
const vscode = require("vscode");
const cp = require("child_process");

let proc = null;
let buffer = Buffer.alloc(0);
let nextId = 1;
let collection = null;
const waiting = new Map();          // request id -> resolve

function send(msg) {
  if (!proc) return;
  const body = Buffer.from(JSON.stringify(msg), "utf8");
  proc.stdin.write(`Content-Length: ${body.length}\r\n\r\n`);
  proc.stdin.write(body);
}

function onData(chunk) {
  buffer = Buffer.concat([buffer, chunk]);
  for (;;) {
    const headerEnd = buffer.indexOf("\r\n\r\n");
    if (headerEnd < 0) return;
    const header = buffer.slice(0, headerEnd).toString("utf8");
    const m = header.match(/Content-Length: *(\d+)/i);
    if (!m) { buffer = buffer.slice(headerEnd + 4); continue; }
    const len = parseInt(m[1], 10);
    const start = headerEnd + 4;
    if (buffer.length < start + len) return;
    const body = buffer.slice(start, start + len).toString("utf8");
    buffer = buffer.slice(start + len);
    try { handle(JSON.parse(body)); } catch (e) { /* ignore */ }
  }
}

function request(method, params) {
  return new Promise((resolve) => {
    const id = nextId++;
    const timer = setTimeout(() => {          // never hang the editor
      waiting.delete(id);
      resolve(null);
    }, 8000);
    waiting.set(id, (result) => { clearTimeout(timer); resolve(result); });
    send({ jsonrpc: "2.0", id, method, params });
  });
}

function handle(msg) {
  if (msg.id !== undefined && waiting.has(msg.id)) {
    const done = waiting.get(msg.id);
    waiting.delete(msg.id);
    done(msg.result === undefined ? null : msg.result);
    return;
  }
  if (msg.method === "textDocument/publishDiagnostics") {
    const { uri, diagnostics } = msg.params;
    const diags = diagnostics.map((d) => {
      const r = d.range;
      const range = new vscode.Range(
        r.start.line, r.start.character, r.end.line, r.end.character);
      const diag = new vscode.Diagnostic(
        range, d.message, vscode.DiagnosticSeverity.Error);
      diag.source = d.source || "sabline";
      return diag;
    });
    collection.set(vscode.Uri.parse(uri), diags);
  }
}

function docParams(doc) {
  return {
    textDocument: {
      uri: doc.uri.toString(), languageId: "sabline",
      version: doc.version, text: doc.getText(),
    },
  };
}

function activate(context) {
  collection = vscode.languages.createDiagnosticCollection("sabline");
  context.subscriptions.push(collection);
  try {
    proc = cp.spawn("sabline", ["lsp"], { shell: process.platform === "win32" });
  } catch (e) { proc = null; }
  if (!proc) return;
  proc.on("error", () => {
    proc = null;
    vscode.window.showInformationMessage(
      "Sabline: install the compiler (pip install .) to get live errors.");
  });
  proc.stdout.on("data", onData);

  send({ jsonrpc: "2.0", id: nextId++, method: "initialize", params: {} });
  send({ jsonrpc: "2.0", method: "initialized", params: {} });

  const isVel = (doc) => doc.languageId === "sabline";
  for (const doc of vscode.workspace.textDocuments) {
    if (isVel(doc)) {
      send({ jsonrpc: "2.0", method: "textDocument/didOpen",
             params: docParams(doc) });
    }
  }
  const at = (doc, position) => ({
    textDocument: { uri: doc.uri.toString() },
    position: { line: position.line, character: position.character },
  });
  const toRange = (r) => new vscode.Range(
    r.start.line, r.start.character, r.end.line, r.end.character);

  context.subscriptions.push(
    // what a function takes, promises, and may do
    vscode.languages.registerHoverProvider("sabline", {
      async provideHover(doc, position) {
        const got = await request("textDocument/hover", at(doc, position));
        if (!got || !got.contents) return null;
        const text = got.contents.value || got.contents;
        return new vscode.Hover(new vscode.MarkdownString(text));
      },
    }),

    // functions in scope with their contracts, builtins with their effects
    vscode.languages.registerCompletionItemProvider("sabline", {
      async provideCompletionItems(doc, position) {
        const got = await request("textDocument/completion",
                                  at(doc, position));
        const items = (got && got.items) || [];
        return items.map((it) => {
          const item = new vscode.CompletionItem(
            it.label,
            it.kind === 14 ? vscode.CompletionItemKind.Keyword
                           : vscode.CompletionItemKind.Function);
          if (it.detail) item.detail = it.detail;
          if (it.documentation) {
            item.documentation = new vscode.MarkdownString(it.documentation);
          }
          return item;
        });
      },
    }, ".", " "),

    // jump to where a function is written, across imports
    vscode.languages.registerDefinitionProvider("sabline", {
      async provideDefinition(doc, position) {
        const got = await request("textDocument/definition",
                                  at(doc, position));
        if (!got || !got.uri) return null;
        return new vscode.Location(vscode.Uri.parse(got.uri),
                                   toRange(got.range));
      },
    }),

    // "promises proven before running" above each function
    vscode.languages.registerCodeLensProvider("sabline", {
      async provideCodeLenses(doc) {
        const got = await request("textDocument/codeLens", {
          textDocument: { uri: doc.uri.toString() },
        });
        if (!Array.isArray(got)) return [];
        return got.map((lens) => new vscode.CodeLens(toRange(lens.range), {
          title: lens.command.title, command: "",
        }));
      },
    }),

    // an outline of the file's functions
    vscode.languages.registerDocumentSymbolProvider("sabline", {
      async provideDocumentSymbols(doc) {
        const got = await request("textDocument/documentSymbol", {
          textDocument: { uri: doc.uri.toString() },
        });
        if (!Array.isArray(got)) return [];
        return got.map((sym) => new vscode.DocumentSymbol(
          sym.name, sym.detail || "", vscode.SymbolKind.Function,
          toRange(sym.range), toRange(sym.selectionRange)));
      },
    }),

    // rename a function everywhere it is used in this file
    vscode.languages.registerRenameProvider("sabline", {
      async provideRenameEdits(doc, position, newName) {
        const params = at(doc, position);
        params.newName = newName;
        const got = await request("textDocument/rename", params);
        if (!got || !got.changes) return null;
        const edit = new vscode.WorkspaceEdit();
        for (const [uri, edits] of Object.entries(got.changes)) {
          for (const e of edits) {
            edit.replace(vscode.Uri.parse(uri), toRange(e.range), e.newText);
          }
        }
        return edit;
      },
    }),

    vscode.workspace.onDidOpenTextDocument((doc) => {
      if (isVel(doc)) send({ jsonrpc: "2.0",
        method: "textDocument/didOpen", params: docParams(doc) });
    }),
    vscode.workspace.onDidChangeTextDocument((ev) => {
      if (!isVel(ev.document)) return;
      send({ jsonrpc: "2.0", method: "textDocument/didChange", params: {
        textDocument: { uri: ev.document.uri.toString(),
                        version: ev.document.version },
        contentChanges: [{ text: ev.document.getText() }],
      }});
    }),
    vscode.workspace.onDidSaveTextDocument((doc) => {
      if (isVel(doc)) send({ jsonrpc: "2.0",
        method: "textDocument/didSave", params: {
          textDocument: { uri: doc.uri.toString() },
          text: doc.getText(),
        }});
    }),
    vscode.workspace.onDidCloseTextDocument((doc) => {
      if (isVel(doc)) send({ jsonrpc: "2.0",
        method: "textDocument/didClose", params: {
          textDocument: { uri: doc.uri.toString() } }});
    }),
  );
}

function deactivate() {
  if (proc) {
    send({ jsonrpc: "2.0", id: nextId++, method: "shutdown", params: {} });
    send({ jsonrpc: "2.0", method: "exit" });
    proc = null;
  }
}

module.exports = { activate, deactivate };
