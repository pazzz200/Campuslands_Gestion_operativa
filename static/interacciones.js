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

  // 4) Fondo de estrellitas: canvas fijo detrás del contenido.
  const cielo = { canvas: null, ctx: null, estrellas: [], fugaz: null, proximaFugaz: 0, w: 0, h: 0 };

  function crearEstrellas() {
    const cantidad = Math.round((cielo.w * cielo.h) / 9000);
    cielo.estrellas = Array.from({ length: cantidad }, () => ({
      x: Math.random() * cielo.w,
      y: Math.random() * cielo.h,
      r: 0.4 + Math.random() * 1.1,
      fase: Math.random() * Math.PI * 2,
      vel: 0.6 + Math.random() * 1.4,          // velocidad del titileo
      sube: 0.02 + Math.random() * 0.06,       // deriva hacia arriba (px/frame)
      celeste: Math.random() < 0.3,
    }));
  }

  function ajustarCielo() {
    const dpr = win.devicePixelRatio || 1;
    cielo.w = win.innerWidth;
    cielo.h = win.innerHeight;
    cielo.canvas.width = cielo.w * dpr;
    cielo.canvas.height = cielo.h * dpr;
    cielo.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    crearEstrellas();
    if (reducirMovimiento) dibujarCielo(0);
  }

  function lanzarFugaz(t) {
    cielo.fugaz = {
      x: cielo.w * (0.2 + Math.random() * 0.7), y: cielo.h * Math.random() * 0.4,
      vx: -(5 + Math.random() * 3), vy: 2 + Math.random() * 1.5, vida: 1,
    };
    cielo.proximaFugaz = t + 7000 + Math.random() * 9000;
  }

  function dibujarCielo(t) {
    const { ctx, w, h } = cielo;
    ctx.clearRect(0, 0, w, h);
    for (const e of cielo.estrellas) {
      if (!reducirMovimiento) {
        e.y -= e.sube;
        if (e.y < -2) { e.y = h + 2; e.x = Math.random() * w; }
      }
      const brillo = 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(t / 1000 * e.vel + e.fase));
      ctx.globalAlpha = brillo;
      ctx.fillStyle = e.celeste ? "#8ce4ff" : "#ffffff";
      ctx.beginPath();
      ctx.arc(e.x, e.y, e.r, 0, Math.PI * 2);
      ctx.fill();
    }
    const f = cielo.fugaz;
    if (f) {
      const grad = ctx.createLinearGradient(f.x, f.y, f.x - f.vx * 14, f.y - f.vy * 14);
      grad.addColorStop(0, "rgba(255,255,255,1)");
      grad.addColorStop(1, "rgba(140,228,255,0)");
      ctx.globalAlpha = f.vida;
      ctx.strokeStyle = grad;
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.moveTo(f.x, f.y);
      ctx.lineTo(f.x - f.vx * 14, f.y - f.vy * 14);
      ctx.stroke();
      f.x += f.vx; f.y += f.vy; f.vida -= 0.015;
      if (f.vida <= 0 || f.x < -50 || f.y > h + 50) cielo.fugaz = null;
    }
    ctx.globalAlpha = 1;
  }

  function animarCielo(t) {
    if (!cielo.fugaz && t > cielo.proximaFugaz) lanzarFugaz(t);
    dibujarCielo(t);
    win.requestAnimationFrame(animarCielo);
  }

  function montarCielo() {
    const app = doc.querySelector(".stApp");
    if (!app || doc.getElementById("cg-cielo")) return;
    cielo.canvas = doc.createElement("canvas");
    cielo.canvas.id = "cg-cielo";
    cielo.canvas.setAttribute("aria-hidden", "true");
    app.prepend(cielo.canvas);
    cielo.ctx = cielo.canvas.getContext("2d");
    ajustarCielo();
    if (!cielo.iniciado) {
      cielo.iniciado = true;
      cielo.proximaFugaz = performance.now() + 4000;
      win.addEventListener("resize", ajustarCielo);
      if (!reducirMovimiento) win.requestAnimationFrame(animarCielo);
    }
  }

  // Streamlit redibuja el DOM a menudo: observar y reaplicar.
  function refrescar() {
    doc.querySelectorAll('[data-testid="stMetricValue"] > div').forEach(animarMetrica);
    reloj();
    montarCielo();
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
