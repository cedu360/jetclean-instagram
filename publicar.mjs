// Publica no Instagram da JetClean (@jetclean_360) pela API oficial. O token vem só da variável IG_TOKEN (segredo do repositório).
// Uso:  node publicar.mjs [manha|reel1|tarde|reel2|noite] [--teste]
//         sem turno, escolhe pelo relógio de Brasília. --teste mostra o que sairia, sem publicar.
//       node publicar.mjs FEED|STORIES|REELS <arquivo> ["legenda"]   publica um item avulso
// Ritmo do dia: manhã, tarde e noite = 1 foto + 1 story; reel1 (entre manhã e tarde) e reel2 (entre tarde e noite) = 1 reel.
// No máximo 3 fotos, 3 stories e 2 reels por dia, contados no próprio perfil.
// Antes de cada post o robô lê o perfil e pula o que repetiria: mesmo arquivo, mesma imagem (hash),
// legenda parecida com uma recente, ou mesmo tema (profissão) nas últimas 24 h. Segue para o próximo da fila.
// Reaproveita: quando não há nada novo aprovado, repete o item aprovado publicado há mais tempo (no mínimo IG_RECICLAR_DIAS, padrão 30;
// stories somem em 24 h, então voltam depois de IG_RECICLAR_STORIES_DIAS, padrão 5). Legenda parecida só adia (janela de 3 dias), não descarta.
// Só sai o que tem "aprovado": true na fila.json (peça revisada). Itens publicados ou descartados ficam em estado.json (IG_ESTADO) e nunca saem duas vezes.
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";

const API = "https://graph.instagram.com/v23.0";
const token = process.env.IG_TOKEN;
const aqui = dirname(fileURLToPath(import.meta.url));
const ESTADO = process.env.IG_ESTADO || join(aqui, "estado.json");
const estado = existsSync(ESTADO) ? JSON.parse(readFileSync(ESTADO, "utf8")) : {};
const agoraBR = new Date(Date.now() - 3 * 3600e3);
const hojeBR = agoraBR.toISOString().slice(0, 10);
const diaBR = (iso) => new Date(Date.parse(iso) - 3 * 3600e3).toISOString().slice(0, 10);
const espera = (ms) => new Promise((r) => setTimeout(r, ms));
const RECICLAR = Number(process.env.IG_RECICLAR_DIAS || 30) * 86400e3;
const RECICLAR_STORIES = Number(process.env.IG_RECICLAR_STORIES_DIAS || 5) * 86400e3;
const PARECIDA_DIAS = 3 * 86400e3;
const LIMITE = { FEED: 3, STORIES: 3, REELS: 2 };
const TURNOS = { manha: ["FEED", "STORIES"], reel1: ["REELS"], tarde: ["FEED", "STORIES"], reel2: ["REELS"], noite: ["FEED", "STORIES"] };
const GENERICAS = new Set(["#jetclean", "#lavajato", "#itabirito"]);

