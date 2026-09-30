const navTrigger = document.querySelector(".nav-trigger");
const menu = document.querySelector("#mega-menu");
const menuToggle = document.querySelector(".menu-toggle");
const nav = document.querySelector("#main-nav");

if (navTrigger && menu) {
  navTrigger.addEventListener("click", () => {
    const open = navTrigger.getAttribute("aria-expanded") === "true";
    navTrigger.setAttribute("aria-expanded", String(!open));
    menu.hidden = open;
  });
}

if (menuToggle && nav) {
  menuToggle.addEventListener("click", () => {
    const open = menuToggle.getAttribute("aria-expanded") === "true";
    menuToggle.setAttribute("aria-expanded", String(!open));
    nav.classList.toggle("open", !open);
  });
}

document.addEventListener("click", (event) => {
  if (navTrigger && menu && !event.target.closest(".navbar") && !event.target.closest(".site-header")) {
    navTrigger.setAttribute("aria-expanded", "false");
    menu.hidden = true;
  }
});

const yearEl = document.querySelector("#year");
if (yearEl) {
  yearEl.textContent = new Date().getFullYear();
}

