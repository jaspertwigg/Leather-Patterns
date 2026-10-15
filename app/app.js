/* Leather Patterns -- a phone-only pattern catalog.
 * Everything lives in this browser's IndexedDB: pattern metadata and the
 * actual files (original, reference PDF, thumbnail) as Blobs. There is no
 * server and nothing is sent anywhere -- back up via Settings before you
 * clear browser data, switch phones, or uninstall the app.
 */

// pdf.js loads from a CDN <script> tag in index.html; if that fails (flaky
// network, an ad-blocker) `pdfjsLib` is simply absent here. Guard it so a
// missing thumbnail library degrades to "no thumbnail", not a broken app.
if (window.pdfjsLib) {
  pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
}

const DB_NAME = "leather-patterns-db";
const STORE = "patterns";

/* ---------------------------------------------------------------------
 * IndexedDB
 * ------------------------------------------------------------------- */
function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function withStore(mode, fn) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, mode);
    const store = tx.objectStore(STORE);
    let result;
    Promise.resolve(fn(store)).then(r => { result = r; }).catch(reject);
    tx.oncomplete = () => resolve(result);
    tx.onerror = () => reject(tx.error);
  });
}

function reqToPromise(req) {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

const dbGetAll = () => withStore("readonly", store => reqToPromise(store.getAll()));
const dbGet = id => withStore("readonly", store => reqToPromise(store.get(id)));
const dbAdd = record => withStore("readwrite", store => reqToPromise(store.add(record)));
const dbPut = record => withStore("readwrite", store => reqToPromise(store.put(record)));
const dbDelete = id => withStore("readwrite", store => reqToPromise(store.delete(id)));
const dbClear = () => withStore("readwrite", store => reqToPromise(store.clear()));

/* ---------------------------------------------------------------------
 * Small helpers
 * ------------------------------------------------------------------- */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove("show"), 2800);
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function cleanTitle(filename) {
  let name = (filename || "").replace(/^.*[\\/]/, "");
  name = name.replace(/\.[^.]+$/, "");
  name = name.replace(/^[0-9a-f]{6,12}-(?=[A-Za-z])/, "");
  name = name.replace(/_/g, " ");
  name = name.replace(/\s*-\s*Copy\s*$/i, "");
  return name.replace(/\s+/g, " ").trim();
}

function extOf(filename) {
  const m = /\.[^.]+$/.exec(filename || "");
  return m ? m[0].toLowerCase() : "";
}

const ALLOWED_EXTS = new Set([".lcc", ".dxf", ".svg", ".pdf", ".png", ".jpg", ".jpeg"]);
const IMAGE_EXTS = new Set([".png", ".jpg", ".jpeg"]);

function downloadBlob(blob, filename) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}

/* ---------------------------------------------------------------------
 * .lcc metadata: named layers, a rough shape count (distinct line groups
 * via "gid"), and the overall canvas size from every line's start/end
 * point. A lightweight read for cataloguing, not the full geometry engine
 * leathercraft-pdf uses -- it won't notice two shapes are mirror images
 * of the same piece, for instance.
 * ------------------------------------------------------------------- */
function parseLccSummary(text) {
  const clean = text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
  const data = JSON.parse(clean);

  const layerNames = (data.layers || [])
    .map(l => l.nam)
    .filter(nam => nam && !/^layer\s+\d+$/i.test(nam.trim()));

  const shapes = data.shapes || [];
  const gids = new Set(shapes.map(s => s.gid).filter(g => g !== undefined && g !== null));
  const shapeCount = gids.size || shapes.length;

  let xs = [], ys = [];
  for (const s of shapes) {
    for (const pt of [s.sp, s.ep]) {
      if (Array.isArray(pt) && pt.length === 2) { xs.push(pt[0]); ys.push(pt[1]); }
    }
  }
  const canvasWmm = xs.length ? Math.max(...xs) - Math.min(...xs) : null;
  const canvasHmm = ys.length ? Math.max(...ys) - Math.min(...ys) : null;

  return { layerNames, shapeCount, canvasWmm, canvasHmm };
}

