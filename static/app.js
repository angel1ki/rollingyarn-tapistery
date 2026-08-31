const gridW = document.getElementById("gridW");
const gridWVal = document.getElementById("gridWVal");
const numColors = document.getElementById("numColors");
const numColorsVal = document.getElementById("numColorsVal");
const form = document.getElementById("uploadForm");
const loading = document.getElementById("loading");
const errorBox = document.getElementById("errorBox");
const results = document.getElementById("results");
const generateBtn = document.getElementById("generateBtn");
const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

gridW.addEventListener("input", () => { gridWVal.textContent = gridW.value; });
numColors.addEventListener("input", () => { numColorsVal.textContent = numColors.value; });

function showError(message) {
  errorBox.textContent = "⚠️ " + message;
  errorBox.classList.remove("hidden");
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorBox.classList.add("hidden");
  results.classList.add("hidden");

  const photoInput = document.getElementById("photo");
  if (!photoInput.files.length) {
    showError("Παρακαλώ επιλέξτε πρώτα μια φωτογραφία.");
    return;
  }

  const formData = new FormData();
  formData.append("photo", photoInput.files[0]);
  formData.append("grid_w", gridW.value);
  formData.append("num_colors", numColors.value);
  formData.append("show_symbols", document.getElementById("showSymbols").checked ? "true" : "false");

  loading.classList.remove("hidden");
  generateBtn.disabled = true;

  try {
    const response = await fetch("/process", {
      method: "POST",
      headers: { "X-CSRFToken": csrfToken },
      body: formData,
    });
    const data = await response.json();

    if (!response.ok) {
      showError(data.error || "Κάτι πήγε στραβά. Δοκιμάστε ξανά.");
      return;
    }

    renderResults(data);
  } catch (err) {
    showError("Δεν ήταν δυνατή η σύνδεση με τον διακομιστή.");
  } finally {
    loading.classList.add("hidden");
    generateBtn.disabled = false;
  }
});

let lastResult = null;

function renderResults(data) {
  lastResult = data;
  document.getElementById("saveMsg").textContent = "";

  const previewSrc = "data:image/png;base64," + data.preview_image;
  const patternSrc = "data:image/png;base64," + data.pattern_image;

  const previewImg = document.getElementById("previewImg");
  const patternImg = document.getElementById("patternImg");
  previewImg.src = previewSrc;
  patternImg.src = patternSrc;

  document.getElementById("downloadPreview").href = previewSrc;
  document.getElementById("downloadPattern").href = patternSrc;
  document.getElementById("dimText").textContent = data.grid_w + " x " + data.grid_h;
  document.getElementById("symbolsDisabledNote").classList.toggle("hidden", !data.symbols_disabled);

  const printImg = document.getElementById("printPatternImg");
  printImg.src = patternSrc;

  fillLegendTable(document.getElementById("legendTable").querySelector("tbody"), data.legend, true);
  fillLegendTable(document.getElementById("printLegendTable"), data.legend, false, true);

  results.classList.remove("hidden");
  results.scrollIntoView({ behavior: "smooth" });
}

function fillLegendTable(target, legend, isTbody, withHeader) {
  target.innerHTML = "";
  if (withHeader) {
    const headRow = document.createElement("tr");
    ["Αρ.", "Χρώμα", "Κωδικός", "Πλήθος θηλιών"].forEach((text) => {
      const th = document.createElement("th");
      th.textContent = text;
      headRow.appendChild(th);
    });
    target.appendChild(headRow);
  }
  legend.forEach((item) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${item.symbol}</td>
      <td><span class="swatch" style="background:${item.hex}"></span></td>
      <td>${item.hex}</td>
      <td>${item.count}</td>
    `;
    target.appendChild(row);
  });
}

document.getElementById("printBtn").addEventListener("click", () => {
  window.print();
});

document.getElementById("saveBtn").addEventListener("click", async () => {
  if (!lastResult) return;

  const saveMsg = document.getElementById("saveMsg");
  const title = document.getElementById("artTitle").value.trim() || "Χωρίς τίτλο";
  saveMsg.textContent = "⏳ Αποθήκευση...";

  try {
    const response = await fetch("/save", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
      body: JSON.stringify({
        title,
        preview_image: lastResult.preview_image,
        pattern_image: lastResult.pattern_image,
        legend: lastResult.legend,
        grid_w: lastResult.grid_w,
        grid_h: lastResult.grid_h,
      }),
    });
    const data = await response.json();

    if (!response.ok) {
      saveMsg.textContent = "⚠️ " + (data.error || "Αποτυχία αποθήκευσης.");
      return;
    }
    saveMsg.innerHTML = "✅ Αποθηκεύτηκε! Δείτε το στα <a href=\"/profile\">Έργα μου</a>.";
  } catch (err) {
    saveMsg.textContent = "⚠️ Δεν ήταν δυνατή η σύνδεση με τον διακομιστή.";
  }
});
