# Identidade "Gestão do Fogo na Amazônia" na plataforma

Pacote derivado do manual de identidade visual da Agência W5 para o IPAM (arquivo InDesign, março de 2025) e dos arquivos de fonte entregues junto com ele.

## O que tem aqui

```
tokens.css        variáveis CSS: paleta, escalas, tipografia, espaçamento, dataviz
componentes.css   camada opcional de componentes (prefixo .gf-)
styleguide.html   guia navegável para consulta e validação visual
fonts/            as três famílias em woff2, subsetadas para latim + acentuação PT-BR (226 KB no total)
```

Uso mínimo em qualquer stack:

```html
<link rel="stylesheet" href="/static/identidade/tokens.css">
<link rel="stylesheet" href="/static/identidade/componentes.css">
```

A pasta `fonts/` precisa ficar ao lado do `tokens.css`, senão os caminhos `url("fonts/...")` quebram.

## Cores: valores exatos, não aproximados

As sete cores foram lidas dos objetos vetoriais do PDF, não amostradas de pixel:

| Papel no manual | Hex | Token |
|---|---|---|
| Fogo ativo, primeiros focos | `#F5821F` | `--of-laranja` |
| Urgência e alerta | `#ED1C24` | `--of-vermelho` |
| Queimada severa | `#9E0A0E` | `--of-bordo` |
| Área devastada, tinta | `#231F20` | `--of-preto` |
| Cinzas, transição | `#777770` | `--of-cinza` |
| Floresta preservada | `#0D6C3E` | `--of-verde` |
| Área em recuperação | `#9FAD63` | `--of-oliva` |

Sete cores bastam para um documento, mas não para uma interface, que precisa de fundo de campo desabilitado, borda de foco, linha zebrada, estado hover. As escalas de 50 a 900 foram geradas em OKLab preservando matiz e croma de cada cor oficial, e a cor do manual continua presente na rampa, sem deslocamento.

Além delas, o documento usa `#E9C4B4` no fundo das linhas de tabela, `#C5C6C1` na categoria "sem informação" dos gráficos e um degradê de sete faixas de `#B8553E` a `#9E0A0E` na página de metodologia. Esse degradê virou `--faixa-1` a `--faixa-7`.

## Tipografia e licença

Este é o ponto que precisa de decisão antes de subir para produção.

**Zilla Slab** (Mozilla, SIL Open Font License). Livre para servir por `@font-face`, inclusive em produto comercial. Sem restrição.

**Built Titling** (Typodermic). O ZIP traz a licença gratuita de desktop, que permite uso comercial em peças e a incorporação em documento eletrônico do qual a fonte não possa ser extraída, por exemplo um PDF. Servir o arquivo por `@font-face` em uma aplicação web é justamente o caso em que o navegador baixa a fonte, e isso não está coberto por licença de desktop. Três saídas:

1. comprar a licença de webfont da Typodermic para o domínio da plataforma;
2. usar Built Titling apenas nos artefatos gerados pela plataforma (PDF, PNG, mapas exportados), onde o texto sai convertido em contorno ou embutido de forma não extraível, e adotar na tela uma condensada de licença aberta;
3. adotar a condensada aberta em todo lugar e manter Built Titling só no material impresso do IPAM.

Se optar por 2 ou 3, os substitutos mais próximos em largura e ritmo são Oswald (600/700), Archivo Narrow (700) e Barlow Condensed (600/700), todos OFL. O `--fonte-titulo` já cai em Oswald automaticamente se Built Titling não carregar.

**Downcome** (Eduardo Recife, Misprinted Type). Freeware para trabalho comercial, mas o autor pede explicitamente que a fonte não seja redistribuída nem modificada. Servir o `.woff2` publicamente é uma forma de redistribuição, além de subsetar poder ser lido como modificação. O uso seguro e o que faz sentido visualmente é o mesmo: Downcome só no logotipo e na abertura, entregue como SVG com os contornos já convertidos, do jeito que a W5 fez no manual. Em tela ela também não sustenta texto pequeno, porque a textura desgastada some abaixo de 32 px.

Recomendação prática: peça à W5 o logotipo em SVG e trate a Downcome como asset de marca, não como fonte da aplicação.

## Papéis tipográficos

