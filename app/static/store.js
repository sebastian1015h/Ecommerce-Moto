const showroom = document.querySelector("[data-showroom]");
if (showroom) {
  const bike = showroom.querySelector("#warehouse-bike");
  const status = showroom.querySelector("#finish-status");
  const finishes = [...showroom.querySelectorAll(".finish")];
  const stage = showroom.querySelector(".warehouse-stage");
  const viewCaption = showroom.querySelector("[data-view-caption]");
  const viewDescription = showroom.querySelector("[data-view-description]");
  const views = [...showroom.querySelectorAll(".workshop-controls button")];
  const angleViewer = showroom.querySelector("[data-angles]");
  const angleRange = angleViewer?.querySelector("input");
  const angleLabel = angleViewer?.querySelector("[data-angle-label]");
  const angles = [...(angleViewer?.querySelectorAll("[data-angle]") ?? [])];
  let selection = 0;

  async function displayPhoto(url, label) {
    const request = ++selection;
    const preview = new Image();
    preview.src = url;
    try {
      await preview.decode();
    } catch {
      if (request === selection) status.textContent = "La imagen no pudo cargarse.";
      return false;
    }
    if (request !== selection) return false;
    bike.src = preview.src;
    bike.alt = `${bike.dataset.model} · ${label}`;
    bike.getAnimations().forEach((animation) => animation.cancel());
    if (!matchMedia("(prefers-reduced-motion: reduce)").matches) {
      bike.animate([{ opacity: .35, transform: "translateX(8px)" }, { opacity: 1, transform: "none" }], 240);
    }
    return true;
  }

  function labelAngle(angle) {
    angleLabel.textContent = angle.dataset.angle;
    angleRange.setAttribute("aria-valuetext", angle.dataset.angle);
  }

  angleRange?.addEventListener("input", async () => {
    const angle = angles[Number(angleRange.value)];
    if (await displayPhoto(angle.dataset.image, angle.dataset.angle)) {
      views[0].click();
      labelAngle(angle);
    }
  });

  for (const button of views) {
    button.addEventListener("click", () => {
      stage.dataset.view = button.dataset.view;
      viewCaption.textContent = button.dataset.caption;
      viewDescription.textContent = button.dataset.description;
      views.forEach((view) => view.setAttribute("aria-pressed", String(view === button)));
    });
  }

  for (const button of finishes) {
    button.addEventListener("click", async () => {
      if (angleRange) angleRange.disabled = true;
      const changed = await displayPhoto(button.dataset.image, button.dataset.color);
      if (!changed) {
        if (angleRange) angleRange.disabled = angleViewer.hidden;
        return;
      }
      status.textContent = `Acabado: ${button.dataset.color}`;
      finishes.forEach((finish) => finish.setAttribute("aria-pressed", String(finish === button)));
      if (angleRange) {
        angleViewer.hidden = button !== finishes[0];
        angleRange.disabled = angleViewer.hidden;
        angleRange.value = 0;
        labelAngle(angles[0]);
      }
    });
  }
}

const lab = document.querySelector("[data-lab]");
if (lab) {
  const form = lab.querySelector("form");
  const method = form.elements.method;
  const query = form.elements.query;
  const note = form.elements.note;
  const submit = form.querySelector("button");
  const status = lab.querySelector("#lab-status");
  const output = lab.querySelector("#lab-response");
  const sql = lab.querySelector("#lab-sql");
  const steps = [...lab.querySelectorAll("[data-step]")];
  const actions = { GET: "Neon · SELECT", POST: "Neon · INSERT", PATCH: "Neon · UPDATE", DELETE: "Neon · DELETE" };
  const sqlExamples = {
    GET: "SELECT slug, marca, modelo, categoria, color\nFROM inventory_motos\nORDER BY created_at DESC LIMIT 500;",
    POST: "INSERT INTO inventory_example VALUES (1, :value)\nRETURNING modelo;",
    PATCH: "UPDATE inventory_example SET modelo = :value\nWHERE id = 1 RETURNING modelo;",
    DELETE: "DELETE FROM inventory_example\nWHERE id = 1 RETURNING modelo;",
  };
  const requestPath = () => method.value === "GET" ? "/api/laboratorio/inventario" : "/api/laboratorio/muestra";
  const setStep = (index) => {
    steps.forEach((step, i) => {
      step.classList.toggle("completed", i < index);
      step.classList.toggle("active", i === index);
    });
  };
  const pause = () => new Promise((resolve) => setTimeout(resolve,
    matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 240));

  function updateControls() {
    query.disabled = method.value !== "GET";
    note.disabled = !["POST", "PATCH"].includes(method.value);
    note.required = !note.disabled;
    lab.querySelector("#lab-query").hidden = query.disabled;
    lab.querySelector("#lab-payload").hidden = note.disabled;
    lab.querySelector("#lab-path").textContent = requestPath();
    steps[2].textContent = actions[method.value];
    sql.textContent = sqlExamples[method.value];
    setStep(-1);
  }

  method.addEventListener("change", updateControls);
  updateControls();
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const verb = method.value;
    const path = requestPath();
    const url = new URL(path, location.origin);
    const options = { method: verb, signal: AbortSignal.timeout(10000) };
    if (!note.disabled) {
      options.headers = { "Content-Type": "application/json" };
      options.body = JSON.stringify({ nota: note.value });
    }
    if (verb === "GET" && query.value.trim()) url.searchParams.set("q", query.value.trim());

    submit.disabled = true;
    method.disabled = true;
    status.textContent = `Enviando ${verb} ${url.pathname}${url.search}…`;
    output.textContent = "—";
    setStep(0);
    const started = performance.now();
    const result = fetch(url, options).then(async (response) => {
      const elapsed = Math.round(performance.now() - started);
      const body = response.status === 204 ? "Sin cuerpo" : JSON.stringify(await response.json(), null, 2);
      return { status: response.status, body, elapsed };
    }).catch(() => null);
    await pause();
    setStep(1);
    await pause();
    setStep(2);
    const response = await result;
    await pause();
    if (response) {
      setStep(3);
      status.textContent = `HTTP ${response.status} · ${response.elapsed} ms`;
      output.textContent = response.body;
    } else {
      setStep(-1);
      status.textContent = "No se pudo completar la petición. Intenta de nuevo.";
    }
    submit.disabled = false;
    method.disabled = false;
  });
}