async function api(path, params, method = "POST", base = API) {
  const url = new URL(base + path);
  for (const [k, v] of Object.entries({ access_token: token, ...params })) url.searchParams.set(k, v);
  const r = await fetch(url, { method });
  const j = await r.json();
  if (!r.ok || j.error) throw new Error(`${path}: ${JSON.stringify(j.error || j)}`);
  return j;
}
const palavras = (t = "") => new Set(t.toLowerCase().replace(/#\S+|[^\p{L}\p{N}\s]/gu, " ").split(/\s+/).filter((w) => w.length > 3));
function parecida(a, b) {
  const A = palavras(a), B = palavras(b); if (!A.size || !B.size) return false;
  let c = 0; for (const w of A) if (B.has(w)) c++;
  return c / Math.min(A.size, B.size) >= 0.6;
}
const tema = (it) => it.tema || ((it.legenda || "").match(/#\S+/g) || []).map((h) => h.toLowerCase()).find((h) => !GENERICAS.has(h)) || null;
// Imagens saem direto do repositório público. Vídeo (reel) precisa de um endereço completo (http...) que mande o tipo video/mp4.
const BASE_IMAGENS = process.env.IG_BASE_FOTOS || "https://raw.githubusercontent.com/cedu360/jetclean-instagram/main";
const urlDe = (arq) => (arq.startsWith("http") ? arq : `${BASE_IMAGENS}/${arq}`);
async function hashDe(arq) {
  // usa a cópia local quando existe
  for (const local of [join(aqui, "imagens", arq), join(aqui, arq)])
    if (!arq.startsWith("http") && existsSync(local)) return createHash("sha1").update(readFileSync(local)).digest("hex");
  const r = await fetch(urlDe(arq)); if (!r.ok) throw new Error(`Arquivo fora do ar (${r.status}): ${urlDe(arq)}`);
  return createHash("sha1").update(Buffer.from(await r.arrayBuffer())).digest("hex");
}

// O que já está no perfil: posts e reels recentes, stories das últimas 24 h
async function lerPerfil(eu) {
  const m = await api(`/${eu.user_id}/media`, { fields: "caption,media_type,media_product_type,timestamp", limit: 40 }, "GET");
  let s = { data: [] };
  try { s = await api(`/${eu.user_id}/stories`, { fields: "timestamp" }, "GET"); } catch {}
  const recentes = m.data.map((x) => ({ tipo: x.media_product_type === "REELS" ? "REELS" : "FEED", legenda: x.caption || "", em: x.timestamp }));
  for (const x of s.data) recentes.push({ tipo: "STORIES", legenda: "", em: x.timestamp });
  return recentes;
}
function motivoRepetido(it, h, recentes, reciclado = false) {
  if (!reciclado && Object.values(estado).some((e) => e.hash === h && !e.pulado)) return "mesma imagem já publicada";
  if (it.legenda && recentes.some((r) => Date.parse(r.em) > Date.now() - PARECIDA_DIAS && parecida(it.legenda, r.legenda))) return "legenda";
  const t = tema(it), limite = Date.now() - 86400e3;
  if (t && (recentes.some((r) => Date.parse(r.em) > limite && r.legenda.toLowerCase().includes(t)) ||
    Object.values(estado).some((e) => e.tema === t && !e.pulado && Date.parse(e.em) > limite))) return "tema";
  return null;
}

async function publicar(eu, it) {
  const url = urlDe(it.arquivo);
  const p = {};
  if (it.tipo === "REELS") Object.assign(p, { media_type: "REELS", video_url: url, share_to_feed: "true" });
  else if (it.tipo === "STORIES") Object.assign(p, { media_type: "STORIES", [/\.(mp4|mov)$/i.test(url) ? "video_url" : "image_url"]: url });
  else p.image_url = url;
  if (it.legenda && it.tipo !== "STORIES") p.caption = it.legenda;
  const cont = await api(`/${eu.user_id}/media`, p);
  let ok = false;
  for (let i = 0; i < 60 && !ok; i++) {
    const s = await api(`/${cont.id}`, { fields: "status_code" }, "GET");
    if (s.status_code === "FINISHED") ok = true;
    else if (s.status_code === "ERROR") throw new Error(`Instagram recusou ${url}`);
    else await espera(5000);
  }
  if (!ok) throw new Error(`Tempo esgotado processando ${url}`);
  for (let i = 0; ; i++) { // a Meta às vezes diz "não está pronto" logo após FINISHED
    try { return await api(`/${eu.user_id}/media_publish`, { creation_id: cont.id }); }
    catch (e) { if (i >= 5 || !String(e.message).includes("9007")) throw e; await espera(10000); }
  }
}
let falhou = false;
const salvar = () => writeFileSync(ESTADO, JSON.stringify(estado, null, 1));

const args = process.argv.slice(2), teste = args.includes("--teste");
const [a, b, c] = args.filter((x) => x !== "--teste");
if (!token && !teste) { console.log("Falta o segredo IG_TOKEN (token do Instagram da JetClean). Nada publicado."); process.exit(0); }
const fila = JSON.parse(readFileSync(join(aqui, "fila.json"), "utf8"));
let pedidos;
if (["FEED", "STORIES", "REELS"].includes(a) && b) pedidos = [{ avulso: { tipo: a, arquivo: b, legenda: c } }];
else {
  const h = agoraBR.getUTCHours() + agoraBR.getUTCMinutes() / 60;
  // "auto" (agendamento de hora em hora): faz o último turno que já começou e ainda não saiu hoje.
  // O agendamento do GitHub atrasa ou pula horários; assim um atraso não perde o post nem posta duas vezes.
  const INICIO = { manha: 9.6, reel1: 11.75, tarde: 14.1, reel2: 16.75, noite: 19.6 };
  let turno = a === "auto" ? Object.keys(INICIO).filter((t) => h >= INICIO[t]).pop() : a || (h < 11 ? "manha" : h < 13 ? "reel1" : h < 16 ? "tarde" : h < 19 ? "reel2" : "noite");
  if (a === "auto") {
    const feitos = estado._turnos?.[hojeBR] || [];
    if (!turno || feitos.includes(turno)) { console.log(`Nada a fazer agora (${turno || "antes do primeiro turno"}${turno ? " já saiu" : ""}).`); process.exit(0); }
    if (!teste) { estado._turnos = { [hojeBR]: [...feitos, turno] }; }
  }
  if (!TURNOS[turno]) { console.error("Uso: node publicar.mjs [manha|reel1|tarde|reel2|noite] [--teste]  ou  FEED|STORIES|REELS arquivo [legenda]"); process.exit(1); }
  console.log(`Turno ${turno} de ${hojeBR}`);
  pedidos = TURNOS[turno].map((tipo) => ({ tipo }));
}

const eu = token ? await api("/me", { fields: "user_id,username" }, "GET") : null;
const recentes = eu ? await lerPerfil(eu) : [];
const hoje = { FEED: 0, STORIES: 0, REELS: 0 };
for (const r of recentes) if (diaBR(r.em) === hojeBR) hoje[r.tipo]++;
let n = 0;
for (const ped of pedidos) {
  let it = ped.avulso;
  if (it) it.hash = await hashDe(it.arquivo);
  else {
    if (hoje[ped.tipo] >= LIMITE[ped.tipo]) { console.log(`${ped.tipo}: já tem ${hoje[ped.tipo]} hoje no perfil, limite atingido.`); continue; }
    for (const cand of fila.filter((x) => x.tipo === ped.tipo && x.aprovado && (!estado[x.arquivo] || String(estado[x.arquivo].pulado).startsWith("legenda")))) {
      const h = await hashDe(cand.arquivo), motivo = motivoRepetido(cand, h, recentes);
      if (!motivo) { it = { ...cand, hash: h }; break; }
      if (motivo === "tema") { console.log(`Adiado ${cand.arquivo}: tema ${tema(cand)} saiu nas últimas 24 h`); continue; }
      if (motivo === "legenda") { console.log(`Adiado ${cand.arquivo}: legenda parecida com post dos últimos 3 dias`); continue; }
      console.log(`Descartado ${cand.arquivo}: ${motivo}`);
      if (!teste) { estado[cand.arquivo] = { pulado: motivo, em: new Date().toISOString() }; salvar(); }
    }
    if (!it) { // nada novo: reaproveita o aprovado que saiu há mais tempo
      const velhos = fila.filter((x) => x.tipo === ped.tipo && x.aprovado && estado[x.arquivo]?.id && Date.now() - Date.parse(estado[x.arquivo].em) > (ped.tipo === "STORIES" ? RECICLAR_STORIES : RECICLAR))
        .sort((x, y) => Date.parse(estado[x.arquivo].em) - Date.parse(estado[y.arquivo].em));
      for (const cand of velhos) if (!motivoRepetido(cand, estado[cand.arquivo].hash, recentes, true)) { it = { ...cand, hash: estado[cand.arquivo].hash, vezes: (estado[cand.arquivo].vezes || 1) + 1 }; break; }
      if (it) console.log(`Reaproveitando ${it.arquivo} (vez ${it.vezes})`);
    }
    if (!it) { console.log(`${ped.tipo}: nada aprovado e novo na fila. Precisa de mais conteúdo revisado.`); continue; }
  }
  if (teste) { console.log(`Sairia agora: ${it.tipo} ${it.arquivo}`); continue; }
  if (n++) await espera(4 * 60e3); // alguns minutos entre itens do mesmo turno
  let pub;
  try { pub = await publicar(eu, it); }
  catch (e) { // a Meta às vezes perde o contêiner ("Media Not Found"): tenta de novo do zero, uma vez
    console.log(`Aviso: ${it.arquivo} falhou (${e.message}); tentando de novo`);
    try { pub = await publicar(eu, it); } catch (e2) { console.log(`Falhou ${it.arquivo}: ${e2.message}`); falhou = true; continue; }
  }
  estado[it.arquivo] = { id: pub.id, em: new Date().toISOString(), tipo: it.tipo, hash: it.hash, tema: tema(it), ...(it.vezes ? { vezes: it.vezes } : {}) };
  salvar(); hoje[it.tipo]++;
  recentes.push({ tipo: it.tipo, legenda: it.legenda || "", em: new Date().toISOString() });
  console.log(`Publicado ${it.tipo} ${it.arquivo}: mídia ${pub.id}`);
}

if (!teste) salvar();
if (token && !teste) try {
  const t = await api("/refresh_access_token", { grant_type: "ig_refresh_token" }, "GET", "https://graph.instagram.com");
  console.log(`Token renovado, vale mais ${Math.round(t.expires_in / 86400)} dias`);
} catch (e) { console.log("Aviso: não renovou o token:", e.message); }
if (falhou) process.exit(1);