| Token | Família | Onde usar |
|---|---|---|
| `--fonte-marca` | Downcome | logotipo e título de abertura, nada mais |
| `--fonte-titulo` | Built Titling | títulos, rótulos, botões, cabeçalho de tabela, sempre em caixa alta |
| `--fonte-texto` | Zilla Slab | corpo, formulários, números, tudo que se lê em quantidade |

Built Titling é uma condensada de titulação. Em caixa baixa e em corpo pequeno ela fecha demais o contraforma, por isso a regra do manual vale igual em tela: caixa alta, `letter-spacing` de 0,08em nos rótulos, nunca em parágrafo.

## Tailwind

Tailwind 4, dentro do CSS principal:

```css
@import "tailwindcss";
@import "./identidade/tokens.css";

@theme inline {
  --color-laranja-400: var(--laranja-400);
  --color-vermelho-500: var(--vermelho-500);
  --color-bordo-700: var(--bordo-700);
  --color-verde-700: var(--verde-700);
  --color-oliva-400: var(--oliva-400);
  --color-cinza-950: var(--cinza-950);
  --font-titulo: var(--fonte-titulo);
  --font-texto: var(--fonte-texto);
}
```

Tailwind 3, em `tailwind.config.js`:

```js
theme: {
  extend: {
    colors: {
      laranja: {400:'#F5821F',500:'#CE5E00',700:'#973000'},
      vermelho:{500:'#ED1C24',700:'#B20000'},
      bordo:   {50:'#FFEFEB',700:'#9E0A0E',800:'#7C0206'},
      verde:   {50:'#EDFAF1',700:'#0D6C3E',800:'#004E29'},
      oliva:   {400:'#9FAD63',600:'#69752A'},
      cinza:   {50:'#F6F6F4',200:'#D2D2CE',600:'#777770',700:'#575751',950:'#231F20'}
    },
    fontFamily: {
      titulo: ['"Built Titling"','Oswald','sans-serif'],
      texto:  ['"Zilla Slab"','Georgia','serif']
    }
  }
}
```

## Regras de contraste que a paleta impõe

O laranja oficial dá 2,6:1 no branco. Ele não pode virar cor de texto nem de link, apenas preenchimento, traço e borda de foco. O vermelho oficial dá 4,4:1, o que reprova em texto normal e aprova em texto grande, ícone e dataviz. Para texto vermelho use `--vermelho-700` (`#B20000`, 7,3:1). Para botão destrutivo use fundo bordô com texto branco (8,4:1), não vermelho.

O verde `#0D6C3E` dá 6,5:1 no branco, então ele é a cor de ação da interface. Isso também resolve um problema semântico: em uma plataforma de fogo, vermelho e laranja precisam significar risco, não "clique aqui".

## Dataviz

- `--fogo-1` a `--fogo-7`: rampa sequencial para área queimada, frequência e severidade, terminando no preto do manual, que representa a área devastada.
- `--veg-1` a `--veg-5`: rampa sequencial para cobertura vegetal e regeneração.
- `--dv-1` a `--dv-7` mais `--dv-sem-info`: categórica na mesma ordem do gráfico de entrevistas do documento.

Em mapa coroplético, a rampa de fogo funciona sobre base cinza clara. Sobre imagem de satélite ela perde legibilidade nos dois primeiros passos, então nesse caso comece em `--fogo-3` e use contorno branco de 0,5 px nos polígonos.

## Pontos de atenção na transposição do impresso

O manual foi desenhado para A4 com muito preto e muita mancha vermelha em página inteira. Repetir isso em tela cansa e afunda a leitura de dados. A tradução adotada aqui mantém a marca sem escurecer a interface:

- fundo claro `#F6F6F4` como padrão, preto reservado para cabeçalho, rodapé e painel sobre mapa;
- bordô nos cabeçalhos de seção e de tabela, que é exatamente o papel dele no documento;
- vermelho e laranja restritos a estado, alerta e dado;
- verde como cor de ação e de estado estável;
- cantos retos ou quase, seguindo os blocos do logotipo, com raio máximo de 4 px.

Os recursos gráficos que valeu a pena trazer para componente: o bloco sólido de rótulo (`.gf-rotulo`, o mesmo recurso do "DO" e do "NA"), o numeral grande sobre bloco colorido (`.gf-eixo`), as faixas empilhadas em degradê (`.gf-faixas`) e a linha de degradê de fogo abaixo dos títulos (`.gf-secao__linha-fogo`).
