// 3D для рилса «ЛИЦО» (Three.js, детерминированно от времени HyperFrames: hf-seek).
// Конфиг — window.LICO = { glyphs: {key: {d, w}}, mesh: {pts, tess, oval}, scenes: [{canvas, t0, t1, mode, ...}] }
// Масштаб: плоскость z=0 = кадр 1080×1920, 1 единица = 100 px; px(x, y) — точка кадра в мире.
import * as THREE from "three";
import { SVGLoader } from "./three-addons/SVGLoader.js";

const CFG = window.LICO;
const W = 1080, H = 1920, U = 100, FOV = 30;
const CAMZ = (H / 2 / U) / Math.tan((FOV / 2) * Math.PI / 180);
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const easeOutBack = (x) => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
const easeOut = (x) => 1 - Math.pow(1 - clamp(x), 3);
const easeInOut = (x) => { x = clamp(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
const rnd = (i) => { const s = Math.sin(i * 127.1 + 311.7) * 43758.5453; return s - Math.floor(s); };
const px = (x, y, z = 0) => new THREE.Vector3((x - W / 2) / U, (H / 2 - y) / U, z);
const loader = new THREE.TextureLoader();
let lastT = 0;

function textGeo(key, depth = 16, bevel = 2.4) {
  const g0 = CFG.glyphs[key];
  const data = new SVGLoader().parse(`<svg xmlns="http://www.w3.org/2000/svg"><path d="${g0.d}"/></svg>`);
  const shapes = data.paths.flatMap((p) => SVGLoader.createShapes(p));
  const g = new THREE.ExtrudeGeometry(shapes, { depth, bevelEnabled: true, bevelThickness: bevel, bevelSize: bevel * 0.55,
    bevelSegments: 3, curveSegments: 10 });
  g.center();
  g.scale(1 / U, 1 / U, 1 / U);  // глифы в y-up (textpath y_up=True) — без отрицательного масштаба
  g.computeBoundingBox();
  return g;
}
const gw = (g) => g.boundingBox.max.x - g.boundingBox.min.x;

function envMap(renderer) {  // студийная «комната» для отражений хрома и золота
  const pm = new THREE.PMREMGenerator(renderer);
  const sc = new THREE.Scene();
  sc.background = new THREE.Color(0x0b0d12);
  const box = (c, k, x, y, z, sx, sy, sz) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(sx, sy, sz), new THREE.MeshBasicMaterial({ color: new THREE.Color(c).multiplyScalar(k) }));
    m.position.set(x, y, z); sc.add(m);
  };
  box(0xffffff, 7, 0, 9, 0, 14, 0.4, 10);
  box(0xffd9a0, 5, -10, 2, 2, 0.4, 9, 8);
  box(0x9cc8ff, 4, 10, 1, 2, 0.4, 9, 8);
  box(0xffffff, 2.5, 0, 1, 12, 12, 5, 0.4);
  box(0x403020, 1, 0, -8, 0, 20, 0.4, 20);
  const tex = pm.fromScene(sc, 0.03).texture;
  pm.dispose();
  return tex;
}

function setup(sc, fov = FOV) {
  const canvas = document.getElementById(sc.canvas);
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setSize(W, H, false);
  renderer.setPixelRatio(1);
  renderer.setClearColor(0x000000, 0);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.15;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const scene = new THREE.Scene();
  scene.environment = envMap(renderer);
  const camera = new THREE.PerspectiveCamera(fov, W / H, 0.1, 500);
  camera.position.set(0, 0, CAMZ);
  scene.add(new THREE.HemisphereLight(0xfff2e0, 0x101420, 0.8));
  const key = new THREE.DirectionalLight(0xffffff, 2.2); key.position.set(3, 6, 10); scene.add(key);
  const rim = new THREE.DirectionalLight(0x8fc4ff, 1.6); rim.position.set(-6, 2, -4); scene.add(rim);
  return { renderer, scene, camera };
}

