const form = document.querySelector("#pesquisa");
const button = document.querySelector("#pesquisar");
const errorBox = document.querySelector("#erro");
const flow = document.querySelector("#fluxo");
const log = document.querySelector("#log");
const result = document.querySelector("#resultado");
const report = document.querySelector("#relatorio");
const lanes = {
  busca: document.querySelector("#buscas"),
  analista: document.querySelector("#analista"),
  sintetizador: document.querySelector("#sintetizador"),
};
const WAITING = {
  busca: "Esperando o coordenador",
  analista: "Esperando as buscas",
  sintetizador: "Esperando a análise",
};
const TOOL_NAMES = {
  WebSearch: "pesquisou",
  WebFetch: "abriu",
  Read: "leu",
  Write: "criou",
  Edit: "atualizou",
};
const STATUS_TEXT = { running: "rodando", ok: "terminou", partial: "terminou com falhas", failed: "falhou" };

// Estado da pesquisa atual.
let runDir = "";
let startedAt = 0;
let ticker = null;
const channels = new Map(); // id da chamada Agent -> { element, start }
const toolLines = new Map(); // id da ferramenta -> linha na tela
const pendingMarks = new Map(); // aviso que chegou antes da linha da ferramenta

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function seconds(since) {
  return `${Math.round((Date.now() - since) / 1000)} s`;
}

function shortDetail(tool, detail) {
  if (tool === "WebFetch") {
    try {
      const url = new URL(detail);
      return url.hostname.replace(/^www\./, "") + url.pathname;
    } catch {
      return detail;
    }
  }
  if (runDir && detail.startsWith(`${runDir}/`)) return detail.slice(runDir.length + 1);
  return detail;
}

function addLogLine(text, className) {
  const line = el("li", className);
  line.append(el("span", "quando", seconds(startedAt)), el("span", "texto", text));
  log.append(line);
  return line;
}

function setWaiting(agent) {
  lanes[agent].replaceChildren(el("p", "espera", WAITING[agent]));
}

function mark(toolId, text) {
  const line = toolLines.get(toolId);
  if (!line) {
    pendingMarks.set(toolId, text);
    return;
  }
  line.classList.add("barrada");
  line.append(el("span", "aviso", text));
}

function setStatus(channel, status) {
  channel.dataset.status = status;
  channel.querySelector(".estado").textContent = STATUS_TEXT[status];
}

function setStat(key, value, { warn = false, note = "" } = {}) {
  const item = document.querySelector(`[data-chave="${key}"]`);
  item.hidden = false;
  item.classList.toggle("alerta", warn);
  const dd = item.querySelector("dd");
  dd.textContent = value;
  if (note) dd.append(el("small", "", note));
}

function money(value) {
  return `US$ ${value.toFixed(3).replace(".", ",")}`;
}

function renderMarkdown(target, markdown) {
  if (!window.marked || !window.DOMPurify) {
    target.replaceChildren(el("pre", "", markdown));
    return;
  }
  target.innerHTML = DOMPurify.sanitize(marked.parse(markdown));
  for (const link of target.querySelectorAll("a[href^='http']")) {
    link.target = "_blank";
    link.rel = "noopener noreferrer";
  }
}