async function renderPdfThumbnail(blob) {
  if (!window.pdfjsLib) throw new Error("pdf.js did not load");
  const buf = await blob.arrayBuffer();
  const pdf = await pdfjsLib.getDocument({ data: buf }).promise;
  const page = await pdf.getPage(1);
  const viewport = page.getViewport({ scale: 1.0 });
  const scale = 480 / viewport.width;
  const scaledViewport = page.getViewport({ scale });
  const canvas = document.createElement("canvas");
  canvas.width = scaledViewport.width;
  canvas.height = scaledViewport.height;
  await page.render({ canvasContext: canvas.getContext("2d"), viewport: scaledViewport }).promise;
  return new Promise(resolve => canvas.toBlob(resolve, "image/png"));
}

/* ---------------------------------------------------------------------
 * Router
 * ------------------------------------------------------------------- */
function parseHash() {
  const h = location.hash.replace(/^#\/?/, "");
  const parts = h.split("/").filter(Boolean);
  if (parts.length === 0) return { screen: "library" };
  if (parts[0] === "new") return { screen: "new" };
  if (parts[0] === "settings") return { screen: "settings" };
  if (parts[0] === "p" && parts[1]) return { screen: "detail", id: Number(parts[1]), edit: parts[2] === "edit" };
  return { screen: "library" };
}

function navigate(hash) { location.hash = hash; }

window.addEventListener("hashchange", render);
window.addEventListener("DOMContentLoaded", () => {
  render();
  $("#fab-add").addEventListener("click", () => navigate(parseHash().screen === "library" ? "#/new" : "#/"));
  $("#btn-nav-home").addEventListener("click", () => navigate("#/"));
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
});

/* ---------------------------------------------------------------------
 * Render: top-level
 * ------------------------------------------------------------------- */
let patternsCache = [];

async function loadPatterns() {
  patternsCache = (await dbGetAll()).sort((a, b) => (b.createdAt || "").localeCompare(a.createdAt || ""));
}

async function render() {
  const app = $("#app");
  const route = parseHash();
  $("#btn-nav-home").hidden = route.screen === "library";
  $("#fab-add").hidden = route.screen === "new";
  $("#fab-add").innerHTML = route.screen === "library" ? "+" : "&times;";
  $("#fab-add").title = route.screen === "library" ? "Add pattern" : "Close";

  if (route.screen === "library") { await loadPatterns(); renderLibrary(); return; }
  if (route.screen === "new") { renderForm(null); return; }
  if (route.screen === "settings") { renderSettings(); return; }
  if (route.screen === "detail") { await renderDetail(route.id, route.edit); return; }
  app.innerHTML = "";
}

/* ---------------------------------------------------------------------
 * Library screen
 * ------------------------------------------------------------------- */
let libraryFilter = { q: "", category: "", tag: "" };

function renderLibrary() {
  const app = $("#app");

  const categories = [...new Set(patternsCache.map(p => p.category).filter(Boolean))].sort();
  const allTags = [...new Set(patternsCache.flatMap(p => p.tags || []))].sort();

  const q = libraryFilter.q.trim().toLowerCase();
  const filtered = patternsCache.filter(p => {
    if (q && !((p.name || "").toLowerCase().includes(q) || (p.notes || "").toLowerCase().includes(q))) return false;
    if (libraryFilter.category && p.category !== libraryFilter.category) return false;
    if (libraryFilter.tag && !(p.tags || []).includes(libraryFilter.tag)) return false;
    return true;
  });

  app.innerHTML = `
    <div class="toolbar">
      <input type="search" id="f-q" placeholder="Search name or notes…" value="${esc(libraryFilter.q)}">
      <select id="f-cat">
        <option value="">All categories</option>
        ${categories.map(c => `<option value="${esc(c)}" ${c === libraryFilter.category ? "selected" : ""}>${esc(c)}</option>`).join("")}
      </select>
      <select id="f-tag">
        <option value="">All tags</option>
        ${allTags.map(t => `<option value="${esc(t)}" ${t === libraryFilter.tag ? "selected" : ""}>${esc(t)}</option>`).join("")}
      </select>
      <button class="btn btn-ghost" id="btn-settings" title="Settings">⚙️</button>
    </div>
    ${filtered.length === 0 ? renderEmpty() : `<div class="grid">${filtered.map(cardHtml).join("")}</div>`}
  `;

  $("#f-q").addEventListener("input", e => { libraryFilter.q = e.target.value; renderLibrary(); });
  $("#f-cat").addEventListener("change", e => { libraryFilter.category = e.target.value; renderLibrary(); });
  $("#f-tag").addEventListener("change", e => { libraryFilter.tag = e.target.value; renderLibrary(); });
  $("#btn-settings").addEventListener("click", () => navigate("#/settings"));
  $$(".card").forEach(c => c.addEventListener("click", () => navigate("#/p/" + c.dataset.id)));
}

function renderEmpty() {
  const hasAny = patternsCache.length > 0;
  return `<div class="empty">
    <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M4 4h11l5 5v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z"/><path d="M15 4v5h5"/></svg>
    <p>${hasAny ? "No patterns match that filter." : "No patterns yet. Tap + to add your first one."}</p>
  </div>`;
}

function cardHtml(p) {
  const thumbBlob = p.thumbnailBlob || (IMAGE_EXTS.has(p.originalExt) ? p.originalBlob : null);
  const thumb = thumbBlob
    ? `<img src="${objectUrlFor(p.id, thumbBlob)}" alt="">`
    : `<span class="ext-badge">${esc((p.originalExt || "").replace(".", "").toUpperCase())}</span>`;
  const meta = [];
  if (p.shapeCount) meta.push(`${p.shapeCount} piece${p.shapeCount === 1 ? "" : "s"}`);
  if (p.canvasWmm && p.canvasHmm) meta.push(`${Math.round(p.canvasWmm)}×${Math.round(p.canvasHmm)}mm`);
  return `
    <div class="card" data-id="${p.id}" role="button" tabindex="0">
      <div class="thumb">${thumb}</div>
      <div class="body">
        <h3>${esc(p.name)}</h3>
        ${p.category ? `<span class="pill">${esc(p.category)}</span>` : ""}
        ${meta.length ? `<div class="mono" style="font-size:.76rem;color:var(--muted)">${meta.join(" · ")}</div>` : ""}
        ${(p.tags || []).length ? `<div class="tags">${p.tags.map(t => `<span class="tag">${esc(t)}</span>`).join("")}</div>` : ""}
      </div>
    </div>`;
}

// Object URLs are cheap but must be revoked eventually; cache one per
// (pattern, blob) pair for the life of the page rather than leaking a
// fresh URL on every re-render.
const _objectUrls = new Map();
function objectUrlFor(id, blob) {
  const key = id + ":" + (blob.size || 0);
  if (!_objectUrls.has(key)) _objectUrls.set(key, URL.createObjectURL(blob));
  return _objectUrls.get(key);
}

/* ---------------------------------------------------------------------
 * Upload / edit form screen
 * ------------------------------------------------------------------- */
function renderForm(existing) {
  const app = $("#app");
  const isEdit = !!existing;
  app.innerHTML = `
    <h2>${isEdit ? "Edit pattern" : "Add a pattern"}</h2>
    <form id="pattern-form">
      ${isEdit ? "" : `
      <div class="field">
        <label>Pattern file <span class="hint">.lcc, .dxf, .svg, .pdf, or a photo</span></label>
        <div class="file-input"><input type="file" id="f-file" required></div>
        <div class="file-name" id="f-file-name"></div>
      </div>
      <div class="field" id="pdf-field" hidden>
        <label>Reference PDF <span class="hint">optional — a print-ready cut sheet, if separate</span></label>
        <div class="file-input"><input type="file" id="f-pdf" accept=".pdf"></div>
      </div>`}
      <div class="field">
        <label>Name</label>
        <input type="text" id="f-name" placeholder="e.g. Classic Trifold Wallet" value="${esc(existing?.name || "")}">
        ${isEdit ? "" : `<span class="hint">leave blank to use the filename</span>`}
      </div>
      <div class="field">
        <label>Category <span class="hint">e.g. Wallet, Bag, Case</span></label>
        <input type="text" id="f-category" value="${esc(existing?.category || "")}">
      </div>
      <div class="field">
        <label>Tags <span class="hint">comma-separated</span></label>
        <input type="text" id="f-tags" value="${esc((existing?.tags || []).join(', '))}" placeholder="bifold, veg-tan, gift">
      </div>
      <div class="field">
        <label>Notes</label>
        <textarea id="f-notes" rows="4" placeholder="Leather weight, stitch length, anything worth remembering…">${esc(existing?.notes || "")}</textarea>
      </div>
      <div class="action-row">
        <button type="submit" class="btn-accent" id="f-submit">${isEdit ? "Save changes" : "Save pattern"}</button>
        <button type="button" class="btn-ghost" id="f-cancel">Cancel</button>
      </div>
    </form>
  `;

  $("#f-cancel").addEventListener("click", () => history.back());

  if (!isEdit) {
    $("#f-file").addEventListener("change", e => {
      const f = e.target.files[0];
      $("#f-file-name").textContent = f ? f.name : "";
      const ext = extOf(f?.name);
      $("#pdf-field").hidden = ext === ".pdf" || IMAGE_EXTS.has(ext);
      if (!$("#f-name").value) $("#f-name").value = cleanTitle(f?.name || "");
    });
  }

  $("#pattern-form").addEventListener("submit", async e => {
    e.preventDefault();
    const btn = $("#f-submit");
    btn.disabled = true;
    const originalLabel = btn.innerHTML;
    btn.innerHTML = `<span class="spinner"></span> Saving…`;
    try {
      if (isEdit) await submitEdit(existing);
      else await submitNew();
    } catch (err) {
      console.error(err);
      toast(err.message || "Something went wrong saving that.");
      btn.disabled = false;
      btn.innerHTML = originalLabel;
    }
  });
}

function tagsFromInput(raw) {
  const seen = new Set();
  const out = [];
  for (const t of raw.split(",").map(s => s.trim()).filter(Boolean)) {
    const k = t.toLowerCase();
    if (!seen.has(k)) { seen.add(k); out.push(t); }
  }
  return out;
}

async function submitEdit(existing) {
  existing.name = $("#f-name").value.trim() || "Untitled pattern";
  existing.category = $("#f-category").value.trim();
  existing.tags = tagsFromInput($("#f-tags").value);
  existing.notes = $("#f-notes").value.trim();
  existing.updatedAt = new Date().toISOString();
  await dbPut(existing);
  toast("Saved.");
  navigate("#/p/" + existing.id);
}

async function submitNew() {
  const file = $("#f-file").files[0];
  if (!file) throw new Error("Choose a pattern file first.");
  const ext = extOf(file.name);
  if (!ALLOWED_EXTS.has(ext)) throw new Error(`Unsupported file type "${ext}". Try .lcc, .dxf, .svg, .pdf, or a photo.`);

  let layerNames = [], shapeCount = null, canvasWmm = null, canvasHmm = null;
  if (ext === ".lcc") {
    try {
      const summary = parseLccSummary(await file.text());
      ({ layerNames, shapeCount, canvasWmm, canvasHmm } = summary);
    } catch (e) {
      console.warn("could not parse .lcc metadata", e);
    }
  }

  const pdfFile = $("#f-pdf")?.files?.[0];
  let pdfBlob = null;
  if (ext === ".pdf") pdfBlob = file;
  else if (pdfFile) pdfBlob = pdfFile;

  let thumbnailBlob = null;
  if (pdfBlob && !IMAGE_EXTS.has(ext)) {
    thumbnailBlob = await renderPdfThumbnail(pdfBlob).catch(e => { console.warn("thumbnail failed", e); return null; });
  }

  const name = $("#f-name").value.trim() || cleanTitle(file.name);
  const now = new Date().toISOString();
  const id = await dbAdd({
    name,
    category: $("#f-category").value.trim(),
    tags: tagsFromInput($("#f-tags").value),
    notes: $("#f-notes").value.trim(),
    originalFilename: file.name,
    originalExt: ext,
    originalBlob: file,
    pdfBlob: ext === ".pdf" ? null : pdfBlob, // the original already *is* the pdf in that case
    thumbnailBlob,
    layerNames, shapeCount, canvasWmm, canvasHmm,
    createdAt: now, updatedAt: now,
  });
  toast("Pattern saved.");
  navigate("#/p/" + id);
}

/* ---------------------------------------------------------------------
 * Detail screen
 * ------------------------------------------------------------------- */
async function renderDetail(id, editing) {
  const app = $("#app");
  let p = patternsCache.find(x => x.id === id) || await dbGet(id);
  if (!p) { app.innerHTML = `<div class="empty">That pattern isn't here anymore.</div>`; return; }
  if (editing) { renderForm(p); return; }

  const thumbBlob = p.thumbnailBlob || (IMAGE_EXTS.has(p.originalExt) ? p.originalBlob : null);
  const thumb = thumbBlob
    ? `<img src="${objectUrlFor(p.id, thumbBlob)}" alt="">`
    : `<div class="ext-badge" style="font-size:2rem;padding:50px 0">${esc((p.originalExt || "").replace(".", "").toUpperCase())}</div>`;

  const hasPdf = p.originalExt === ".pdf" || !!p.pdfBlob;

  app.innerHTML = `
    <div class="detail-head">
      <div class="detail-thumb">${thumb}</div>
      <h2 style="margin:0">${esc(p.name)}</h2>
      ${p.category ? `<span class="pill">${esc(p.category)}</span>` : ""}
    </div>

    <div class="meta-row"><span class="k">File</span><span>${esc(p.originalFilename)}</span></div>
    ${p.shapeCount ? `<div class="meta-row"><span class="k">Shapes</span><span>~${p.shapeCount}</span></div>` : ""}
    ${p.canvasWmm && p.canvasHmm ? `<div class="meta-row"><span class="k">Canvas</span><span class="mono">${Math.round(p.canvasWmm)} × ${Math.round(p.canvasHmm)} mm</span></div>` : ""}
    <div class="meta-row"><span class="k">Added</span><span>${esc((p.createdAt || "").slice(0, 10))}</span></div>

    ${(p.layerNames || []).length ? `
      <div style="margin-top:10px">
        <div class="k" style="font-size:.88rem">Named layers</div>
        <div class="layer-list">${p.layerNames.map(l => `<span class="tag">${esc(l)}</span>`).join("")}</div>
      </div>` : ""}

    ${(p.tags || []).length ? `<div class="tags" style="margin-top:12px">${p.tags.map(t => `<span class="tag">${esc(t)}</span>`).join("")}</div>` : ""}

    ${p.notes ? `<div class="notes-box" style="margin-top:14px">${esc(p.notes)}</div>` : ""}

    <div class="action-row">
      <button class="btn btn-ghost" id="btn-save-original">Save original (${esc(p.originalExt)})</button>
      ${hasPdf && p.originalExt !== ".pdf" ? `<button class="btn btn-ghost" id="btn-save-pdf">Save PDF</button>` : ""}
      <button class="btn btn-ghost" id="btn-edit">Edit details</button>
    </div>

    <div class="danger-zone">
      <button class="btn btn-danger" id="btn-delete">Delete this pattern</button>
    </div>
  `;

  $("#btn-edit").addEventListener("click", () => navigate(`#/p/${p.id}/edit`));
  $("#btn-delete").addEventListener("click", () => deletePattern(p));
  $("#btn-save-original").addEventListener("click", () => downloadBlob(p.originalBlob, p.originalFilename));
  if (hasPdf && p.originalExt !== ".pdf") {
    $("#btn-save-pdf").addEventListener("click", () => downloadBlob(p.pdfBlob, `${p.name}.pdf`));
  }
}

async function deletePattern(p) {
  if (!confirm(`Delete "${p.name}"? This removes it and its files for good.`)) return;
  await dbDelete(p.id);
  toast("Deleted.");
  navigate("#/");
}

/* ---------------------------------------------------------------------
 * Settings screen: backup / restore, since everything lives only in this
 * browser -- losing the phone, clearing site data, or switching browsers
 * loses the library unless you've exported one of these first.
 * ------------------------------------------------------------------- */
function renderSettings() {
  const app = $("#app");
  app.innerHTML = `
    <h2>Settings</h2>
    <div class="settings-row">
      <p>Your patterns live only in this browser. Export a backup before you clear site data, switch phones, or uninstall the app — and periodically besides, just in case.</p>
      <button class="btn btn-accent" id="btn-export">⬇️ Export backup</button>
      <label class="btn btn-ghost" style="justify-content:center">⬆️ Import backup<input type="file" accept="application/json,.json" id="btn-import" hidden></label>
    </div>
    <div class="danger-zone">
      <button class="btn btn-danger" id="btn-wipe">Delete all patterns</button>
    </div>
  `;
  $("#btn-export").addEventListener("click", exportBackup);
  $("#btn-import").addEventListener("change", e => { if (e.target.files[0]) importBackup(e.target.files[0]); });
  $("#btn-wipe").addEventListener("click", async () => {
    if (!confirm("Delete ALL patterns? This can't be undone.")) return;
    await dbClear();
    toast("Library cleared.");
    navigate("#/");
  });
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(",")[1]);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

function base64ToBlob(b64, type) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Blob([bytes], { type });
}

