"use strict";

const NEXUS_OFFICIAL_URL = "https://nexus.con"; // Dirección oficial del proyecto NEXUS Tech Market
const API_HOST = window.location.hostname || "127.0.0.1";
const API_PROTOCOL = window.location.protocol === "https:" ? "https:" : "http:";
const API_BASE = (window.NEXUS_API_URL || (window.location.protocol === "https:"
  ? `${window.location.origin}/api`
  : `${API_PROTOCOL}//${API_HOST}:5000/api`)).replace(/\/$/, "");
const CART_KEY = "nexus-cart-v1";
const money = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  maximumFractionDigits: 0
});

const state = {
  products: [],
  category: "Todos",
  query: "",
  cart: readCart(),
  csrfToken: "",
  adminName: "",
  backendReady: false
};
let latestRegisteredOrder = null;

const $ = (selector) => document.querySelector(selector);

function readCart() {
  try {
    const cart = JSON.parse(localStorage.getItem(CART_KEY) || "{}");
    return cart && typeof cart === "object" && !Array.isArray(cart) ? cart : {};
  } catch {
    return {};
  }
}

function persistCart() {
  localStorage.setItem(CART_KEY, JSON.stringify(state.cart));
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[character]);
}

function downloadHtml(filename, markup) {
  const blob = new Blob([markup], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function printableDocument({ title, code, subtitle, rows, total, status, badge, imageUrl, productName, sourceUrl }) {
  const itemRows = rows.map((item) => `<tr><td>${escapeHtml(item.label)}</td><td>${escapeHtml(item.detail || "")}</td><td>${escapeHtml(item.value)}</td></tr>`).join("");
  const productImage = imageUrl ? `<div class="doc-product"><img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(productName || title)}" referrerpolicy="no-referrer" onerror="this.parentElement.hidden=true"><span>${escapeHtml(productName || "")}</span></div>` : "";
  const sourceLink = sourceUrl ? `<p><a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">Consultar producto y vendedor</a></p>` : "";
  return `<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escapeHtml(title)} · ${escapeHtml(code)}</title><style>body{margin:0;padding:32px;background:#f4f0f8;color:#21172b;font:15px/1.55 Arial,sans-serif}.sheet{max-width:760px;margin:auto;padding:40px;background:white;border:1px solid #e5dcef;border-radius:18px;box-shadow:0 20px 60px #26163218}.brand{color:#7653a5;font-weight:800;letter-spacing:.18em}.code{display:inline-block;padding:8px 12px;border-radius:8px;background:#f3edf8;color:#674486;font-weight:bold}.notice{padding:14px;border-left:4px solid #b99a57;background:#fbf7ed}.doc-product{display:flex;align-items:center;gap:18px;margin:22px 0;padding:14px;border:1px solid #e5dcef;border-radius:12px;background:#faf8fd}.doc-product img{width:110px;height:110px;object-fit:contain;border-radius:8px;background:white}.doc-product span{font-weight:bold;font-size:16px;color:#3d2b52}table{width:100%;border-collapse:collapse;margin:25px 0}td,th{text-align:left;padding:12px;border-bottom:1px solid #e9e3ed}th{color:#766c7e;font-size:12px;text-transform:uppercase}.total{font-size:22px;font-weight:bold;text-align:right}.foot{margin-top:32px;color:#766c7e;font-size:12px}@media print{body{padding:0;background:white}.sheet{border:0;box-shadow:none}}</style><main class="sheet"><div class="brand">NEXUS · TECH MARKET</div><h1>${escapeHtml(title)}</h1><p>${escapeHtml(subtitle)}</p>${productImage}${sourceLink}<p class="code">Código: ${escapeHtml(code)}</p>${badge ? `<p class="code code-badge">${escapeHtml(badge)}</p>` : ""}${status ? `<p class="notice">${escapeHtml(status)}</p>` : ""}<table><thead><tr><th>Concepto</th><th>Detalle</th><th>Valor</th></tr></thead><tbody>${itemRows}</tbody></table>${total ? `<p class="total">Total de referencia: ${escapeHtml(total)}</p>` : ""}<p class="foot">Documento académico generado por NEXUS. No es factura electrónica, soporte fiscal, recibo de pago ni confirmación de compra. No se procesan pagos reales.</p><button onclick="window.print()">Imprimir / Guardar como PDF</button></main></html>`;
}

function downloadQuote(product) {
  const uniquePart = window.crypto?.randomUUID
    ? window.crypto.randomUUID().slice(0, 6).toUpperCase()
    : Math.random().toString(16).slice(2, 8).toUpperCase();
  const quoteCode = `COT-${new Date().toISOString().slice(0, 10).replaceAll("-", "")}-${uniquePart}`;
  const markup = printableDocument({
    title: "Cotización de referencia",
    code: quoteCode,
    subtitle: `Producto: ${product.name} · Consulta: ${new Date().toLocaleString("es-CO")}`,
    imageUrl: product.image_url,
    productName: product.name,
    sourceUrl: product.product_url,
    rows: [
      { label: product.name, detail: `${product.category} / ${productDisplayDescription(product)}`, value: money.format(product.price) },
      { label: "Vendedor y fecha", detail: `${product.seller || "Fuente no indicada"} / ${product.checked_on || "sin fecha"}`, value: "COP" }
    ],
    total: money.format(product.price),
    status: `Precio de referencia consultado el ${product.checked_on || "sin fecha registrada"}. Verifica precio, disponibilidad, variante y condiciones con el vendedor antes de comprar.`
  });
  downloadHtml(`${quoteCode}.html`, markup);
  showToast(`Cotización ${quoteCode} descargada. No es un pago.`, "success");
}

function downloadOrderRecord(order) {
  const rows = order.items.map((item) => {
    const product = state.products.find((entry) => entry.id === item.product_id || entry.name === item.product_name);
    return {
      label: `${item.quantity} × ${item.product_name}`,
      detail: `Precio unitario de referencia: ${money.format(item.unit_price)}`,
      value: money.format(item.quantity * item.unit_price)
    };
  });
  const first = state.products.find((entry) => order.items.some((item) => entry.id === item.product_id || entry.name === item.product_name));
  const markup = printableDocument({
    title: "Comprobante de registro de compra",
    code: order.payment_code || order.number,
    badge: `Orden ${order.number} · Estado: ${order.status}`,
    subtitle: `Compra registrada para ${order.customer_name} · ${order.created_at}`,
    imageUrl: first?.image_url || "",
    productName: order.items.map((item) => `${item.quantity} × ${item.product_name}`).join(" + "),
    rows,
    total: money.format(order.total),
    status: `Código de compra ${order.payment_code || order.number}. Verifícalo en la tienda con el consultor de códigos. Estado actual: ${order.status}. Este comprobante acredita el registro local de la compra simulada; no es factura electrónica ni soporte fiscal y no confirma despacho.`
  });
  downloadHtml(`${order.payment_code || order.number}-comprobante.html`, markup);
  showToast(`Comprobante ${order.payment_code || order.number} descargado.`, "success");
}

function showToast(message, type = "") {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`.trim();
  toast.textContent = message;
  $("#toast-region").append(toast);
  window.setTimeout(() => toast.remove(), 4500);
}

async function apiRequest(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body) headers.set("Content-Type", "application/json");
  if (options.method && options.method !== "GET") {
    const token = state.csrfToken || await getCsrfToken();
    headers.set("X-CSRF-Token", token);
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: "include"
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `El servidor respondió ${response.status}.`);
  return payload;
}

async function getCsrfToken() {
  const result = await apiRequest("/security");
  state.csrfToken = result.csrf_token;
  return state.csrfToken;
}

async function loadCatalog() {
  const grid = $("#product-grid");
  try {
    const result = await apiRequest("/products");
    state.products = result.products;
    state.backendReady = true;
    $("#results-count").textContent = `${state.products.length} productos`;
    renderFilters();
    renderProducts();
    refreshCart();
    await getCsrfToken();
  } catch (error) {
    try {
      const response = await fetch("catalog.json");
      if (!response.ok) throw new Error("No se pudo cargar el catálogo local.");
      state.products = await response.json();
      $("#results-count").textContent = `${state.products.length} productos · API sin conexión`;
      renderFilters();
      renderProducts();
      refreshCart();
      showToast("Catálogo en modo visual. Inicia el backend para enviar solicitudes o usar el panel.", "error");
    } catch {
      grid.innerHTML = '<div class="empty-state">No se pudo cargar el catálogo. Inicia el backend y vuelve a cargar esta página.</div>';
      $("#results-count").textContent = "Catálogo no disponible";
      showToast(error.message, "error");
    }
  }
}

function renderFilters() {
  const categories = ["Todos", ...new Set(state.products.map((product) => product.category))];
  $("#category-filters").innerHTML = categories.map((category) =>
    `<button class="filter-button ${category === state.category ? "active" : ""}" type="button" data-category="${escapeHtml(category)}">${escapeHtml(category)}</button>`
  ).join("");
  $("#category-filters").querySelectorAll("[data-category]").forEach((button) => {
    button.addEventListener("click", () => {
      state.category = button.dataset.category;
      renderFilters();
      renderProducts();
    });
  });
}

function filteredProducts() {
  const query = state.query.trim().toLocaleLowerCase("es");
  return state.products.filter((product) => {
    const matchesCategory = state.category === "Todos" || product.category === state.category;
    const searchable = `${product.name} ${product.category} ${productDisplayDescription(product)}`.toLocaleLowerCase("es");
    return matchesCategory && (!query || searchable.includes(query));
  });
}

function purchaseChecks(product) {
  const description = `${product.name} ${productDisplayDescription(product)}`.toLocaleLowerCase("es");
  const checks = {
    "Computadores": ["Confirma la combinación exacta de procesador, memoria RAM, almacenamiento y sistema operativo con el vendedor.", "Verifica distribución de teclado, cargador, garantía y condiciones de entrega."],
    "Tabletas": ["Confirma si la versión es Wi‑Fi o celular, la capacidad de almacenamiento y los accesorios incluidos.", "Verifica compatibilidad de lápiz/teclado, sistema operativo, garantía y estado de batería."],
    "Celulares": ["Confirma almacenamiento, color y referencia exacta; revisa bandas de red y compatibilidad con tu operador.", "Verifica estado de batería, cargador incluido, garantía y soporte de actualizaciones."],
    "Celulares Windows": ["Confirma que el equipo encienda, esté desbloqueado y tenga batería funcional; estos modelos son de colección.", "Revisa compatibilidad de red, disponibilidad de repuestos y que Windows Mobile ya no recibe soporte vigente."],
    "Celulares Gamer": ["Confirma la variante de memoria/almacenamiento, bandas de red y compatibilidad del cargador.", "Verifica garantía, estado de batería y disponibilidad de accesorios de refrigeración específicos."],
    "Tabletas Windows": ["Confirma procesador, RAM, almacenamiento, edición de Windows y si incluye teclado/cargador.", "En equipos usados, valida batería, estado físico, activación de Windows y garantía del vendedor."],
    "Tabletas Gamer": ["Confirma generación, memoria, almacenamiento y versión regional del sistema.", "Verifica cargador, estado de batería, garantía y compatibilidad de accesorios."],
    "Componentes": ["Comprueba compatibilidad física y eléctrica con tu equipo: socket/interfaz, formato y potencia.", "Confirma versión, accesorios incluidos, garantía y política de devolución."],
    "Monitores": ["Confirma resolución, frecuencia, tipo de panel y puertos que necesitas.", "Verifica soporte VESA, cables incluidos, garantía y política de píxeles defectuosos."],
    "Videojuegos": ["Confirma plataforma/región, capacidad y si incluye control, cables o juegos.", "Verifica estado, garantía y compatibilidad de los accesorios con tu consola."],
    "Accesorios": ["Confirma conector, estándar, dimensiones y compatibilidad con tu dispositivo.", "Verifica contenido del paquete, garantía y condiciones de devolución."],
    "Impresión": ["Confirma conectividad, consumibles compatibles y funciones que necesitas.", "Verifica tintas iniciales, garantía y disponibilidad de repuestos/consumibles en Colombia."]
  };
  const selected = checks[product.category] || ["Confirma la referencia y la variante exacta con el vendedor.", "Revisa compatibilidad, garantía, disponibilidad y condiciones de entrega antes de comprar."];
  if (/usad|outlet|importaci|colecci/.test(description)) {
    selected.push("La ficha indica unidad usada, outlet, importada o de colección: solicita fotos actuales y confirma estado, garantía, impuestos y costo de envío.");
  }
  if (product.id === "samsung-galaxy-a57-256") selected.push("Esta variante es 8 GB RAM / 256 GB; Samsung indica que la serie A57 no admite tarjeta microSD. Comprueba las bandas 5G de la versión ofrecida con tu operador.");
  if (product.id === "asus-rog-phone-8-pro") selected.push("Para la variante de 512 GB, ASUS publica 16 GB de RAM (la de 24 GB corresponde a 1 TB); confirma la variante y compatibilidad de bandas antes de comprar.");
  return selected;
}

function productDisplayDescription(product) {
  if (product.id === "samsung-galaxy-a57-256") return "Galaxy A57 5G: pantalla 6,7\" FHD+ Super AMOLED+ hasta 120 Hz, 8 GB de RAM y 256 GB de almacenamiento. Revisa compatibilidad 5G con tu operador; esta serie no admite microSD.";
  if (product.id === "asus-rog-phone-8-pro") return "ROG Phone 8 Pro de 512 GB: Snapdragon 8 Gen 3, 16 GB de RAM, pantalla AMOLED de 6,78\" con frecuencia de hasta 165 Hz y batería de 5.500 mAh. ASUS también ofrece una variante distinta de 24 GB/1 TB.";
  return product.description || "Consulta los detalles de esta referencia con el vendedor.";
}

function productOfficialSource(product) {
  if (product.id === "samsung-galaxy-a57-256") return "https://news.samsung.com/co/samsung-presenta-en-colombia-los-nuevos-galaxy-a57-5g-y-galaxy-a37-5g";
  if (product.id === "asus-rog-phone-8-pro") return "https://rog.asus.com/phones/rog-phone-8-pro/spec/";
  return "";
}

function openProductDetails(productId) {
  const product = state.products.find((entry) => entry.id === productId);
  if (!product) return;
  const image = product.image_url
    ? `<img class="product-detail-image" src="${escapeHtml(product.image_url)}" alt="${escapeHtml(product.name)}" referrerpolicy="no-referrer" onerror="this.hidden=true;this.nextElementSibling.hidden=false"><span class="product-detail-fallback" hidden>${escapeHtml(product.glyph || "N")}</span>`
    : `<span class="product-detail-fallback">${escapeHtml(product.glyph || "N")}</span>`;
  const officialSource = productOfficialSource(product);
  const source = product.product_url
    ? `<a class="product-detail-source" href="${escapeHtml(product.product_url)}" target="_blank" rel="noopener noreferrer">Consultar precio y disponibilidad en ${escapeHtml(product.seller || "la tienda de referencia")} ↗</a>${officialSource ? ` <a class="product-detail-source" href="${escapeHtml(officialSource)}" target="_blank" rel="noopener noreferrer">Ver especificaciones del fabricante ↗</a>` : ""}`
    : `<p class="product-detail-muted">Fuente comercial no disponible para esta ficha.</p>`;
  const checks = purchaseChecks(product).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const checkedOn = product.checked_on ? new Date(`${product.checked_on}T12:00:00`).toLocaleDateString("es-CO", {year:"numeric",month:"long",day:"numeric"}) : "sin fecha de consulta registrada";
  $("#product-detail-content").innerHTML = `
    <div class="product-detail-layout">
      <div class="product-detail-media">${image}<span class="product-detail-badge">${escapeHtml(product.tag || product.category)}</span></div>
      <div class="product-detail-info">
        <span class="eyebrow">${escapeHtml(product.category)} · FICHA DE PRODUCTO</span>
        <h2 id="product-detail-title">${escapeHtml(product.name)}</h2>
        <p class="product-detail-description">${escapeHtml(productDisplayDescription(product))}</p>
        <div class="product-detail-price"><small>PRECIO DE REFERENCIA · COP</small><strong>${money.format(product.price)}</strong><span>Consultado: ${escapeHtml(checkedOn)}. El vendedor puede actualizar el precio o inventario.</span></div>
        <section class="product-detail-section"><h3>Antes de comprar</h3><ul>${checks}</ul></section>
        <div class="product-detail-source-wrap">${source}</div>
        <div class="product-detail-actions">
          <button class="button button-outline" type="button" data-detail-add="${escapeHtml(product.id)}">Añadir al carrito</button>
          <button class="button button-primary" type="button" data-detail-buy="${escapeHtml(product.id)}">Solicitar compra <span>→</span></button>
        </div>
        <button class="product-detail-quote" type="button" data-detail-quote="${escapeHtml(product.id)}">Descargar cotización de este producto</button>
        <p class="product-detail-disclaimer">La cotización es una referencia en pesos colombianos. La solicitud se registra en el entorno local y no realiza un pago.</p>
      </div>
    </div>`;
  $("#product-detail-modal").showModal();
}

function renderProducts() {
  const products = filteredProducts();
  $("#results-count").textContent = `${products.length} ${products.length === 1 ? "producto" : "productos"}${state.backendReady ? "" : " · API sin conexión"}`;
  $("#product-grid").innerHTML = products.length ? products.map((product) => `
    <article class="product-card" data-product-detail="${escapeHtml(product.id)}" tabindex="0" role="group" aria-label="${escapeHtml(product.name)}. Presiona Enter para ver detalles">
      <div class="product-art" data-category="${escapeHtml(product.category)}" aria-label="${product.image_url ? "Fotografía" : "Ilustración"} de ${escapeHtml(product.name)}">
        <button class="product-download-tab" type="button" data-quote="${escapeHtml(product.id)}" title="Descargar ficha de cotización con código">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12m0 0 4-4m-4 4-4-4M4 21h16"></path></svg> Descargar
        </button>
        <span class="product-tag">${escapeHtml(product.tag)}</span>
        ${product.image_url ? `<img class="product-image" src="${escapeHtml(product.image_url)}" alt="${escapeHtml(product.name)}" loading="lazy" referrerpolicy="no-referrer" onerror="this.hidden=true;this.nextElementSibling.hidden=false">` : ""}
        <span class="product-icon" aria-hidden="true" ${product.image_url ? "hidden" : ""}>${escapeHtml(product.glyph)}</span>
      </div>
      <div class="product-details">
        <span class="product-category">${escapeHtml(product.category)}</span>
        <h3 class="product-name">${escapeHtml(product.name)}</h3>
        <p class="product-description">${escapeHtml(productDisplayDescription(product))}</p>
        ${product.product_url ? `<a class="product-source" href="${escapeHtml(product.product_url)}" target="_blank" rel="noopener noreferrer">Ver fuente · ${escapeHtml(product.seller || "referencia")}</a>` : ""}
        <button class="quote-download" type="button" data-quote="${escapeHtml(product.id)}">Descargar cotización</button>
        <div class="product-bottom">
          <span class="product-price">${money.format(product.price)}<small>Precio de referencia · COP</small></span>
          <button class="add-button" type="button" data-add="${escapeHtml(product.id)}" aria-label="Añadir ${escapeHtml(product.name)} al carrito">+</button>
        </div>
      </div>
    </article>`).join("") : '<div class="empty-state">No encontramos productos con esa búsqueda.</div>';
  $("#product-grid").querySelectorAll("[data-add]").forEach((button) => {
    button.addEventListener("click", () => addToCart(button.dataset.add));
  });
  $("#product-grid").querySelectorAll("[data-quote]").forEach((button) => {
    button.addEventListener("click", () => {
      const product = state.products.find((entry) => entry.id === button.dataset.quote);
      if (product) downloadQuote(product);
    });
  });
  $("#product-grid").querySelectorAll("[data-product-detail]").forEach((card) => {
    card.addEventListener("click", (event) => {
      if (event.target.closest("button, a")) return;
      openProductDetails(card.dataset.productDetail);
    });
    card.addEventListener("keydown", (event) => {
      if ((event.key === "Enter" || event.key === " ") && event.target === card) {
        event.preventDefault();
        openProductDetails(card.dataset.productDetail);
      }
    });
  });
}

function addToCart(productId) {
  const product = state.products.find((entry) => entry.id === productId);
  if (!product) return;
  state.cart[productId] = Math.min((state.cart[productId] || 0) + 1, 10);
  persistCart();
  refreshCart();
  showToast(`${product.name} se añadió al carrito.`, "success");
}

function updateQuantity(productId, delta) {
  const nextQuantity = (state.cart[productId] || 0) + delta;
  if (nextQuantity <= 0) delete state.cart[productId];
  else state.cart[productId] = Math.min(nextQuantity, 10);
  persistCart();
  refreshCart();
}

function cartDetails() {
  return Object.entries(state.cart).map(([id, quantity]) => {
    const product = state.products.find((entry) => entry.id === id);
    return product ? { ...product, quantity } : null;
  }).filter(Boolean);
}

function refreshCart() {
  const items = cartDetails();
  const quantity = items.reduce((total, item) => total + item.quantity, 0);
  const total = items.reduce((sum, item) => sum + item.price * item.quantity, 0);
  $("#cart-count").textContent = quantity;
  $("#drawer-count").textContent = `(${quantity})`;
  $("#cart-total").textContent = money.format(total);
  $("#checkout-open").disabled = items.length === 0;
  $("#cart-items").innerHTML = items.length ? items.map((item) => `
    <div class="cart-item">
      <span class="cart-item-icon" aria-hidden="true">${escapeHtml(item.glyph)}</span>
      <div><h3 class="cart-item-name">${escapeHtml(item.name)}</h3><span class="cart-item-price">${money.format(item.price)} c/u</span>
        <div class="quantity-controls"><button type="button" data-quantity="${escapeHtml(item.id)}" data-delta="-1" aria-label="Quitar uno">−</button><span>${item.quantity}</span><button type="button" data-quantity="${escapeHtml(item.id)}" data-delta="1" aria-label="Añadir uno">+</button></div>
      </div>
      <button class="remove-item" type="button" data-remove="${escapeHtml(item.id)}" aria-label="Eliminar ${escapeHtml(item.name)}">×</button>
    </div>`).join("") : '<div class="cart-empty">Todavía no hay productos en tu carrito.<br>Explora el catálogo y añade algo que te interese.</div>';
  $("#cart-items").querySelectorAll("[data-quantity]").forEach((button) => {
    button.addEventListener("click", () => updateQuantity(button.dataset.quantity, Number(button.dataset.delta)));
  });
  $("#cart-items").querySelectorAll("[data-remove]").forEach((button) => {
    button.addEventListener("click", () => updateQuantity(button.dataset.remove, -(state.cart[button.dataset.remove] || 0)));
  });
}

function setDrawer(open) {
  $("#cart-drawer").classList.toggle("open", open);
  $("#drawer-backdrop").classList.toggle("open", open);
  $("#cart-drawer").setAttribute("aria-hidden", String(!open));
}

function openCheckout() {
  if (!cartDetails().length) return;
  const totalUnits = cartDetails().reduce((sum, item) => sum + item.quantity, 0);
  $("#checkout-summary").textContent = `${totalUnits} artículo(s) · ${$("#cart-total").textContent}`;
  setDrawer(false);
  $("#checkout-modal").showModal();
}

$("#search-input").addEventListener("input", (event) => {
  state.query = event.target.value;
  renderProducts();
});

$("#search-input").addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    event.target.value = "";
    state.query = "";
    renderProducts();
  }
});

document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    $("#search-input").focus();
  }
  if (event.key === "Escape") setDrawer(false);
});

$("#mobile-menu").addEventListener("click", () => $(".main-nav").classList.toggle("mobile-open"));
$(".cart-open").addEventListener("click", () => setDrawer(true));
$(".drawer-close").addEventListener("click", () => setDrawer(false));
$("#drawer-backdrop").addEventListener("click", () => setDrawer(false));
$("#checkout-open").addEventListener("click", openCheckout);
$(".modal-close").addEventListener("click", () => $("#checkout-modal").close());
$(".admin-close").addEventListener("click", () => $("#admin-modal").close());
$(".product-detail-close").addEventListener("click", () => $("#product-detail-modal").close());
$("#product-detail-content").addEventListener("click", (event) => {
  const addButton = event.target.closest("[data-detail-add]");
  const buyButton = event.target.closest("[data-detail-buy]");
  const quoteButton = event.target.closest("[data-detail-quote]");
  if (addButton) {
    addToCart(addButton.dataset.detailAdd);
    $("#product-detail-modal").close();
  } else if (buyButton) {
    if (!state.cart[buyButton.dataset.detailBuy]) addToCart(buyButton.dataset.detailBuy);
    $("#product-detail-modal").close();
    openCheckout();
  } else if (quoteButton) {
    const product = state.products.find((entry) => entry.id === quoteButton.dataset.detailQuote);
    if (product) downloadQuote(product);
  }
});
$(".checkout-open").setAttribute("aria-label", "Crear solicitud de compra simulada");
$("#download-order-record").addEventListener("click", () => {
  if (latestRegisteredOrder) downloadOrderRecord(latestRegisteredOrder);
});

$("#checkout-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = $("#checkout-submit");
  submit.disabled = true;
  try {
    const result = await apiRequest("/orders", {
      method: "POST",
      body: JSON.stringify({
        customer_name: $("#customer-name").value.trim(),
        customer_email: $("#customer-email").value.trim(),
        items: cartDetails().map((item) => ({ product_id: item.id, quantity: item.quantity }))
      })
    });
    latestRegisteredOrder = result.order;
    $("#order-download-label").textContent = `Solicitud ${result.order.payment_code} registrada. Descarga su constancia simulada.`;
    $("#order-download").hidden = false;
    state.cart = {};
    persistCart();
    refreshCart();
    $("#checkout-modal").close();
    $("#checkout-form").reset();
    showToast(`Compra ${result.order.payment_code} registrada. Descargué tu comprobante con el código.`, "success");
  } catch (error) {
    showToast(error.message || "No se pudo registrar la solicitud.", "error");
  } finally {
    submit.disabled = false;
  }
});

document.querySelectorAll(".admin-open").forEach((button) => {
  button.addEventListener("click", () => {
    $("#admin-modal").showModal();
    $("#admin-name").focus();
  });
});

$("#verify-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const result = $("#verify-result");
  const code = $("#verify-code").value.trim();
  if (!code) return;
  result.hidden = true;
  try {
    const data = await apiRequest(`/orders/verify/${encodeURIComponent(code)}`);
    result.hidden = false;
    result.className = "verify-result verify-ok";
    result.innerHTML = `<b>✓ ${escapeHtml(data.payment_code)}</b> · Orden ${escapeHtml(data.number)} · Estado: <span class="verify-status">${escapeHtml(data.status)}</span> · ${escapeHtml(data.created_at)} · Total ${money.format(data.total)}`;
  } catch (error) {
    result.hidden = false;
    result.className = "verify-result verify-fail";
    result.textContent = `✕ ${error.message}`;
  }
});

$("#admin-login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = event.currentTarget.querySelector("button[type=submit]");
  submit.disabled = true;
  try {
    const result = await apiRequest("/admin/login", {
      method: "POST",
      body: JSON.stringify({ admin: $("#admin-name").value, code: $("#admin-code").value })
    });
    state.csrfToken = result.csrf_token;
    state.adminName = result.admin_name;
    $("#admin-login-form").hidden = true;
    $("#admin-panel").hidden = false;
    $("#admin-code").value = "";
    await loadAdminOrders();
    showToast(`Sesión de revisión iniciada por ${result.admin_name}.`, "success");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    submit.disabled = false;
  }
});

async function loadAdminOrders() {
  const result = await apiRequest("/admin/orders");
  const target = $("#admin-orders");
  if (!result.orders.length) {
    target.innerHTML = '<div class="admin-empty">Todavía no hay solicitudes registradas.</div>';
    return;
  }
  target.innerHTML = result.orders.map((order) => `
    <article class="admin-order">
      <div class="admin-order-top"><b>${escapeHtml(order.number)} · ${escapeHtml(order.customer_name)}</b><span class="order-status">${escapeHtml(order.status)}</span></div>
      <p>${escapeHtml(order.items.map((item) => `${item.quantity} × ${item.product_name}`).join(", "))}<br>${money.format(order.total)} · ${escapeHtml(order.created_at)}${order.decision_note ? `<br>Motivo: ${escapeHtml(order.decision_note)}` : ""}</p>
      ${order.status === "pendiente" ? `<div class="admin-order-actions"><button type="button" data-decision="approved" data-order="${escapeHtml(order.id)}">Aprobar</button><button type="button" data-decision="rejected" data-order="${escapeHtml(order.id)}">Rechazar</button></div>` : ""}
    </article>`).join("");
  target.querySelectorAll("[data-decision]").forEach((button) => {
    button.addEventListener("click", () => decideOrder(button.dataset.order, button.dataset.decision));
  });
}

async function decideOrder(orderId, decision) {
  const label = decision === "approved" ? "aprobar" : "rechazar";
  const note = decision === "rejected"
    ? window.prompt("Escribe un motivo breve para rechazar esta solicitud:")
    : "";
  if (decision === "rejected" && (!note || note.trim().length < 3)) {
    showToast("Para rechazar, escribe un motivo de al menos 3 caracteres.", "error");
    return;
  }
  if (!window.confirm(`¿Confirmas ${label} esta solicitud de demostración?`)) return;
  try {
    await apiRequest(`/admin/orders/${encodeURIComponent(orderId)}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, note: note ? note.trim() : "" })
    });
    await loadAdminOrders();
    showToast(`Solicitud ${decision === "approved" ? "aprobada" : "rechazada"}.`, "success");
  } catch (error) {
    showToast(error.message, "error");
  }
}

$("#admin-logout").addEventListener("click", async () => {
  try {
    await apiRequest("/admin/logout", { method: "POST", body: "{}" });
    $("#admin-panel").hidden = true;
    $("#admin-login-form").hidden = false;
    showToast("Sesión cerrada.", "success");
  } catch (error) {
    showToast(error.message, "error");
  }
});

loadCatalog();
// Exponer helpers para depuración y para las pruebas automatizadas del proyecto.
window.NEXUS = { state, printableDocument, downloadQuote, downloadOrderRecord };