const CHROME = () => new THREE.MeshStandardMaterial({ color: 0xffffff, metalness: 1, roughness: 0.14 });
const GOLD = () => new THREE.MeshStandardMaterial({ color: 0xf0c46a, metalness: 1, roughness: 0.18 });

function particles(n, x0, x1, y0, y1, color, size) {
  const pos = new Float32Array(n * 3);
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  const m = new THREE.PointsMaterial({ color, size, transparent: true, opacity: 0.8, blending: THREE.AdditiveBlending, depthWrite: false,
    map: dotTex(), sizeAttenuation: true });
  const pts = new THREE.Points(g, m);
  pts.userData.step = (t) => {
    for (let i = 0; i < n; i++) {
      const sp = 0.15 + rnd(i + 5) * 0.35;
      const y = y0 + ((rnd(i + 1) * (y1 - y0) + t * sp) % (y1 - y0));
      pos[i * 3] = x0 + rnd(i) * (x1 - x0) + Math.sin(t * 0.7 + i) * 0.1;
      pos[i * 3 + 1] = y;
      pos[i * 3 + 2] = -2 + rnd(i + 2) * 4;
    }
    g.attributes.position.needsUpdate = true;
  };
  return pts;
}

let _dot;
function dotTex() {
  if (_dot) return _dot;
  const c = document.createElement("canvas"); c.width = c.height = 64;
  const x = c.getContext("2d"), gr = x.createRadialGradient(32, 32, 0, 32, 32, 32);
  gr.addColorStop(0, "rgba(255,255,255,1)"); gr.addColorStop(0.35, "rgba(255,255,255,.5)"); gr.addColorStop(1, "rgba(255,255,255,0)");
  x.fillStyle = gr; x.fillRect(0, 0, 64, 64);
  _dot = new THREE.CanvasTexture(c);
  return _dot;
}

function bar(a, b, r, mat) {  // толстая «линия» между двумя точками (WebGL-линии всегда 1 px)
  const d = new THREE.Vector3().subVectors(b, a), len = d.length();
  const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, len, 10), mat);
  m.position.copy(a).addScaledVector(d, 0.5);
  m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.normalize());
  return m;
}

