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
  const purchase = showroom.querySelector("[data-moto-buy]");
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
      if (purchase) {
        const stock = Number(button.dataset.stock);
        const priceLabel = button.dataset.priceLabel;
        purchase.elements.color.value = button.dataset.color;
        purchase.querySelector("button").disabled = !stock || !priceLabel;
        showroom.querySelector("[data-moto-price]").textContent = priceLabel || "Precio por confirmar";
        showroom.querySelector("[data-moto-stock]").textContent =
          stock === 1 ? "1 unidad disponible" : stock ? `${stock} unidades disponibles` : "Agotada";
      }
      if (angleRange) {
        angleViewer.hidden = button !== finishes[0];
        angleRange.disabled = angleViewer.hidden;
        angleRange.value = 0;
        labelAngle(angles[0]);
      }
    });
  }
}

if (document.querySelector("[data-cart]")) {
  let updating = false;

  function openPreview(details) {
    const image = details.querySelector("img[data-preview-src]");
    if (details.open && image.hidden) {
      image.src = image.dataset.previewSrc;
      image.hidden = false;
    }
  }

  document.addEventListener("toggle", (event) => {
    if (event.target.matches("[data-cart-preview]")) openPreview(event.target);
  }, true);

  function activateCart(cart) {
    cart.dataset.cartReady = "";
    for (const form of cart.querySelectorAll("form[data-cart-form]")) {
      const quantity = form.querySelector("input[type=number]");
      if (!quantity) continue;
      for (const button of form.querySelectorAll("[data-cart-step]")) {
        const change = Number(button.dataset.cartStep);
        button.disabled = change < 0 ? +quantity.value <= +quantity.min : +quantity.value >= +quantity.max;
      }
    }
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-cart-step]");
    if (!button || updating) return;
    const input = button.form.elements.quantity;
    const quantity = input.valueAsNumber + Number(button.dataset.cartStep);
    if (Number.isInteger(quantity) && quantity >= +input.min && quantity <= +input.max) {
      input.value = quantity;
      button.form.requestSubmit();
    }
  });

  document.addEventListener("change", (event) => {
    if (event.target.matches("[data-cart-form] input[type=number]") && event.target.checkValidity()) {
      event.target.form.requestSubmit();
    }
  });

  document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!form.matches("[data-cart-form]")) return;
    event.preventDefault();
    if (updating) return;

    const cart = form.closest("[data-cart]");
    const previewOpen = cart.querySelector("[data-cart-preview]")?.open;
    const focusedLine = form.closest("[data-cart-line]").dataset.cartLine;
    const payload = new URLSearchParams(new FormData(form));
    const status = cart.querySelector("[data-cart-status]");
    updating = true;
    cart.setAttribute("aria-busy", "true");
    status.textContent = "Actualizando carrito…";
    try {
      const response = await fetch(form.getAttribute("action"), { method: "POST", body: payload });
      const page = new DOMParser().parseFromString(await response.text(), "text/html");
      const updated = page.querySelector("[data-cart]");
      if (!updated) throw new Error("Respuesta de carrito inválida");
      const nextPreview = updated.querySelector("[data-cart-preview]");
      if (nextPreview && previewOpen) nextPreview.open = true;
      cart.replaceWith(updated);
      activateCart(updated);
      if (nextPreview?.open) openPreview(nextPreview);
      updated.querySelector("[data-cart-status]").textContent = response.ok ? "Carrito actualizado." : "";
      const quantity = updated.querySelector(`[data-cart-line="${CSS.escape(focusedLine)}"] input[type=number]`);
      (quantity || updated.querySelector("h1")).focus({ preventScroll: true });
    } catch {
      status.textContent = "No se pudo actualizar. Intenta de nuevo.";
    } finally {
      cart.removeAttribute("aria-busy");
      updating = false;
    }
  });

  activateCart(document.querySelector("[data-cart]"));
}

function closePanel(panel) {
  if (!panel.open || panel.classList.contains("closing")) return;
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
    panel.close();
    return;
  }
  panel.classList.add("closing");
  setTimeout(() => {
    panel.close();
    panel.classList.remove("closing");
  }, 230);
}

for (const panel of document.querySelectorAll("dialog.slide-panel")) {
  panel.querySelector("[data-panel-close]").addEventListener("click", () => closePanel(panel));
  panel.addEventListener("cancel", (event) => {
    event.preventDefault();
    closePanel(panel);
  });
  panel.addEventListener("click", (event) => {
    if (event.target === panel) {
      const bounds = panel.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right ||
          event.clientY < bounds.top || event.clientY > bounds.bottom) closePanel(panel);
    }
  });
}

const menuButton = document.querySelector("[data-open-menu]");
const siteMenu = document.querySelector("[data-site-menu]");
if (typeof siteMenu?.showModal === "function") {
  menuButton.hidden = false;
  menuButton.addEventListener("click", () => siteMenu.showModal());
}

const cartDrawer = document.querySelector("[data-cart-drawer]");
if (typeof cartDrawer?.showModal === "function") {
  let drawerBusy = false;
  const body = cartDrawer.querySelector("[data-drawer-body]");
  const status = cartDrawer.querySelector("[data-drawer-status]");

  async function showDrawer(url, options = {}) {
    if (drawerBusy) return;
    drawerBusy = true;
    if (!cartDrawer.open) cartDrawer.showModal();
    body.setAttribute("aria-busy", "true");
    status.textContent = "Actualizando carrito…";
    try {
      const response = await fetch(url, { ...options, headers: { "X-Cart-Drawer": "1" } });
      const page = new DOMParser().parseFromString(await response.text(), "text/html");
      const content = page.querySelector("[data-drawer-content]");
      if (!content) throw new Error("Respuesta de carrito inválida");
      const restoreFocus = body.contains(document.activeElement);
      body.replaceChildren(content);
      document.querySelectorAll("[data-cart-count]").forEach((counter) => {
        counter.textContent = content.dataset.count;
      });
      if (restoreFocus) cartDrawer.querySelector("[data-panel-close]").focus();
      status.textContent = response.ok ? "Carrito actualizado." : "";
    } catch {
      status.textContent = "No se pudo actualizar el carrito. Intenta de nuevo.";
    } finally {
      body.removeAttribute("aria-busy");
      drawerBusy = false;
    }
  }

  document.addEventListener("click", (event) => {
    const link = event.target.closest("[data-open-cart]");
    if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    showDrawer(link.href);
  });
  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!form.matches("[data-quick-add]")) return;
    event.preventDefault();
    showDrawer(form.getAttribute("action"), { method: "POST", body: new URLSearchParams(new FormData(form)) });
  });
}

const checkout = document.querySelector("[data-checkout]");
if (checkout) {
  const amount = new Intl.NumberFormat("es-CO");
  const format = (value) => `$ ${amount.format(value)}`;
  checkout.elements.zone.addEventListener("change", () => {
    const shipping = Number(checkout.elements.zone.selectedOptions[0].dataset.shipping);
    const total = Number(checkout.dataset.merchandise) + shipping;
    checkout.elements.expected_total.value = total;
    checkout.querySelector("[data-checkout-shipping]").textContent = format(shipping);
    checkout.querySelector("[data-checkout-total]").textContent = `${format(total)} COP`;
  });
}