const handlers = {
  start(event) {
    runDir = event.run_dir;
    flow.hidden = false;
    document.querySelector("#pasta").textContent = `Arquivos em ${event.run_dir.split("/").slice(-2).join("/")}`;
    Object.keys(lanes).forEach(setWaiting);
    addLogLine(event.mode === "sequencial" ? "recebeu o pedido; buscas uma por vez" : "recebeu o pedido");
  },

  agent_start(event) {
    const lane = lanes[event.agent] ?? lanes.busca;
    lane.querySelector(".espera")?.remove();
    const channel = el("article", "canal");
    const header = el("header");
    header.append(el("span", "led"), el("h3", "", event.description), el("span", "estado"), el("span", "tempo", "0 s"));
    const prompt = el("details", "mandado");
    prompt.append(el("summary", "", "O que o coordenador mandou"), el("pre", "", event.prompt));
    channel.append(header, el("ol", "ferramentas"), el("p", "saida"), prompt);
    setStatus(channel, "running");
    lane.append(channel);
    channels.set(event.id, { element: channel, start: Date.now() });
    addLogLine(`chamou ${event.agent}: ${event.description}`);
  },

  tool(event) {
    const text = `${TOOL_NAMES[event.tool] ?? event.tool} ${shortDetail(event.tool, event.detail)}`;
    const channel = channels.get(event.parent);
    let line;
    if (channel) {
      line = el("li");
      line.append(el("span", "texto", text));
      channel.element.querySelector(".ferramentas").append(line);
    } else {
      line = addLogLine(text);
    }
    toolLines.set(event.id, line);
    if (pendingMarks.has(event.id)) {
      mark(event.id, pendingMarks.get(event.id));
      pendingMarks.delete(event.id);
    }
  },

  notice(event) {
    if (event.tool_id) mark(event.tool_id, event.text);
    else addLogLine(`${event.source}: ${event.text}`, "aviso");
  },

  tool_error(event) {
    mark(event.id, event.text.slice(0, 120));
  },

  agent_end(event) {
    const channel = channels.get(event.id);
    if (!channel) return;
    const { element } = channel;
    setStatus(element, event.status);
    element.querySelector(".tempo").textContent = `${event.seconds} s`;
    const output = element.querySelector(".saida");
    output.textContent = event.label;
    if (event.file) output.append(el("span", "arquivo", event.file));
    channels.delete(event.id);
  },

  done(event) {
    if (event.subtype !== "success") addLogLine(`parou antes do fim (${event.subtype})`, "aviso");
    if (event.result) addLogLine(event.result);
  },

  report(event) {
    result.hidden = false;
    renderMarkdown(report, event.markdown);
    document.querySelector("#salvo").textContent = `Salvo em ${event.path.split("/").slice(-3).join("/")}`;
  },

  no_report(event) {
    result.hidden = false;
    renderMarkdown(report, `O sintetizador não terminou, então não há relatório.\n\n${event.coverage}`);
  },

  checks(event) {
    const { links, disputes, quotes } = event;
    setStat("links", `${links.total - links.outside.length} de ${links.total}`, { warn: links.outside.length > 0 });
    if (disputes) {
      setStat("disputas", `${disputes.report} de ${disputes.analysis}`, {
        warn: disputes.report !== disputes.analysis,
      });
    }
    if (quotes) {
      const missing = quotes.mismatched;
      setStat("trechos", `${quotes.checked - missing.length} de ${quotes.checked}`, { warn: missing.length > 0 });
      showMismatches(missing);
    }
  },

  timing(event) {
    setStat("buscas", `${event.window} s`, { note: `somadas, ${event.sum} s` });
  },

  cost(event) {
    result.hidden = false;
    setStat("custo", money(event.total));
    setStat("tempo", `${Math.round(event.seconds)} s`);
  },

  error(event) {
    showError(`A pesquisa parou: ${event.message}`);
  },
};

function showMismatches(items) {
  const box = document.querySelector("#divergencias");
  box.hidden = items.length === 0;
  box.querySelector("summary").textContent = `Trechos que não mostram o número do valor (${items.length})`;
  box.querySelector("ul").replaceChildren(
    ...items.map((item) => {
      const line = el("li");
      line.append(
        el("strong", "", `${item.part}, ${item.criterion}: `),
        el("span", "", `${item.value} `),
        el("q", "", item.quote),
      );
      return line;
    }),
  );
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}

function reset() {
  errorBox.hidden = true;
  flow.hidden = true;
  result.hidden = true;
  log.replaceChildren();
  report.replaceChildren();
  document.querySelector("#salvo").textContent = "";
  document.querySelector("#divergencias").hidden = true;
  for (const item of document.querySelectorAll("[data-chave]")) item.hidden = true;
  channels.clear();
  toolLines.clear();
  pendingMarks.clear();
  startedAt = Date.now();
}

function tick() {
  for (const { element, start } of channels.values()) {
    element.querySelector(".tempo").textContent = seconds(start);
  }
}

// A resposta chega aos poucos, um evento JSON por linha.
async function readEvents(body) {
  const reader = body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    const lines = buffer.split("\n");
    buffer = lines.pop();
    for (const line of lines) {
      if (!line) continue;
      const event = JSON.parse(line);
      handlers[event.type]?.(event);
    }
  }
}

async function run() {
  reset();
  button.disabled = true;
  button.textContent = "Pesquisando…";
  ticker = setInterval(tick, 1000);
  try {
    const response = await fetch("/api/pesquisa", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pedido: document.querySelector("#pedido").value,
        sequencial: document.querySelector("#sequencial").checked,
        simularTimeout: document.querySelector("#timeout").checked,
      }),
    });
    if (!response.ok) {
      const { error } = await response.json().catch(() => ({ error: `erro ${response.status}` }));
      showError(error);
      return;
    }
    await readEvents(response.body);
  } catch {
    showError("A conexão com o servidor caiu. Confira se o tela.py continua rodando no terminal.");
  } finally {
    clearInterval(ticker);
    button.disabled = false;
    button.textContent = "Pesquisar";
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  run();
});

// Ctrl+Enter no campo do pedido também pesquisa.
document.querySelector("#pedido").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey) && !button.disabled) form.requestSubmit();
});
