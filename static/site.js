document.addEventListener("click", (e) => {
  if (e.target.closest("[data-action='print']")) {
    window.print();
  }
});

document.addEventListener("submit", (e) => {
  const message = e.target.dataset.confirm;
  if (message && !confirm(message)) {
    e.preventDefault();
  }
});
