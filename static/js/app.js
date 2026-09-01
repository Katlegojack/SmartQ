const toast = document.querySelector("[data-toast]");
const demoActions = document.querySelectorAll("[data-demo-action]");

function showToast(message) {
    if (!toast) return;

    toast.textContent = message;
    toast.hidden = false;

    window.clearTimeout(showToast.timeoutId);
    showToast.timeoutId = window.setTimeout(() => {
        toast.hidden = true;
    }, 3200);
}

for (const control of demoActions) {
    control.addEventListener("click", () => {
        showToast("Authentication screens are scheduled for Day 42.");
    });
}
