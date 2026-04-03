(function () {
  const HOME = "/";
  const NO_FRAME_TIMEOUT_MS = 2500;

  let lastFrameAt = performance.now();
  let started = false;

  const _raf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = (cb) =>
    _raf((t) => {
      started = true;
      lastFrameAt = t;
      cb(t);
    });

  window.addEventListener("error", () => setTimeout(() => location.replace(HOME), 50));
  window.addEventListener("unhandledrejection", (e) => {
    try { e.preventDefault?.(); } catch (_) {}
    setTimeout(() => location.replace(HOME), 50);
  });

  setInterval(() => {
    if (!started) return;
    if (document.hidden) return;
    if (performance.now() - lastFrameAt > NO_FRAME_TIMEOUT_MS) {
      location.replace(HOME);
    }
  }, 500);
})();