function ring(color) {
  const m = new THREE.Mesh(new THREE.TorusGeometry(1, 0.03, 8, 96),
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
  return m;
}

// ---------- ХУК: хромированный «?/10» над головой + золотое «ПРАВДУ» внизу ----------
function buildHook(sc) {
  const { renderer, scene, camera } = setup(sc);
  const q = new THREE.Mesh(textGeo("q", 22, 3), CHROME());
  const ten = new THREE.Mesh(textGeo("s10", 18, 2.6), CHROME());
  const top = new THREE.Group(); top.add(q, ten); scene.add(top);
  const k = 2.6, wq = gw(q.geometry) * k, wt = gw(ten.geometry) * k, gap = 0.25, tw = wq + gap + wt;
  q.scale.setScalar(k); ten.scale.setScalar(k);
  q.position.x = -tw / 2 + wq / 2; ten.position.x = tw / 2 - wt / 2;
  const P0 = px(540, sc.topY ?? 340);
  const pr = new THREE.Mesh(textGeo("pravdu", 20, 3), GOLD());
  const kp = (sc.pravW ?? 900) / U / gw(pr.geometry);
  pr.scale.setScalar(kp);
  scene.add(pr);
  const P1 = px(540, sc.pravY ?? 1510);
  const shock = ring(0xffd88a); shock.position.copy(P1); scene.add(shock);
  const dust = particles(90, -5.4, 5.4, -9.6, 9.6, 0xffe2b0, 0.09); scene.add(dust);

  return (T) => {
    if (T < sc.t0 - 0.05 || T > sc.t1 + 0.6) return;
    const t = T - sc.t0, out = clamp((T - sc.t1 + 0.35) / 0.35);
    const a = clamp(t / 0.7);
    top.position.copy(P0).add(new THREE.Vector3(0, Math.sin(t * 1.6) * 0.08 + out * 3, 0));
    top.scale.setScalar(Math.max(0.0001, easeOutBack(a) * (1 - out)));
    top.rotation.set(-0.5 * (1 - easeOut(a)) + Math.sin(t * 1.1) * 0.05, Math.sin(t * 0.9) * 0.22, 0);
    q.rotation.set(0, Math.sin(t * 2.2) * 0.75 + (1 - easeOut(a)) * 6, Math.sin(t * 3) * 0.06);   // «?» крутится, как барабан
    ten.rotation.set(0, Math.sin(t * 1.3 + 1) * 0.12, 0);
    // «ПРАВДУ»: прилетает из камеры и бьёт в кадр
    const p = T - sc.pravT;
    if (p < 0) { pr.visible = false; shock.material.opacity = 0; }
    else {
      pr.visible = true;
      const e = easeOut(p / 0.28);
      pr.position.copy(P1).add(new THREE.Vector3(0, Math.sin(p * 2) * 0.05, (1 - e) * 26));
      pr.rotation.set((1 - e) * -0.9 + Math.sin(p * 1.5) * 0.04, Math.sin(p * 1.2) * 0.12, (1 - e) * 0.25);
      pr.scale.setScalar(kp * (1 + (p > 0.28 ? 0.06 * Math.exp(-(p - 0.28) * 10) : 0)) * (1 - out));
      const s = clamp((p - 0.24) / 0.6);
      shock.scale.setScalar(0.5 + s * 7); shock.material.opacity = p > 0.24 ? (1 - s) * 0.9 : 0;
    }
    // лёгкая тряска камеры от удара
    const sh = p > 0.26 ? Math.exp(-(p - 0.26) * 12) * 0.12 : 0;
    camera.position.set(Math.sin(T * 90) * sh, Math.cos(T * 77) * sh, CAMZ);
    dust.userData.step(t); dust.material.opacity = 0.55 * (1 - out);
    renderer.render(scene, camera);
  };
}

// ---------- СКАН ЛИЦА: фото + 3D-сетка (MediaPipe, 478 точек с глубиной) ----------
function buildScan(sc) {
  const { renderer, scene, camera } = setup(sc);
  const M = CFG.mesh, fw = sc.w / U, fh = sc.h / U;
  const grp = new THREE.Group(); grp.position.copy(px(sc.cx, sc.cy)); scene.add(grp);
  const tex = loader.load(sc.img, () => render(lastT)); tex.colorSpace = THREE.SRGBColorSpace;
  const photoM = new THREE.MeshBasicMaterial({ map: tex, transparent: true, toneMapped: false });
  const photo = new THREE.Mesh(new THREE.PlaneGeometry(fw, fh), photoM); grp.add(photo);
  const V = M.pts.map(([x, y, z]) => new THREE.Vector3((x - 0.5) * fw, (0.5 - y) * fh, -z * fw + 0.06));
  // сетка
  const pos = new Float32Array(M.tess.length * 6), col = new Float32Array(M.tess.length * 6);
  M.tess.forEach(([a, b], i) => { V[a].toArray(pos, i * 6); V[b].toArray(pos, i * 6 + 3); });
  const lg = new THREE.BufferGeometry();
  lg.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  lg.setAttribute("color", new THREE.BufferAttribute(col, 3));
  const lines = new THREE.LineSegments(lg, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.9,
    blending: THREE.AdditiveBlending, depthWrite: false }));
  grp.add(lines);
  // точки-«поры» (кожа)
  const pp = new Float32Array(V.length * 3); V.forEach((v, i) => v.toArray(pp, i * 3));
  const pg = new THREE.BufferGeometry(); pg.setAttribute("position", new THREE.BufferAttribute(pp, 3));
  const dots = new THREE.Points(pg, new THREE.PointsMaterial({ color: 0x9ff7d8, size: 0.09, map: dotTex(), transparent: true, opacity: 0,
    blending: THREE.AdditiveBlending, depthWrite: false }));
  grp.add(dots);
  // симметрия: ось через лоб (10) и подбородок (152)
  const gold = new THREE.MeshBasicMaterial({ color: 0xffd27a, transparent: true, opacity: 0 });
  const axisA = V[10].clone().add(new THREE.Vector3(0, 0.5, 0.1)), axisB = V[152].clone().add(new THREE.Vector3(0, -0.4, 0.1));
  const axis = bar(axisA, axisB, 0.02, gold); grp.add(axis);
  // пропорции: три трети — лоб (10) / межбровье (168) / под носом (2) / подбородок (152)
  const white = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0 });
  const thirds = [10, 168, 2, 152].map((i) => {
    const b = bar(new THREE.Vector3(-fw * 0.42, V[i].y, 0.35), new THREE.Vector3(fw * 0.42, V[i].y, 0.35), 0.012, white);
    grp.add(b); return b;
  });
  // линия челюсти: нижняя часть овала — золотые «трубки», рисуются слева направо
  const jawMat = new THREE.MeshBasicMaterial({ color: 0xffc35a, transparent: true, opacity: 1 });
  const ny = V[2].y;
  const jaw = M.oval.filter(([a, b]) => V[a].y < ny && V[b].y < ny)
    .map(([a, b]) => ({ a: V[a].clone().setZ(V[a].z + 0.05), b: V[b].clone().setZ(V[b].z + 0.05), x: (V[a].x + V[b].x) / 2 }))
    .sort((p, q) => p.x - q.x)
    .map((s) => { const m = bar(s.a, s.b, 0.03, jawMat); m.visible = false; grp.add(m); return m; });
  // скан-луч
  const beam = new THREE.Mesh(new THREE.PlaneGeometry(fw * 1.15, 0.04), new THREE.MeshBasicMaterial({ color: 0x7ff3ff, transparent: true,
    blending: THREE.AdditiveBlending, depthWrite: false }));
  const glow = new THREE.Mesh(new THREE.PlaneGeometry(fw * 1.15, 0.7), new THREE.MeshBasicMaterial({ color: 0x2fd6ff, transparent: true,
    opacity: 0.18, blending: THREE.AdditiveBlending, depthWrite: false }));
  beam.position.z = glow.position.z = 0.5; grp.add(beam, glow);
  const cyan = new THREE.Color(0x47e5ff), hot = new THREE.Color(0xffffff), tmp = new THREE.Color();

  function render(T) {
    if (T < sc.t0 - 0.05 || T > sc.t1 + 0.6) return;
    const t = T - sc.t0, a = easeOut(t / 0.6);
    grp.scale.setScalar(0.85 + 0.15 * a);
    grp.rotation.set(0.06 * Math.sin(t * 0.8), Math.sin(t * 0.9) * 0.42 * clamp(t / 1.2), 0);
    photoM.opacity = a * (1 - 0.45 * clamp((t - 0.5) / 0.6));
    // луч проходит лицо сверху вниз за 1,3 с, затем ходит медленно туда-обратно
    const s1 = clamp((t - 0.3) / 1.3), loop = t > 1.6 ? 0.5 - 0.5 * Math.cos((t - 1.6) * 1.6) : 0;
    const by = fh / 2 - fh * (t <= 1.6 ? s1 : 1 - loop);
    beam.position.y = glow.position.y = by;
    beam.material.opacity = glow.material.opacity = t > 0.3 ? 0.9 : 0;
    glow.material.opacity *= 0.2;
    for (let i = 0; i < pos.length / 3; i++) {
      const y = pos[i * 3 + 1], seen = t > 1.6 || y > by;
      const near = Math.exp(-Math.pow((y - by) / 0.18, 2));
      tmp.copy(cyan).multiplyScalar(seen ? 0.55 : 0).lerp(hot, near * 0.9);
      tmp.toArray(col, i * 3);
    }
    lg.attributes.color.needsUpdate = true;
    const f = (k) => clamp((T - sc.marks[k]) / 0.3);
    gold.opacity = f(0); axis.scale.y = Math.max(0.0001, easeOut(f(0)));
    white.opacity = f(1) * 0.9; thirds.forEach((b, i) => { b.scale.set(1, Math.max(0.0001, easeOut(clamp((T - sc.marks[1] - i * 0.08) / 0.3))), 1); });
    dots.material.opacity = f(2) * (0.6 + 0.4 * Math.sin(T * 9));
    dots.material.size = 0.07 + 0.03 * f(2);
    const jn = Math.floor(jaw.length * clamp((T - sc.marks[3]) / 0.6));
    jaw.forEach((m, i) => { m.visible = i < jn; });
    renderer.render(scene, camera);
  }
  return render;
}

