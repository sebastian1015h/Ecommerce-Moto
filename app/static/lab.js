const lab = document.querySelector("[data-lab]");
const form = lab.querySelector("form");
const method = form.elements.method;
const dataset = form.elements.dataset;
const modelId = form.elements.model_id;
const query = form.elements.query;
const note = form.elements.note;
const submit = form.querySelector("button");
const status = lab.querySelector("#lab-status");
const output = lab.querySelector("#lab-response");
const sql = lab.querySelector("#lab-sql");
const contracts = JSON.parse(lab.querySelector("#lab-contracts").textContent);
const map = lab.querySelector("[data-trace-map]");
const nodes = [...map.querySelectorAll("[data-trace-node]")];
const edges = [...map.querySelectorAll("[data-trace-edge]")];
const labels = [...map.querySelectorAll("[data-edge-label]")];
const packet = map.querySelector(".trace-packet");
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
const operations = { GET: "SELECT", POST: "INSERT", PATCH: "UPDATE", DELETE: "DELETE" };
const idleDetails = [
  "Prepara la petición", "Valida y dirige la petición",
  "Envía SQL con parámetros", "Espera una consulta",
];
const timing = lab.querySelector("#trace-db-time");
const clientPath = lab.querySelector("#trace-client-path");
const requestPreview = lab.querySelector("#lab-request");
const responseMeta = lab.querySelector("#trace-response-meta");
const stockSummary = lab.querySelector("#trace-stock-summary");
const stockMode = () => method.value === "GET" && dataset.value === "stock";
const contractKey = () => stockMode() ? "STOCK" : method.value;
const requestPath = () => stockMode() ? "/api/laboratorio/stock-motos"
  : method.value === "GET" ? "/api/laboratorio/inventario" : "/api/laboratorio/muestra";
const writeMethods = ["POST", "PATCH"];
const examples = {
  stock: ["GET", ""],
  ktm: ["GET", "ktm-390-duke"],
  insert: ["POST", "KTM 390 Duke · muestra nueva"],
  update: ["PATCH", "KTM 390 Duke · muestra actualizada"],
  delete: ["DELETE", ""],
};

function requestUrl() {
  const url = new URL(requestPath(), location.origin);
  if (stockMode() && modelId.value) url.searchParams.set("modelo_id", modelId.value);
  if (method.value === "GET" && !stockMode() && query.value.trim()) {
    url.searchParams.set("q", query.value.trim());
  }
  return url;
}

function drawConnections() {
  const bounds = map.getBoundingClientRect();
  for (const [index, edge] of edges.entries()) {
    const from = nodes[index].getBoundingClientRect();
    const to = nodes[index + 1].getBoundingClientRect();
    const dx = (to.left + to.right - from.left - from.right) / 2;
    const dy = (to.top + to.bottom - from.top - from.bottom) / 2;
    let x1, y1, x2, y2;
    const horizontal = Math.abs(dx) > Math.abs(dy);
    if (horizontal) {
      const right = dx > 0;
      x1 = (right ? from.right + 4 : from.left - 4) - bounds.left;
      x2 = (right ? to.left - 4 : to.right + 4) - bounds.left;
      y1 = (from.top + from.bottom) / 2 - bounds.top;
      y2 = (to.top + to.bottom) / 2 - bounds.top;
    } else {
      x1 = (from.left + from.right) / 2 - bounds.left;
      x2 = (to.left + to.right) / 2 - bounds.left;
      y1 = from.bottom + 4 - bounds.top;
      y2 = to.top - 4 - bounds.top;
    }
    edge.setAttribute("d", `M ${x1} ${y1} L ${x2} ${y2}`);
    labels[index].classList.toggle("vertical", !horizontal);
    labels[index].style.left = `${(x1 + x2) / 2}px`;
    labels[index].style.top = `${(y1 + y2) / 2}px`;
  }
}

new ResizeObserver(drawConnections).observe(map);
drawConnections();

function showNode(index, detail, state = "active") {
  for (const node of nodes) node.classList.remove("active");
  if (state) nodes[index].classList.add(state);
  nodes[index].querySelector("[data-node-detail]").textContent = detail;
}

