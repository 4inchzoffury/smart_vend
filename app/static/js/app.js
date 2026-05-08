// Close the task modal after HTMX swaps the task board
document.addEventListener("htmx:afterSwap", function (evt) {
  if (evt.detail.target && evt.detail.target.id === "task-board") {
    const modal = document.getElementById("taskModal");
    if (modal) {
      const bsModal = bootstrap.Modal.getInstance(modal);
      if (bsModal) bsModal.hide();
    }
  }
});
