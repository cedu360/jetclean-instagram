# Faz posts novos da JetClean sozinho quando a fila está acabando. Textos do Gemini (chave grátis em GEMINI_API_KEY);
# fotos do banco fotos/ (fotos reais do lava jato, placas já borradas), com corte, zoom, cores e layout sorteados (sem espelhar: as fotos têm letreiros).
# Cada peça nova é comparada com todas as anteriores (hash da imagem) e refeita se ficar parecida demais.
# O que o negócio é (cidade, contato, temas, tom) fica em negocio.json: mude lá, não aqui.
# Uso: python3 gerar.py               gera POR_VEZ peças se sobrarem menos de IG_FILA_MINIMA fotos novas na fila
#      python3 gerar.py --inicial 12  gera 12 peças já, com os textos de reserva (sem Gemini)
#      python3 gerar.py --teste       gera 2 peças em teste/ sem mexer na fila
import json, os, random, sys, time, urllib.request
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))
KIT, FOTOS, PECAS = (os.path.join(AQUI, p) for p in ("kit", "fotos", "pecas"))
NEG = json.load(open(os.path.join(AQUI, "negocio.json")))
CHAVE = os.environ.get("GEMINI_API_KEY", "")
MODELOS = os.environ.get("GEMINI_MODELO_TEXTO", "gemini-3.5-flash-lite,gemini-flash-lite-latest").split(",")
MINIMO = int(os.environ.get("IG_FILA_MINIMA", 4))
POR_VEZ = int(os.environ.get("IG_GERAR_POR_VEZ", 2))
DIST_MINIMA = 12  # bits de diferença no hash (de 64) para não sair imagem quase igual
args = sys.argv[1:]
TESTE = "--teste" in args
INICIAL = int(args[args.index("--inicial") + 1]) if "--inicial" in args else 0

BRANCO, CIANO = (255, 255, 255), (230, 28, 36)  # CIANO = cor de destaque (vermelho da marca)
PALETAS = [((8, 8, 10), (40, 6, 8)), ((14, 14, 16), (30, 30, 34)), ((24, 4, 6), (90, 10, 14)), ((10, 10, 12), (60, 12, 16))]

def fonte(peso, t): return ImageFont.truetype(os.path.join(KIT, f"Inter-{peso}.otf"), t)
def degrade(w, h, a, b):
    g = Image.new("RGB", (1, h))
    for y in range(h): g.putpixel((0, y), tuple(int(a[i] + (b[i] - a[i]) * y / h) for i in range(3)))
    return g.resize((w, h))
def sombra_baixo(w, h, ini, forca=235):
    g = Image.new("L", (1, h))
    for y in range(h): g.putpixel((0, y), 0 if y < h * ini else min(forca, int(forca * (y - h * ini) / (h * (1 - ini) * 0.6))))
    return g.resize((w, h))
def foto(nome, w, h, aleatorio=True):
    f = Image.open(os.path.join(FOTOS, nome + ".jpg")).convert("RGB")
    z = random.uniform(1.0, 1.25) if aleatorio else 1.0
    s = max(w / f.width, h / f.height) * z
    f = f.resize((int(f.width * s) + 1, int(f.height * s) + 1), Image.LANCZOS)
    x = random.randint(0, f.width - w) if aleatorio else (f.width - w) // 2
    y = random.randint(int((f.height - h) * 0.2), int((f.height - h) * 0.6)) if aleatorio else (f.height - h) // 2
    return f.crop((x, y, x + w, y + h))
def quebrar(d, texto, f, maxw):
    linhas, l = [], ""
    for w in texto.split():
        t = (l + " " + w).strip()
        if d.textlength(t, font=f) > maxw and l: linhas.append(l); l = w
        else: l = t
    return linhas + [l]