function resetTrace() {
  map.dataset.direction = "out";
  for (const [index, node] of nodes.entries()) {
    node.classList.remove("active", "done", "fault");
    node.querySelector("[data-node-detail]").textContent = idleDetails[index];
  }
  for (const edge of edges) {
    edge.classList.remove("sent", "returned");
    edge.removeAttribute("marker-start");
    edge.removeAttribute("marker-end");
  }
  timing.textContent = "";
  const verb = method.value;
  const operation = operations[verb];
  labels[0].textContent = `HTTP ${verb}`;
  labels[1].textContent = "Llamada";
  labels[2].textContent = operation;
  lab.querySelector("#trace-send").textContent = writeMethods.includes(verb) ? `${verb} · JSON` : `${verb} · sin cuerpo`;
  lab.querySelector("#trace-receive").textContent = "Esperando respuesta HTTP";
  lab.querySelector("#trace-table").textContent = stockMode() ? "moto_offers"
    : verb === "GET" ? "inventory_motos" : "inventory_example · temporal";
  for (const key of ["branch", "database", "schema"]) {
    lab.querySelector(`#trace-${key}`).textContent = "Por verificar";
  }
  responseMeta.textContent = "Esperando respuesta";
  stockSummary.hidden = true;
}

function travel(index, backwards = false, label) {
  const edge = edges[index];
  if (label) labels[index].textContent = label;
  map.dataset.direction = backwards ? "back" : "out";
  edge.classList.add(backwards ? "returned" : "sent");
  edge.removeAttribute(backwards ? "marker-end" : "marker-start");
  edge.setAttribute(backwards ? "marker-start" : "marker-end", "url(#trace-arrow)");
  if (reducedMotion.matches) return Promise.resolve();
  packet.setAttribute("visibility", "visible");
  return new Promise((resolve) => {
    let start;
    const step = (now) => {
      start ??= now;
      const progress = Math.min(1, (now - start) / 380);
      const point = edge.getPointAtLength(edge.getTotalLength() * (backwards ? 1 - progress : progress));
      packet.setAttribute("cx", point.x);
      packet.setAttribute("cy", point.y);
      if (progress < 1) requestAnimationFrame(step);
      else {
        packet.setAttribute("visibility", "hidden");
        resolve();
      }
    };
    requestAnimationFrame(step);
  });
}

function updateControls() {
  dataset.disabled = method.value !== "GET";
  modelId.disabled = !stockMode();
  query.disabled = method.value !== "GET" || stockMode();
  note.disabled = !writeMethods.includes(method.value);
  note.required = !note.disabled;
  lab.querySelector("#lab-query").hidden = query.disabled;
  lab.querySelector("#lab-dataset").hidden = dataset.disabled;
  lab.querySelector("#lab-model").hidden = modelId.disabled;
  lab.querySelector("#lab-payload").hidden = note.disabled;
  const url = requestUrl();
  lab.querySelector("#lab-path").textContent = url.pathname + url.search;
  const verb = method.value;
  const operation = operations[verb];
  const key = contractKey();
  const repository = contracts.repositories[key];
  const route = `${verb} ${url.pathname}${url.search}`;
  lab.querySelector("#trace-handler").textContent = `${contracts.handlers[key]}()`;
  lab.querySelector("#trace-route").textContent = route;
  const noteArgument = writeMethods.includes(verb) ? ", nota" : "";
  lab.querySelector("#trace-operation").textContent = verb === "GET"
    ? `${repository}(${stockMode() ? "modelo_id" : "q"})`
    : `${repository}("${operation.toLowerCase()}"${noteArgument})`;
  const seedOperation = ["PATCH", "DELETE"].includes(verb) ? " → INSERT de muestra" : "";
  lab.querySelector("#trace-driver").textContent = verb === "GET"
    ? "connect() → execute(SELECT)"
    : `begin() → CREATE TEMP TABLE${seedOperation} → execute(${operation}) → COMMIT`;
  lab.querySelector("#trace-db-operation").textContent = verb === "GET" ? "SELECT · lectura" : `${operation} · tabla temporal, eliminada al hacer COMMIT`;
  clientPath.textContent = route;
  requestPreview.textContent = route;
  sql.textContent = `${contracts.sql[key]};`;
  status.textContent = "Listo para enviar";
  output.textContent = "—";
  resetTrace();
}

