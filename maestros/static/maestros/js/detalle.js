(() => {
  "use strict";

  document.querySelectorAll("[data-work-carousel]").forEach((carousel) => {
    const slides = Array.from(carousel.querySelectorAll("[data-work-slide]"));
    const previous = carousel.querySelector("[data-work-previous]");
    const next = carousel.querySelector("[data-work-next]");
    const current = carousel.querySelector("[data-work-current]");
    if (slides.length < 2 || !previous || !next) return;

    let activeIndex = 0;
    let touchStartX = null;

    const showSlide = (newIndex) => {
      activeIndex = (newIndex + slides.length) % slides.length;
      slides.forEach((slide, index) => {
        const isActive = index === activeIndex;
        slide.classList.toggle("is-active", isActive);
        slide.setAttribute("aria-hidden", String(!isActive));
      });
      if (current) current.textContent = String(activeIndex + 1);
    };

    previous.addEventListener("click", () => showSlide(activeIndex - 1));
    next.addEventListener("click", () => showSlide(activeIndex + 1));
    carousel.addEventListener("keydown", (event) => {
      if (event.key === "ArrowLeft") showSlide(activeIndex - 1);
      if (event.key === "ArrowRight") showSlide(activeIndex + 1);
    });
    carousel.addEventListener("touchstart", (event) => {
      touchStartX = event.changedTouches[0]?.clientX ?? null;
    }, {passive: true});
    carousel.addEventListener("touchend", (event) => {
      if (touchStartX === null) return;
      const distance = (event.changedTouches[0]?.clientX ?? touchStartX) - touchStartX;
      if (Math.abs(distance) > 45) showSlide(activeIndex + (distance < 0 ? 1 : -1));
      touchStartX = null;
    }, {passive: true});
  });
})();
