# Prepara fotos novas para o visual de estúdio: recorta o carro do fundo e salva em fotos/recortes/<nome>.png.
# Roda no computador (não no GitHub): pip install "rembg[cpu]" scipy pillow
# Uso: python3 preparar.py fotos/carro-prata.jpg [outras...]
# ATENÇÃO: a placa precisa estar borrada ANTES (o repositório é público). Confira o recorte: postes e objetos colados no carro podem sobrar.
import os, sys
import numpy as np
from PIL import Image, ImageFilter
from rembg import remove, new_session
from scipy import ndimage

SAIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fotos", "recortes")
os.makedirs(SAIDA, exist_ok=True)
sessao = new_session("isnet-general-use")
for arq in sys.argv[1:]:
    p = remove(Image.open(arq).convert("RGB"), session=sessao)
    m = np.array(p.getchannel("A")) > 140
    lab, n = ndimage.label(m)
    if n > 1: m = lab == 1 + int(np.argmax(ndimage.sum(m, lab, range(1, n + 1))))  # fica só o maior pedaço: o carro
    m = ndimage.binary_opening(m, iterations=4)
    a = Image.fromarray((m * 255).astype("uint8")).filter(ImageFilter.GaussianBlur(1.2))
    p.putalpha(a); p = p.crop(a.point(lambda v: 255 if v > 200 else 0).getbbox())
    nome = os.path.splitext(os.path.basename(arq))[0]
    p.save(os.path.join(SAIDA, nome + ".png")); print("Recorte:", nome, p.size)