method.addEventListener("change", updateControls);
dataset.addEventListener("change", updateControls);
modelId.addEventListener("change", updateControls);
for (const button of lab.querySelectorAll("[data-lab-example]")) {
  button.addEventListener("click", () => {
    if (submit.disabled) return;
    const [verb, value] = examples[button.dataset.labExample];
    method.value = verb;
    if (verb === "GET") {
      dataset.value = "stock";
      modelId.value = value;
    } else if (writeMethods.includes(verb)) {
      note.value = value;
    }
    updateControls();
  });
}
updateControls();
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (submit.disabled) return;
  const verb = method.value;
  const url = requestUrl();
  const options = { method: verb, cache: "no-store", signal: AbortSignal.timeout(15000) };
  if (!note.disabled) {
    options.headers = { "Content-Type": "application/json" };
    options.body = JSON.stringify({ nota: note.value });
  }
  const isStock = stockMode();
  clientPath.textContent = `${verb} ${url.pathname}${url.search}`;
  requestPreview.textContent = options.body
    ? `${clientPath.textContent}\nContent-Type: application/json\n\n${JSON.stringify(JSON.parse(options.body), null, 2)}`
    : clientPath.textContent;
  resetTrace();
  submit.disabled = true;
  method.disabled = true;
  dataset.disabled = true;
  modelId.disabled = true;
  query.readOnly = true;
  note.readOnly = true;
  output.textContent = "—";
  status.textContent = "Enviando petición HTTP…";
  if (matchMedia("(max-width: 980px)").matches) {
    lab.querySelector(".lab-trace").scrollIntoView({ behavior: reducedMotion.matches ? "instant" : "smooth", block: "start" });
  }
  showNode(0, "Petición enviada", "done");
  const started = performance.now();
  const pending = fetch(url, options).then(async (response) => {
    const body = await response.text();
    return { response, body, elapsed: Math.round(performance.now() - started) };
  }).catch(() => null);
  try {
    await travel(0);
    showNode(1, "Esperando al servidor…");
    const result = await pending;
    if (!result) {
      showNode(1, "Sin respuesta HTTP", "fault");
      status.textContent = "La petición no llegó a completarse.";
      lab.querySelector("#trace-receive").textContent = "Sin respuesta HTTP";
      responseMeta.textContent = "Sin respuesta HTTP";
      return;
    }
    const { response, body, elapsed } = result;
    const database = response.headers.get("X-Lab-Database");
    const duration = response.headers.get("Server-Timing")?.match(/postgres;dur=([\d.]+)/)?.[1];
    if (database === "ok" || database === "unavailable") {
      status.textContent = "Siguiendo el recorrido a PostgreSQL…";
      showNode(1, "Ruta FastAPI ejecutada", "done");
      await travel(1);
      showNode(2, `${operations[verb]} · consulta parametrizada`, "done");
      await travel(2);
      const count = Number(response.headers.get("X-Lab-Rows"));
      const rows = `${count} ${count === 1 ? "fila" : "filas"}`;
      if (database === "ok") {
        const target = JSON.parse(response.headers.get("X-Lab-Target") || "{}");
        lab.querySelector("#trace-branch").textContent = target.branch || "No informada";
        lab.querySelector("#trace-database").textContent = target.database || "No informada";
        lab.querySelector("#trace-schema").textContent = target.schema || "No informado";
        if (target.schema && target.relation) {
          lab.querySelector("#trace-table").textContent = `${target.schema}.${target.relation}`;
        }
      }
      showNode(3, database === "ok" ? `${rows} ${verb === "GET" ? "devueltas" : "afectadas"}` : "Acceso a PostgreSQL fallido",
        database === "ok" ? "done" : "fault");
      if (duration) timing.textContent = `Acceso a PostgreSQL · ${duration} ms`;
      status.textContent = "Devolviendo la respuesta…";
      await travel(2, true, database === "ok" ? rows : "Error");
      await travel(1, true, "Resultado");
    } else {
      showNode(1, response.status === 422 ? "Validación rechazada" : "Sin consulta confirmada a Neon", "fault");
      showNode(3, response.status === 422 ? "Sin acceso a la base" : "Destino sin confirmar", null);
    }
    await travel(0, true, `HTTP ${response.status}`);
    showNode(0, `Respuesta HTTP ${response.status} recibida`, response.ok ? "done" : "fault");
    status.textContent = `HTTP ${response.status} · ${elapsed} ms`;
    const contentType = response.headers.get("Content-Type")?.split(";")[0];
    const received = `HTTP ${response.status} · ${body ? contentType || "respuesta" : "sin cuerpo"}`;
    responseMeta.textContent = received;
    lab.querySelector("#trace-receive").textContent = received;
    try {
      const payload = body ? JSON.parse(body) : null;
      output.textContent = payload === null ? "Sin cuerpo" : JSON.stringify(payload, null, 2);
      if (isStock && response.ok && payload) {
        const units = payload.unidades_disponibles;
        const models = payload.modelos_encontrados;
        stockSummary.textContent = `${units} ${units === 1 ? "moto disponible" : "motos disponibles"} · ${models} ${models === 1 ? "modelo" : "modelos"}`;
        stockSummary.hidden = false;
      }
    } catch {
      output.textContent = body;
    }
  } finally {
    submit.disabled = false;
    method.disabled = false;
    dataset.disabled = verb !== "GET";
    modelId.disabled = !isStock;
    query.readOnly = false;
    note.readOnly = false;
  }
});