// ---------- 3D-ОЧКИ ----------
function rrect(w, h, r) {
  const s = new THREE.Shape(), x = -w / 2, y = -h / 2;
  s.moveTo(x + r, y); s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r); s.lineTo(x + w, y + h - r);
  s.quadraticCurveTo(x + w, y + h, x + w - r, y + h); s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r);
  s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y);
  return s;
}

function buildGlasses(sc) {
  const { renderer, scene, camera } = setup(sc);
  const metal = new THREE.MeshStandardMaterial({ color: 0xf0c46a, metalness: 0.55, roughness: 0.3, emissive: 0x7a5414, emissiveIntensity: 0.6 });
  const g = new THREE.Group(); g.position.copy(px(sc.cx, sc.cy)); scene.add(g);
  const rim = rrect(2.3, 1.55, 0.5); rim.holes.push(rrect(2.0, 1.25, 0.4));
  const rg = new THREE.ExtrudeGeometry(rim, { depth: 0.14, bevelEnabled: true, bevelThickness: 0.04, bevelSize: 0.03, bevelSegments: 3, curveSegments: 16 });
  const lensM = new THREE.MeshStandardMaterial({ color: 0x9fc2ff, metalness: 0.2, roughness: 0.05, transparent: true, opacity: 0.22 });
  for (const sx of [-1, 1]) {
    const r = new THREE.Mesh(rg, metal); r.position.set(sx * 1.32, 0, -0.07); g.add(r);
    const l = new THREE.Mesh(new THREE.ShapeGeometry(rrect(2.0, 1.25, 0.4)), lensM); l.position.set(sx * 1.32, 0, 0); g.add(l);
    const tmpl = new THREE.Mesh(new THREE.BoxGeometry(0.09, 0.12, 3.2), metal); tmpl.position.set(sx * 2.48, 0.45, -1.6); g.add(tmpl);
    const tip = new THREE.Mesh(new THREE.BoxGeometry(0.09, 0.6, 0.12), metal); tip.position.set(sx * 2.48, 0.18, -3.18); tip.rotation.x = 0.4; g.add(tip);
  }
  const br = new THREE.Mesh(new THREE.TorusGeometry(0.26, 0.055, 12, 32, Math.PI), metal); br.position.set(0, 0.32, 0); g.add(br);
  const gl = ring(0x9fd0ff); gl.position.copy(px(sc.cx, sc.cy, -1)); scene.add(gl);
  const k0 = (sc.width ?? 560) / U / 5.3;
  return (T) => {
    if (T < sc.t0 - 0.05 || T > sc.t1 + 0.6) return;
    const t = T - sc.t0, a = clamp(t / 0.8), out = clamp((T - sc.t1 + 0.3) / 0.3);
    g.scale.setScalar(Math.max(0.0001, k0 * easeOutBack(a) * (1 - out)));
    g.rotation.set(0.12 + Math.sin(t * 1.4) * 0.06, (1 - easeOut(a)) * Math.PI * 2 + Math.sin(t * 1.1) * 0.35, 0);
    const s = clamp((t - 0.5) / 0.7); gl.scale.setScalar(1 + s * 4); gl.material.opacity = t > 0.5 ? (1 - s) * 0.7 : 0;
    renderer.render(scene, camera);
  };
}

