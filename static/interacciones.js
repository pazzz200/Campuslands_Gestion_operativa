/* Interacciones de la interfaz (responsable: David López).
   Se ejecuta dentro de un iframe de componente; trabaja sobre la página
   principal mediante window.parent. Se instala una sola vez aunque
   Streamlit vuelva a ejecutar el script en cada interacción. */
(function () {
  const win = window.parent;
  const doc = win.document;
  if (win.__campusUI) return;
  win.__campusUI = true;

  const reducirMovimiento = win.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // 1) Contadores animados en las métricas: anima cuando el número cambia.
  function animarMetrica(el) {
    const texto = el.textContent.trim();
    if (el.dataset.cgFinal === texto) return;
    el.dataset.cgFinal = texto;
    const m = texto.match(/^(\d+)(.*)$/); // "12" o "8/20"
    if (!m || reducirMovimiento) return;
    const destino = parseInt(m[1], 10), resto = m[2];
    const duracion = 700, t0 = performance.now();
    function paso(t) {
      const p = Math.min((t - t0) / duracion, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(destino * eased) + resto;
      if (p < 1) win.requestAnimationFrame(paso);
      else el.textContent = texto;
    }
    win.requestAnimationFrame(paso);
  }

  // 2) Reloj y saludo en el menú lateral.
  function reloj() {
    const caja = doc.getElementById("cg-reloj");
    if (!caja) return;
    const ahora = new Date();
    const h = ahora.getHours();
    const saludo = h < 12 ? "Buenos días" : h < 19 ? "Buenas tardes" : "Buenas noches";
    const hora = ahora.toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" });
    const fecha = ahora.toLocaleDateString("es-CO", { weekday: "long", day: "numeric", month: "long" });
    caja.innerHTML = `${saludo} 👋<b>${hora}</b>${fecha}`;
  }

  // 3) Efecto "ripple" al pulsar botones.
  doc.addEventListener("click", function (ev) {
    const btn = ev.target.closest(".stButton > button, .stFormSubmitButton > button");
    if (!btn || reducirMovimiento) return;
    const r = btn.getBoundingClientRect();
    const size = Math.max(r.width, r.height);
    const onda = doc.createElement("span");
    onda.className = "cg-ripple";
    onda.style.width = onda.style.height = size + "px";
    onda.style.left = ev.clientX - r.left - size / 2 + "px";
    onda.style.top = ev.clientY - r.top - size / 2 + "px";
    btn.appendChild(onda);
    setTimeout(() => onda.remove(), 650);
  }, true);

  // Streamlit redibuja el DOM a menudo: observar y reaplicar.
  function refrescar() {
    doc.querySelectorAll('[data-testid="stMetricValue"] > div').forEach(animarMetrica);
    reloj();
  }
  let pendiente = false;
  new win.MutationObserver(function () {
    if (pendiente) return;
    pendiente = true;
    win.requestAnimationFrame(() => { pendiente = false; refrescar(); });
  }).observe(doc.body, { childList: true, subtree: true, characterData: true });

  setInterval(reloj, 15000);
  refrescar();
})();
