// 3D-арена для рилсов (Three.js, детерминированно от времени HyperFrames: hf-seek).
// Конфиг — window.ARENA = { path, scenes: [{canvas, t0, t1, mode: "spawn"|"fight", spawn, rounds:[{t, ids}], win, winT, crownT, groups}] }
import * as THREE from "three";
import { SVGLoader } from "./three-addons/SVGLoader.js";

const CFG = window.ARENA;
const W = 1080, H = 1920, N = 100;
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const easeOutBack = (x) => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
const easeInOut = (x) => x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
const rnd = (i) => { const s = Math.sin(i * 127.1 + 311.7) * 43758.5453; return s - Math.floor(s); };  // сид-случайность
const GROUP = [0x3aa8ff, 0xa78bfa, 0x22c55e, 0xf97316];

function logoGeometry() {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="${CFG.path}"/></svg>`;
  const data = new SVGLoader().parse(svg);
  const shapes = data.paths.flatMap((p) => SVGLoader.createShapes(p));
  const g = new THREE.ExtrudeGeometry(shapes, { depth: 2.2, bevelEnabled: true, bevelThickness: 0.5, bevelSize: 0.25, bevelSegments: 2, curveSegments: 8 });
  g.center();
  g.scale(0.055, -0.055, 0.055);
  return g;
}

function slot(i) {  // раскладка подсолнухом: от центра к краю
  const r = 7.6 * Math.sqrt((i + 0.5) / N), a = i * 2.39996;
  return { x: Math.cos(a) * r, z: Math.sin(a) * r, r };
}

function build(sc) {
  const canvas = document.getElementById(sc.canvas);
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, preserveDrawingBuffer: true });
  renderer.setSize(W, H, false);
  renderer.setPixelRatio(1);
  renderer.shadowMap.enabled = true;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.4;
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x07060a);
  scene.fog = new THREE.Fog(0x07060a, 22, 46);
  const camera = new THREE.PerspectiveCamera(48, W / H, 0.1, 200);

  scene.add(new THREE.HemisphereLight(0xffe6c8, 0x3a2414, 1.8));
  const key = new THREE.SpotLight(0xffd6a8, 900, 60, Math.PI / 5, 0.5, 1.6);
  key.position.set(0, 26, 6); key.castShadow = true; key.shadow.mapSize.set(1024, 1024);
  scene.add(key, key.target);
  const rimA = new THREE.PointLight(0xff7a3d, 260, 40); rimA.position.set(-12, 7, -8); scene.add(rimA);
  const rimB = new THREE.PointLight(0x3aa8ff, 200, 40); rimB.position.set(12, 6, -6); scene.add(rimB);

  // пол-песок, стена, ярусы трибун, колонны, зрители
  const sand = new THREE.Mesh(new THREE.CylinderGeometry(10, 10, 0.4, 96),
    new THREE.MeshStandardMaterial({ color: 0xc8925a, roughness: 0.95 }));
  sand.position.y = -0.2; sand.receiveShadow = true; scene.add(sand);
  const ringMark = new THREE.Mesh(new THREE.TorusGeometry(8.4, 0.06, 8, 128), new THREE.MeshStandardMaterial({ color: 0x8a5a33, roughness: 1 }));
  ringMark.rotation.x = Math.PI / 2; ringMark.position.y = 0.01; scene.add(ringMark);
  const stone = new THREE.MeshStandardMaterial({ color: 0x5a3c26, roughness: 0.9, side: THREE.DoubleSide });
  const wall = new THREE.Mesh(new THREE.CylinderGeometry(10.3, 10.3, 1.6, 96, 1, true), stone);
  wall.position.y = 0.6; scene.add(wall);
  for (let k = 0; k < 5; k++) {
    const rr = 11.4 + k * 1.7, hh = 1.6 + k * 1.15;
    const tier = new THREE.Mesh(new THREE.CylinderGeometry(rr + 1.7, rr, 0.55, 96, 1, true),
      new THREE.MeshStandardMaterial({ color: k % 2 ? 0x4a3020 : 0x3d2718, roughness: 0.95, side: THREE.DoubleSide }));
    tier.position.y = hh; scene.add(tier);
  }
  const crowdGeo = new THREE.SphereGeometry(0.22, 8, 6);
  const crowd = new THREE.InstancedMesh(crowdGeo, new THREE.MeshStandardMaterial({ roughness: 0.8 }), 900);
  const m4 = new THREE.Matrix4(), col = new THREE.Color();
  for (let i = 0; i < 900; i++) {
    const k = i % 5, a = rnd(i) * Math.PI * 2, rr = 12.2 + k * 1.7 + rnd(i + 7) * 0.6;
    m4.makeTranslation(Math.cos(a) * rr, 2.2 + k * 1.15 + rnd(i + 3) * 0.2, Math.sin(a) * rr);
    crowd.setMatrixAt(i, m4);
    crowd.setColorAt(i, col.setHSL(rnd(i + 11), 0.5, 0.35 + rnd(i + 5) * 0.3));
  }
  scene.add(crowd);
  const colGeo = new THREE.CylinderGeometry(0.45, 0.55, 8, 16);
  const colMat = new THREE.MeshStandardMaterial({ color: 0xb8a58a, roughness: 0.7 });
  for (let i = 0; i < 28; i++) {
    const a = (i / 28) * Math.PI * 2, c = new THREE.Mesh(colGeo, colMat);
    c.position.set(Math.cos(a) * 21.5, 7.5, Math.sin(a) * 21.5); scene.add(c);
  }

  // 100 объёмных логотипов Claude
  const geo = logoGeometry();
  const mat = new THREE.MeshStandardMaterial({ color: 0xffffff, metalness: 0.35, roughness: 0.32, emissive: 0x3a1408 });
  const logos = new THREE.InstancedMesh(geo, mat, N);
  logos.castShadow = true;
  logos.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  scene.add(logos);
  const base = new THREE.Color(0xd97757);
  for (let i = 0; i < N; i++) logos.setColorAt(i, sc.groups ? new THREE.Color(GROUP[(i * 7) % 4]) : base);

  // 3D-корона
  const crown = new THREE.Group();
  const gold = new THREE.MeshStandardMaterial({ color: 0xffc94a, metalness: 0.9, roughness: 0.2, emissive: 0x3a2400 });
  const band = new THREE.Mesh(new THREE.CylinderGeometry(0.75, 0.75, 0.45, 32, 1, true), gold);
  crown.add(band);
  for (let k = 0; k < 6; k++) {
    const a = (k / 6) * Math.PI * 2, sp = new THREE.Mesh(new THREE.ConeGeometry(0.16, 0.6, 12), gold);
    sp.position.set(Math.cos(a) * 0.72, 0.5, Math.sin(a) * 0.72); crown.add(sp);
    const gem = new THREE.Mesh(new THREE.SphereGeometry(0.09, 10, 8), new THREE.MeshStandardMaterial({ color: k % 2 ? 0xff3b6b : 0x2ee6a6, emissive: 0x220011 }));
    gem.position.set(Math.cos(a) * 0.76, 0.05, Math.sin(a) * 0.76); crown.add(gem);
  }
  crown.visible = false;
  scene.add(crown);

  const out = new Map();  // id → время вылета
  (sc.rounds || []).forEach((r) => r.ids.forEach((id) => out.set(id, r.t)));
  const q = new THREE.Quaternion(), e = new THREE.Euler(), p = new THREE.Vector3(), s = new THREE.Vector3();
  const tint = new THREE.Color();

  function renderAt(T) {
    if (T < sc.t0 - 0.05 || T > sc.t1 + 0.5) return;
    const t = T - sc.t0;
    for (let i = 0; i < N; i++) {
      const o = slot(i);
      let x = o.x, z = o.z, y = 0.85, sca = 1, ry = t * 0.9 + i * 0.7, rz = 0;
      if (sc.mode === "spawn") {
        const ti = sc.spawn - sc.t0 + (o.r / 7.6) * 1.9;
        const k = clamp((t - ti) / 0.45);
        sca = k <= 0 ? 0.0001 : easeOutBack(k);
        y = 0.85 + (1 - clamp(k * 1.4)) * 5;
        ry = t * 1.3 + i;
      } else {
        ry = Math.sin(t * 3 + i) * 0.6 + (i % 2 ? Math.PI : 0) * 0.15 + t * 0.4;
        x += Math.sin(t * 17 + i * 1.7) * 0.12;
        z += Math.cos(t * 13 + i * 2.3) * 0.12;
        rz = Math.sin(t * 21 + i) * 0.18;
        const ot = out.get(i);
        if (ot !== undefined && T >= ot) {
          const d = T - ot;
          y += d * 9 + d * d * 6; sca = Math.max(0.0001, 1 - d * 2.4); ry += d * 14; rz += d * 9;
          logos.setColorAt(i, tint.set(0xffffff).lerp(new THREE.Color(0xff2d2d), clamp(d * 4)));
        } else if (i === sc.win && T >= sc.winT) {
          const k = easeInOut(clamp((T - sc.winT) / 0.8));
          x = o.x * (1 - k); z = o.z * (1 - k); y = 0.85 + k * 1.6; sca = 1 + k * 2.4; ry = t * 1.6; rz = 0;
          logos.setColorAt(i, tint.set(GROUP[(i * 7) % 4]).lerp(new THREE.Color(0xffd27a), k));
        } else {
          logos.setColorAt(i, tint.set(GROUP[(i * 7) % 4]));
        }
      }
      p.set(x, y, z); e.set(0, ry, rz); q.setFromEuler(e); s.setScalar(sca);
      m4.compose(p, q, s); logos.setMatrixAt(i, m4);
    }
    logos.instanceMatrix.needsUpdate = true;
    if (logos.instanceColor) logos.instanceColor.needsUpdate = true;

    // корона падает на победителя
    if (sc.mode === "fight" && T >= sc.crownT) {
      const k = clamp((T - sc.crownT) / 0.6);
      crown.visible = true;
      crown.position.set(0, 0.85 + 1.6 + 3.4 * 0.55 + (1 - easeOutBack(k)) * 4, 0);
      crown.rotation.y = T * 1.2;
      crown.scale.setScalar(1.25);
    } else crown.visible = false;

    // камера: облёт, в бою — наезд на победителя
    let ang = 0.6 + t * 0.16, rad = 16, hgt = 16, look = 0;
    if (sc.mode === "spawn") { const k = easeInOut(clamp(t / 7)); rad = 21 - k * 5; hgt = 21 - k * 5; }
    else if (T >= sc.winT) { const k = easeInOut(clamp((T - sc.winT) / 1.2)); rad = 16 - k * 7; hgt = 16 - k * 9.5; look = k * 2.6; }
    camera.position.set(Math.cos(ang) * rad, hgt, Math.sin(ang) * rad);
    camera.lookAt(0, look, 0);
    renderer.render(scene, camera);
  }
  return renderAt;
}

// Прозрачные 3D-сцены поверх кадра (без арены): hook — один большой логотип → взрыв в 100 копий;
// squads — 4 отряда по 9 логотипов в сетке 2×2 (появляются по очереди)
function buildFloat(sc) {
  const canvas = document.getElementById(sc.canvas);
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setSize(W, H, false);
  renderer.setPixelRatio(1);
  renderer.setClearColor(0x000000, 0);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.35;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(40, W / H, 0.1, 200);
  scene.add(new THREE.HemisphereLight(0xfff0e0, 0x1a1020, 1.6));
  const key = new THREE.DirectionalLight(0xffe2c4, 3.2); key.position.set(4, 8, 10); scene.add(key);
  const rimA = new THREE.PointLight(0xff7a3d, 220, 40); rimA.position.set(-8, 6, -4); scene.add(rimA);
  const rimB = new THREE.PointLight(0x3aa8ff, 180, 40); rimB.position.set(8, 2, -4); scene.add(rimB);
  const geo = logoGeometry();
  const mat = new THREE.MeshStandardMaterial({ color: 0xffffff, metalness: 0.45, roughness: 0.28, emissive: 0x2a0e04 });
  const n = sc.mode === "hook" ? N + 1 : 36;
  const logos = new THREE.InstancedMesh(geo, mat, n);
  logos.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  scene.add(logos);
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), p = new THREE.Vector3(), s = new THREE.Vector3();
  const c = new THREE.Color(), grey = new THREE.Color(0x8a8f99), orange = new THREE.Color(0xd97757);
  const CY = sc.cy ?? 5.2;  // высота «центра» графики над карточкой с лицом
  camera.position.set(0, CY - 1.2, 16);
  camera.lookAt(0, CY - 2.2, 0);

  function renderAt(T) {
    if (T < sc.t0 - 0.05 || T > sc.t1 + 0.6) return;
    const t = T - sc.t0;
    if (sc.mode === "hook") {
      // 0 — главный логотип; 1..100 — копии
      const dull = clamp((T - sc.dullT) / 0.4), burst = T - sc.burstT;
      let sc0 = 2.3 * easeOutBack(clamp(t / 0.6)), ry = Math.sin(t * 1.4) * 0.7, rz = Math.sin(t * 2) * 0.08 * (1 + dull * 2);
      let y0 = CY + Math.sin(t * 1.7) * 0.15 - dull * 0.35;
      c.copy(orange).lerp(grey, dull * (burst < 0 ? 1 : 0));
      if (burst >= 0) { const k = clamp(burst / 0.35); sc0 *= 1 + k * 0.6; sc0 *= burst > 0.35 ? Math.max(0.0001, 1 - (burst - 0.35) * 4) : 1;
        c.copy(orange).lerp(new THREE.Color(0xffd0a0), Math.max(0, 1 - burst * 2)); ry += burst * 12; }
      logos.setColorAt(0, c);
      p.set(0, y0, 0); e.set(0.15, ry, rz); q.setFromEuler(e); s.setScalar(sc0); m4.compose(p, q, s); logos.setMatrixAt(0, m4);
      for (let i = 1; i <= N; i++) {
        if (burst < 0) { s.setScalar(0.0001); m4.compose(p.set(0, CY, 0), q, s); logos.setMatrixAt(i, m4); continue; }
        // направление разлёта — фибоначчи-сфера, часть копий летит в камеру
        const yy = 1 - (2 * (i - 0.5)) / N, rr = Math.sqrt(1 - yy * yy), a = i * 2.39996;
        const dir = new THREE.Vector3(Math.cos(a) * rr * 1.1, yy * 0.55 + 0.25, Math.sin(a) * rr * 0.6);
        const k = 1 - Math.pow(1 - clamp(burst / 1.1), 3);
        let dist = 2 + k * (5 + rnd(i) * 4);
        // «турнир»: орбита + столкновения
        const f = T - sc.fightT;
        let ox = 0, oy = 0;
        if (f >= 0) { ox = Math.sin(f * 19 + i) * 0.25; oy = Math.cos(f * 15 + i * 2) * 0.2; dist *= 1 - clamp(f / 0.8) * 0.25; }
        const orbit = burst * 0.35;
        const dx = dir.x * Math.cos(orbit) - dir.z * Math.sin(orbit), dz = dir.x * Math.sin(orbit) + dir.z * Math.cos(orbit);
        p.set(dx * dist + ox, Math.max(CY - 1.6, CY + dir.y * dist * 0.9 + oy), dz * dist);
        e.set(burst * (1 + rnd(i + 3) * 3), burst * 2 + i, f >= 0 ? Math.sin(f * 25 + i) * 0.5 : 0); q.setFromEuler(e);
        s.setScalar(0.6 + rnd(i + 9) * 0.5); m4.compose(p, q, s); logos.setMatrixAt(i, m4);
        logos.setColorAt(i, c.set(f >= 0 ? GROUP[i % 4] : 0xd97757));
      }
    } else {  // squads: 2×2, в каждом отряде 9 копий своего цвета
      for (let g = 0; g < 4; g++) {
        const k = clamp((T - sc.appear[g]) / 0.5), gx = g % 2 ? 1.63 : -1.63, gy = CY + (g < 2 ? 0.91 : -0.54);
        for (let j = 0; j < 9; j++) {
          const i = g * 9 + j, ax = (j % 3 - 1) * 0.72, ay = (Math.floor(j / 3) - 1) * 0.38;
          const sca = k <= 0 ? 0.0001 : easeOutBack(k) * 0.42;
          p.set(gx + ax, gy + ay + (1 - k) * 3, (j % 2) * 0.3);
          e.set(0.1, t * 1.5 + j + g, Math.sin(t * 3 + j) * 0.1); q.setFromEuler(e); s.setScalar(sca);
          m4.compose(p, q, s); logos.setMatrixAt(i, m4); logos.setColorAt(i, c.set(GROUP[g]));
        }
      }
    }
    logos.instanceMatrix.needsUpdate = true;
    if (logos.instanceColor) logos.instanceColor.needsUpdate = true;
    renderer.render(scene, camera);
  }
  return renderAt;
}

const renders = CFG.scenes.map((sc) => (sc.mode === "hook" || sc.mode === "squads") ? buildFloat(sc) : build(sc));
const renderAll = (t) => renders.forEach((f) => f(t));
window.__arenaRender = renderAll;
window.addEventListener("hf-seek", (ev) => renderAll(ev.detail.time));
renderAll(window.__hfThreeTime || 0);