async function exportBackup() {
  const btn = $("#btn-export");
  btn.disabled = true;
  const label = btn.innerHTML;
  btn.innerHTML = `<span class="spinner"></span> Preparing…`;
  try {
    const patterns = await dbGetAll();
    const packed = await Promise.all(patterns.map(async p => ({
      ...p,
      originalBlob: undefined,
      pdfBlob: undefined,
      thumbnailBlob: undefined,
      originalData: await blobToBase64(p.originalBlob),
      originalType: p.originalBlob.type,
      pdfData: p.pdfBlob ? await blobToBase64(p.pdfBlob) : null,
      pdfType: p.pdfBlob ? p.pdfBlob.type : null,
      thumbnailData: p.thumbnailBlob ? await blobToBase64(p.thumbnailBlob) : null,
      thumbnailType: p.thumbnailBlob ? p.thumbnailBlob.type : null,
    })));
    const blob = new Blob([JSON.stringify({ version: 1, exportedAt: new Date().toISOString(), patterns: packed })], { type: "application/json" });
    downloadBlob(blob, `leather-patterns-backup-${new Date().toISOString().slice(0, 10)}.json`);
    toast("Backup downloaded.");
  } catch (e) {
    console.error(e);
    toast("Could not build that backup.");
  } finally {
    btn.disabled = false;
    btn.innerHTML = label;
  }
}

async function importBackup(file) {
  try {
    const data = JSON.parse(await file.text());
    if (!Array.isArray(data.patterns)) throw new Error("not a backup file");
    let count = 0;
    for (const p of data.patterns) {
      const record = {
        ...p,
        originalBlob: base64ToBlob(p.originalData, p.originalType),
        pdfBlob: p.pdfData ? base64ToBlob(p.pdfData, p.pdfType) : null,
        thumbnailBlob: p.thumbnailData ? base64ToBlob(p.thumbnailData, p.thumbnailType) : null,
      };
      delete record.originalData; delete record.originalType;
      delete record.pdfData; delete record.pdfType;
      delete record.thumbnailData; delete record.thumbnailType;
      delete record.id; // let it mint a fresh id rather than collide
      await dbAdd(record);
      count++;
    }
    toast(`Restored ${count} pattern${count === 1 ? "" : "s"}.`);
    navigate("#/");
  } catch (e) {
    console.error(e);
    toast("That doesn't look like a Leather Patterns backup.");
  }
}