def escrever(d, texto, x, y, maxw, tam, destaque=""):
    while len(quebrar(d, texto, fonte("ExtraBold", tam), maxw)) > 3: tam -= 6
    f = fonte("ExtraBold", tam); marcadas = set(destaque.split()); esp = d.textlength(" ", font=f)
    for l in quebrar(d, texto, f, maxw):
        xx = x
        for w in l.split(): d.text((xx, y), w, font=f, fill=CIANO if w in marcadas else BRANCO); xx += d.textlength(w, font=f) + esp
        y += int(tam * 1.12)
    return y
def check(d, x, y, texto, tam=36):
    d.ellipse((x, y + 4, x + 36, y + 40), fill=CIANO); d.line((x + 9, y + 22, x + 16, y + 30, x + 28, y + 14), fill=BRANCO, width=5)
    d.text((x + 54, y), texto, font=fonte("SemiBold", tam), fill=BRANCO)
def logo(c, x, y, tam=54):
    arq = os.path.join(KIT, "logo.png")
    if os.path.exists(arq):
        l = Image.open(arq).convert("RGBA"); l.thumbnail((tam * 6, tam * 2), Image.LANCZOS); c.alpha_composite(l, (x, y)); return
    d = ImageDraw.Draw(c); f = fonte("ExtraBold", tam); p = fonte("Bold", max(14, tam // 3))
    d.text((x + 2, y - tam // 3 - 4), "AUTO ESTÉTICA", font=p, fill=(200, 200, 205))
    d.text((x, y), "JET", font=f, fill=CIANO); d.text((x + d.textlength("JET ", font=f), y), "CLEAN", font=f, fill=BRANCO)
def selo(d, x, y, texto, tam=30):
    f = fonte("Bold", tam); w = d.textlength(texto, font=f)
    d.rounded_rectangle((x, y, x + w + 48, y + tam + 26), (tam + 26) // 2, fill=CIANO); d.text((x + 24, y + 11), texto, font=f, fill=BRANCO)
def botao(d, x, y, texto, tam=38):
    f = fonte("ExtraBold", tam); w = d.textlength(texto, font=f) + 88
    d.rounded_rectangle((x, y, x + w, y + tam + 44), (tam + 44) // 2, fill=CIANO); d.text((x + 44, y + 20), texto, font=f, fill=BRANCO)

def feed_a(p, tema, pal):  # foto em cima, texto embaixo
    W, H = 1080, 1350; c = degrade(W, H, *pal).convert("RGBA")
    fo = foto(random.choice(tema["fotos"]), W, 760).convert("RGBA")
    m = Image.new("L", (1, 760)); [m.putpixel((0, y), 255 if y < 500 else int(255 * (760 - y) / 260)) for y in range(760)]
    c.paste(fo, (0, 0), m.resize((W, 760))); d = ImageDraw.Draw(c)
    selo(d, 60, 56, tema["selo"]); y = escrever(d, p["gancho"], 60, 700, W - 120, 78, p["destaque"]) + 24
    for b in p["pontos"]: check(d, 60, y, b); y += 64
    botao(d, 60, max(y + 20, H - 230), NEG["contato"]); logo(c, W - 330, H - 110, 50); return c.convert("RGB")
def feed_b(p, tema, pal):  # foto inteira, texto sobre a sombra
    W, H = 1080, 1350; c = foto(random.choice(tema["fotos"]), W, H).convert("RGBA")
    sombra = Image.new("RGBA", (W, H), pal[0] + (255,)); c = Image.composite(sombra, c, sombra_baixo(W, H, 0.38)); d = ImageDraw.Draw(c)
    selo(d, 60, 56, tema["selo"]); y = escrever(d, p["gancho"], 60, 790, W - 120, 82, p["destaque"]) + 20
    for b in p["pontos"]: check(d, 60, y, b, 34); y += 60
    logo(c, 60, H - 100, 46); d.text((W - 60 - d.textlength(NEG["rodape"], font=fonte("SemiBold", 30)), H - 88), NEG["rodape"], font=fonte("SemiBold", 30), fill=BRANCO)
    return c.convert("RGB")
def feed_antes_depois(p, tema, pal):
    W, H = 1080, 1350; c = degrade(W, H, *pal).convert("RGBA"); d = ImageDraw.Draw(c)
    for i, (nome, rot) in enumerate(zip(tema["antes_depois"], ("ANTES", "DEPOIS"))):
        f = foto(nome, 500, 760, aleatorio=False); x = 30 + i * 520; c.paste(f, (x, 150))
        selo(d, x + 20, 170, rot, 30)
    selo(d, 60, 56, tema["selo"]); y = escrever(d, p["gancho"], 60, 950, W - 120, 72, p["destaque"]) + 16
    d.text((60, y), " · ".join(p["pontos"][:2]), font=fonte("SemiBold", 32), fill=(210, 225, 240))
    logo(c, 60, H - 100, 46); d.text((W - 60 - d.textlength(NEG["rodape"], font=fonte("SemiBold", 30)), H - 88), NEG["rodape"], font=fonte("SemiBold", 30), fill=BRANCO)
    return c.convert("RGB")
def story(p, tema, pal):
    W, H = 1080, 1920; c = foto(random.choice(tema["fotos"]), W, H).convert("RGBA")
    sombra = Image.new("RGBA", (W, H), pal[0] + (255,)); c = Image.composite(sombra, c, sombra_baixo(W, H, 0.35, 240)); d = ImageDraw.Draw(c)
    selo(d, 70, 140, tema["selo"], 34); y = escrever(d, p["gancho"], 70, 1080, W - 140, 100, p["destaque"]) + 30
    for b in p["pontos"]: check(d, 70, y, b, 38); y += 70
    botao(d, 70, y + 30, NEG["contato"], 42); logo(c, 70, H - 200, 56)
    d.text((70, H - 120), NEG["rodape"].split(" · ")[-1], font=fonte("SemiBold", 34), fill=BRANCO); return c.convert("RGB")

def ahash(img):
    g = img.convert("L").resize((8, 8), Image.LANCZOS); px = list(g.tobytes()); m = sum(px) / 64
    return "".join("1" if v > m else "0" for v in px)
def dist(a, b): return sum(x != y for x, y in zip(a, b))

def gemini(modelo, corpo):
    r = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
        data=json.dumps(corpo).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": CHAVE})
    return json.load(urllib.request.urlopen(r, timeout=90))
def textos(tema, usados, reserva_ok):
    if CHAVE and not TESTE and not reserva_ok:
        p = (f"Crie um post curto para o Instagram da {NEG['nome']}, lava jato em {NEG['cidade']}. Assunto: {tema['assunto']}. Tom: {NEG['tom']}. "
             "Responda só JSON: {\"gancho\": frase de no máximo 42 caracteres, \"destaque\": as 1 a 3 últimas palavras do gancho, "
             "\"pontos\": 3 vantagens com no máximo 26 caracteres cada, \"legenda\": 2 ou 3 frases curtas para a legenda, sem hashtags}. "
             "Português do Brasil com acentos corretos, sem emojis no gancho e nos pontos, sem inventar preço, prazo, desconto, promoção ou garantia, "
             f"sem citar nome de empresa cliente. Não repita estes ganchos: {'; '.join(usados[-25:])}")
        for m in MODELOS:
            try:
                j = gemini(m.strip(), {"contents": [{"parts": [{"text": p}]}], "generationConfig": {"responseMimeType": "application/json", "temperature": 1.1}})
                t = json.loads(next(x["text"] for x in j["candidates"][0]["content"]["parts"] if "text" in x))
                if len(t["gancho"]) <= 55 and len(t["pontos"]) == 3 and all(len(x) <= 30 for x in t["pontos"]) and t["gancho"] not in usados: return t, m
                print("Texto do Gemini fora do tamanho ou repetido")
            except Exception as e: print(f"Gemini ({m}) falhou:", e)
        print("Usando texto de reserva")
    livres = [r for r in tema["reserva"] if r[0] not in usados]
    if not livres: return None, "sem texto novo"
    g, dst, pts = random.choice(livres); return {"gancho": g, "destaque": dst, "pontos": pts, "legenda": ""}, "reserva"

def legenda(t, tema):
    tags = " ".join([tema["hashtag"]] + NEG["hashtags_fixas"])
    corpo = (t.get("legenda") or "").strip()
    return (f"{t['gancho']} ✨\n\n" + (corpo + "\n\n" if corpo else "") + "\n".join("✅ " + x for x in t["pontos"])
            + f"\n\n📲 {NEG['contato']}\n📍 {NEG.get('endereco', NEG['cidade'])}\n\n{tags}")

def nova_peca(slug, fila, usados, i, reserva_ok=False):
    tema = NEG["temas"][slug]; t, origem = textos(tema, usados, reserva_ok)
    if not t: print(f"  {slug}: textos de reserva já usados, pulando"); return []
    usados.append(t["gancho"])
    hashes = [x["ahash"] for x in fila if x.get("ahash")]
    for tentativa in range(10):
        pal = random.choice(PALETAS)
        layouts = [feed_a, feed_b] + ([feed_antes_depois] if tema.get("antes_depois") else [])
        if tema.get("antes_depois") and "antes" in t["gancho"].lower(): layouts = [feed_antes_depois]
        img = random.choice(layouts)(t, tema, pal); h = ahash(img)
        if all(dist(h, o) >= DIST_MINIMA for o in hashes): break
        print(f"  {slug}: ficou parecida com uma peça antiga, refazendo")
    else: print(f"  {slug}: não achei variação diferente o bastante, pulando"); return []
    st = story(t, tema, pal); hs = ahash(st)
    pasta = os.path.join(AQUI, "teste") if TESTE else PECAS; os.makedirs(pasta, exist_ok=True)
    base = f"{slug}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}-{i}"
    img.save(os.path.join(pasta, f"feed-{base}.jpg"), "JPEG", quality=88); st.save(os.path.join(pasta, f"story-{base}.jpg"), "JPEG", quality=88)
    print(f"Gerado {base}: {t['gancho']} ({origem})")
    pre = "teste" if TESTE else "pecas"
    return [{"tipo": "FEED", "arquivo": f"{pre}/feed-{base}.jpg", "legenda": legenda(t, tema), "tema": "#" + slug, "aprovado": True, "gerado": origem, "ahash": h},
            {"tipo": "STORIES", "arquivo": f"{pre}/story-{base}.jpg", "tema": "#" + slug, "aprovado": True, "gerado": origem, "ahash": hs}]

if __name__ == "__main__":
    fila = json.load(open(os.path.join(AQUI, "fila.json")))
    estado = json.load(open(os.path.join(AQUI, "estado.json")))
    livres = [x for x in fila if x["tipo"] == "FEED" and x.get("aprovado") and (x["arquivo"] not in estado or str(estado[x["arquivo"]].get("pulado", "")).startswith("legenda"))]
    quantas = INICIAL or (2 if TESTE else POR_VEZ)
    if not INICIAL and not TESTE and len(livres) >= MINIMO: print(f"Fila com {len(livres)} fotos novas, nada a gerar"); sys.exit(0)
    usos = {s: sum(1 for x in fila if x.get("tema") == "#" + s) for s in NEG["temas"]}
    usados = [x["legenda"].split("\n")[0] for x in fila if x.get("legenda")]
    novos = []
    for i in range(quantas):
        slug = min(NEG["temas"], key=lambda s: (usos[s], random.random())); usos[slug] += 1
        novos += nova_peca(slug, fila + novos, usados, i, reserva_ok=bool(INICIAL))
        if CHAVE and not INICIAL: time.sleep(2)
    if not TESTE:
        with open(os.path.join(AQUI, "fila.json"), "w") as f: json.dump(fila + novos, f, ensure_ascii=False, indent=1)
