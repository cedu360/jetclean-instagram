# Robô do Instagram da JetClean (@jetclean_360)

Publica sozinho no Instagram do lava jato JetClean, pela API oficial do Instagram (nunca com a senha).
Roda no GitHub Actions a cada 30 minutos; não depende de computador ligado nem de sessão do Claude.
Separado do 3Tap: repositório, token, fila e imagens próprios.

## Ritmo do dia (horário de Brasília)

| Horário | Turno | O que sai        |
|---------|-------|------------------|
| 09h36   | manha | 1 foto + 1 story |
| 11h45   | reel1 | 1 reel (quando houver) |
| 14h06   | tarde | 1 foto + 1 story |
| 16h45   | reel2 | 1 reel (quando houver) |
| 19h36   | noite | 1 foto + 1 story |

No máximo 3 fotos, 3 stories e 2 reels por dia, contados no próprio perfil.
Antes de postar o robô lê o perfil e pula o que repetiria (mesma imagem, legenda parecida, mesmo tema nas últimas 24 h).

## Arquivos

- `publicar.mjs`: publica o turno. `node publicar.mjs manha --teste` mostra o que sairia.
- `gerar.py`: quando sobram menos de 4 fotos novas na fila, faz 2 posts novos (feed + story). Texto do Gemini grátis,
  foto do banco `fotos/` com corte, zoom, cores e layout sorteados; peça parecida demais com uma antiga é refeita.
- `negocio.json`: tudo sobre o lava jato (cidade, contato, tom, temas e textos de reserva). Mude aqui.
- `fotos/`: fotos reais do lava jato, **com as placas e os números de frota borrados**. Foto nova só entra borrada.
- `pecas/`: posts prontos. `fila.json`: ordem de preferência. `estado.json`: o que já saiu (não editar à mão).
- `kit/`: fontes Inter (licença OFL). Pondo um `kit/logo.png`, ele substitui o nome escrito.

## Segredos (Settings > Secrets and variables > Actions)

- `IG_TOKEN`: token do Instagram da JetClean (API do Instagram com login do Instagram). Vale 60 dias e o robô renova a cada post.
- `GEMINI_API_KEY`: chave grátis do Google AI Studio para os textos. Sem ela o robô usa os textos de reserva.

Nada de seguir pessoas nem mandar direct automático: risco de bloqueio da conta.