// ---------- ИТОГ: золотые 3D-цифры «8,4» с прокруткой + «/10» ----------
function buildScore(sc) {
  const { renderer, scene, camera } = setup(sc);
  const dg = {}; for (const c of "0123456789,") dg[c] = textGeo("d" + (c === "," ? "c" : c), 22, 3);
  const grp = new THREE.Group(); grp.position.copy(px(sc.cx, sc.cy)); scene.add(grp);
  const k = sc.k ?? 4.2;
  const wD = Math.max(...[..."0123456789"].map((c) => gw(dg[c]))) * k, wC = gw(dg[","]) * k;
  const tenG = textGeo("s10", 16, 2.4), wT = gw(tenG) * k * 0.55;
  const total = wD * 2 + wC + 0.15 + wT;
  const slots = [-total / 2 + wD / 2, -total / 2 + wD + wC / 2, -total / 2 + wD + wC + wD / 2];
  const gold = GOLD();
  const mk = (geo, x, s) => { const m = new THREE.Mesh(geo, gold); m.scale.setScalar(s); m.position.x = x; grp.add(m); return m; };
  const A = [..."0123456789"].map((c) => mk(dg[c], slots[0], k));
  const comma = mk(dg[","], slots[1], k); comma.position.y = -0.95;
  const B = [..."0123456789"].map((c) => mk(dg[c], slots[2], k));
  const ten = new THREE.Mesh(tenG, CHROME()); ten.scale.setScalar(k * 0.55); ten.position.set(total / 2 - wT / 2, -0.75, 0); grp.add(ten);
  const flash = ring(0xffe3a0); flash.position.copy(px(sc.cx, sc.cy, 0.5)); scene.add(flash);
  const dust = particles(70, -5, 5, -3, 9, 0xffe2b0, 0.11); scene.add(dust);
  const target = Math.round(sc.value * 10);
  return (T) => {
    if (T < sc.t0 - 0.05 || T > sc.t1 + 0.6) return;
    const t = T - sc.t0, a = clamp(t / 0.6), out = clamp((T - sc.t1 + 0.3) / 0.3);
    const c = clamp((T - sc.countT) / sc.countD);
    const v = Math.round(target * (1 - Math.pow(1 - c, 2)));
    A.forEach((m, i) => { m.visible = i === Math.floor(v / 10); });
    B.forEach((m, i) => { m.visible = i === v % 10; });
    grp.scale.setScalar(Math.max(0.0001, easeOutBack(a) * (1 - out)));
    const done = T - sc.countT - sc.countD;
    grp.rotation.set(-0.15 + Math.sin(t * 1.2) * 0.05, (1 - easeOut(a)) * -1.4 + Math.sin(t * 0.8) * 0.18, 0);
    if (done > 0) grp.scale.multiplyScalar(1 + 0.08 * Math.exp(-done * 8));
    const s = clamp(done / 0.7); flash.scale.setScalar(1 + s * 6); flash.material.opacity = done > 0 ? (1 - s) * 0.9 : 0;
    dust.userData.step(t); dust.material.opacity = 0.6 * (1 - out);
    renderer.render(scene, camera);
  };
}

