const gridW = document.getElementById("gridWPixelated");
const gridWVal = document.getElementById("gridWPixelatedVal");
const numColors = document.getElementById("numColorsPixelated");
const numColorsVal = document.getElementById("numColorsPixelatedVal");
const form = document.getElementById("uploadFormPixelated");
const loading = document.getElementById("loadingPixelated");
const errorBox = document.getElementById("errorBoxPixelated");
const results = document.getElementById("resultsPixelated");
const generateBtn = document.getElementById("generateBtnPixelated");
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

  const photoInput = document.getElementById("photoPixelated");
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
    const response = await fetch("/process_pixelated", {
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
  document.getElementById("saveMsgPixelated").textContent = "";

  const previewSrc = "data:image/png;base64," + data.preview_image;
  const patternSrc = "data:image/png;base64," + data.pattern_image;

  document.getElementById("previewImgPixelated").src = previewSrc;
  document.getElementById("patternImgPixelated").src = patternSrc;

  document.getElementById("downloadPreviewPixelated").href = previewSrc;
  document.getElementById("downloadPatternPixelated").href = patternSrc;
  document.getElementById("dimTextPixelated").textContent = data.grid_w + " x " + data.grid_h;
  document.getElementById("symbolsDisabledNotePixelated").classList.toggle("hidden", !data.symbols_disabled);

  document.getElementById("printPatternImgPixelated").src = patternSrc;

  fillLegendTable(document.getElementById("legendTablePixelated").querySelector("tbody"), data.legend, true);
  fillLegendTable(document.getElementById("printLegendTablePixelated"), data.legend, false, true);

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

document.getElementById("printBtnPixelated").addEventListener("click", () => {
  window.print();
});

document.getElementById("saveBtnPixelated").addEventListener("click", async () => {
  if (!lastResult) return;

  const saveMsg = document.getElementById("saveMsgPixelated");
  const title = document.getElementById("artTitlePixelated").value.trim() || "Χωρίς τίτλο";
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
