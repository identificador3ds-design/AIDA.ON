# Assets de demonstração dos cards

Gerados por `aida-space/ferramentas/gerar_assets_demo.py`. **Não edite à mão** —
rode o script de novo.

## image/demo.webp

Recorte central de `real159.jpg`, uma fotografia real do acervo do projeto,
redimensionada para 960×540.

## forensics/

Saídas **reais** das funções de explicabilidade do AIDA, calculadas sobre
exatamente o mesmo recorte de `image/demo.webp` — é isso que faz o divisor
before/after do card casar pixel a pixel.

| Arquivo              | Função                                            |
| -------------------- | ------------------------------------------------- |
| `demo_gradient.webp` | `mapa_gradiente` + `sobrepor`                     |
| `demo_noise.webp`    | `mapa_ruido` + `sobrepor`                         |
| `demo_fft.webp`      | `mapas_espectrais` (magnitude, log) + `colorir`   |

Gradiente e ruído são mapas alinhados aos pixels e vão sobrepostos à imagem,
como no pipeline. O espectro vive no domínio da frequência e é apenas
colorizado — sobrepor frequências a pixels não teria significado.

## video/

**Não são frames de um vídeo.** O repositório não tem vídeo de demonstração, e
as fotos do acervo não formam nenhuma rajada — a maior sequência de capturas
parecidas tem duas.

Os 6 arquivos são um travelling sintético: uma janela de recorte que
caminha da esquerda para a direita sobre `real186.jpg`, uma fotografia
panorâmica real. É o que uma câmera em movimento produziria.

O card usa isso para demonstrar o conceito "vídeo → frames → análise temporal".
Ele não afirma que o AIDA analisa vídeo: o selo "Em desenvolvimento" continua
no card e na página do produto.

Quando houver um vídeo de demonstração de verdade, troque a origem no script e
rode de novo — o resto do site não muda.

## Peso total

383 kB para os 11 arquivos.