// ---------- ГАЛЕРЕЯ: три отчёта в 3D (ковер-флоу), камера наезжает на выбранный ----------
function buildGallery(sc) {
  const { renderer, scene, camera } = setup(sc);
  const ch = sc.cardH / U, cw = ch * sc.aspect;
  const cards = sc.imgs.map((src, i) => {
    const tex = loader.load(src, () => draw(lastT)); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
    const geo = new THREE.BoxGeometry(cw, ch, 0.06);
    const side = new THREE.MeshStandardMaterial({ color: 0x1b1f27, metalness: 0.6, roughness: 0.4 });
    const m = new THREE.Mesh(geo, [side, side, side, side, new THREE.MeshBasicMaterial({ map: tex, toneMapped: false }), side]);
    scene.add(m);
    const tag = new THREE.Mesh(textGeo("tag" + i, 18, 2.6), GOLD()); tag.scale.setScalar(1.25); scene.add(tag);
    return { m, tag };
  });
  const glowM = new THREE.MeshBasicMaterial({ color: 0xffd27a, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false });
  const halo = new THREE.Mesh(new THREE.PlaneGeometry(cw * 1.12, ch * 1.08), glowM); scene.add(halo);
  // ковер-флоу: позиция слота (−1, 0, 1) → x, z, поворот
  const slot = (s) => ({ x: s * cw * 0.86, z: -Math.abs(s) * 2.6, ry: -s * 0.62 });
  const lerp = (a, b, x) => a + (b - a) * x;
  const C0 = px(540, sc.cy ?? 900);
  function draw(T) {
    if (T < sc.t0 - 0.05 || T > sc.t1 + 0.6) return;
    const t = T - sc.t0;
    // фокус ковер-флоу: f = индекс карточки в центре (плавно)
    let f = sc.focus[0][1];
    for (let k = 1; k < sc.focus.length; k++) f = lerp(f, sc.focus[k][1], easeInOut((T - sc.focus[k][0]) / 0.7));
    // камера: план за планом (shots: [t, fx, fy, z] — точка на центральной карточке в долях её размера и дальность)
    const shots = sc.shots || [[sc.t0, 0, 0, CAMZ]];
    let cx = shots[0][1], cyy = shots[0][2], cz = shots[0][3];
    for (let k = 1; k < shots.length; k++) {
      const e = easeInOut((T - shots[k][0]) / 0.6);
      cx = lerp(cx, shots[k][1], e); cyy = lerp(cyy, shots[k][2], e); cz = lerp(cz, shots[k][3], e);
    }
    const tgt = new THREE.Vector3(C0.x + cx * cw, C0.y + cyy * ch, 0);
    const wob = clamp((cz - 12) / (CAMZ - 12));
    camera.position.set(tgt.x + Math.sin(t * 0.5) * 0.8 * wob, tgt.y + 0.4 * wob, cz);
    camera.lookAt(tgt);
    const far = clamp((cz - 16) / 10);
    cards.forEach(({ m, tag }, i) => {
      const s = i - f, sl = slot(Math.max(-1.6, Math.min(1.6, s)));
      const e = easeOut((t - i * 0.12) / 0.7);  // влёт из глубины веером
      m.position.set(C0.x + sl.x, C0.y + (1 - e) * -3, sl.z - (1 - e) * 30);
      m.rotation.set((1 - e) * 0.6, sl.ry + (1 - e) * (i - 1) * 1.2, 0);
      const front = Math.max(0, 1 - Math.abs(s));
      tag.position.set(m.position.x, C0.y + ch / 2 + 0.75 + Math.sin(t * 2 + i) * 0.06, m.position.z + 0.4);
      tag.rotation.set(-0.1, sl.ry * 0.6 + Math.sin(t * 1.3 + i) * 0.15, 0);
      tag.scale.setScalar(Math.max(0.0001, (0.9 + 0.5 * front) * e * far));
    });
    halo.position.set(C0.x, C0.y, -0.2); glowM.opacity = 0.18 + 0.08 * Math.sin(t * 3);
    renderer.render(scene, camera);
  }
  return draw;
}

const B = { hook: buildHook, scan: buildScan, glasses: buildGlasses, score: buildScore, gallery: buildGallery };
const renders = CFG.scenes.map((sc) => B[sc.mode](sc));
const renderAll = (t) => { lastT = t; renders.forEach((f) => f(t)); };
window.__arenaRender = renderAll;
window.addEventListener("hf-seek", (ev) => renderAll(ev.detail.time));
renderAll(window.__hfThreeTime || 0);
