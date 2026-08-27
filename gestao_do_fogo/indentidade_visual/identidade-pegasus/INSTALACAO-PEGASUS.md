# Instalar a identidade no projeto Pegasus

Pacote para SaaS Pegasus com Tailwind 4 e daisyUI 5. A ideia é redefinir o tema em vez de escrever CSS por cima: os templates que já vieram no boilerplate (`btn btn-primary`, `alert`, `table`, `navbar`, `card`, `input`) passam a sair na identidade sem edição de template.

## 1. Copiar os arquivos

Da raiz do projeto:

```
static/fonts/identidade/*.woff2                     as três famílias em woff2
assets/styles/identidade/fogo-theme.css             tokens, fontes e os dois temas daisyUI
assets/styles/identidade/fogo-componentes.css       base tipográfica e recursos do impresso
templates/web/identidade_demo.html                  página de conferência, opcional
```

## 2. Ligar no `assets/styles/site-tailwind.css`

Compare com `site-tailwind.css.exemplo`. As linhas que entram:

```css
@plugin "daisyui" {
  themes: false;
}
@import "./identidade/fogo-theme.css";
/* ... imports que o Pegasus já trouxe ... */
@import "./identidade/fogo-componentes.css";
```

O `themes: false` desliga os temas de fábrica do daisyUI. Sem isso, os temas `light` e `dark` continuam no bundle e brigam por especificidade no build de produção. Os temas `fogo` e `fogo-escuro` entram porque são declarados com `@plugin "daisyui/theme"`.

A ordem importa: o tema antes dos estilos do Pegasus, os componentes depois, para vencer no cascade sem `!important`.

## 3. Apontar os temas no Django

Em `settings.py`:

```python
LIGHT_THEME = "fogo"
DARK_THEME = "fogo-escuro"
```

E em `tailwind.config.js`, se o seu projeto ainda tem esse arquivo para o seletor de modo escuro:

```js
module.exports = {
  darkMode: ["class", '[data-theme="fogo-escuro"]'],
}
```

## 4. Reconstruir

```bash
npm install
npm run dev          # ou: make npm-dev no Docker
```

Para produção, `npm run build` antes do `collectstatic`.

## 5. Conferir

Aponte uma rota para a página de demonstração e abra:

```python
path("identidade/", TemplateView.as_view(template_name="web/identidade_demo.html"), name="identidade"),
```

Ajuste o `{% extends %}` e o nome do bloco do template conforme a base do seu projeto.

## Fontes: por que ficam em `static/` e não em `assets/`

As fontes são referenciadas por caminho absoluto `/static/fonts/identidade/...` dentro do `@font-face`. O Vite deixa caminhos absolutos intactos, o Django serve direto em desenvolvimento, e no `collectstatic` com `ManifestStaticFilesStorage` a reescrita de URL dentro do CSS acontece normalmente, versionando a fonte junto com o resto.

Se o seu `STATIC_URL` não for `/static/`, por exemplo quando o estático vai para CDN, ajuste o prefixo nos dez blocos `@font-face` do `fogo-theme.css`.

## Licença das fontes, antes de subir para produção

**Zilla Slab** (Mozilla, SIL Open Font License). Livre para servir por `@font-face`, inclusive em produto comercial. Sem restrição.

**Built Titling** (Typodermic). O ZIP da W5 traz a licença gratuita de desktop, que cobre peças e documento eletrônico do qual a fonte não possa ser extraída, como um PDF. Servir o arquivo por `@font-face` é justamente o caso em que o navegador baixa a fonte, e isso não está coberto por licença de desktop. Opções: comprar a licença de webfont da Typodermic para o domínio; usar Built Titling só nos PDFs e mapas exportados pela plataforma e adotar uma condensada aberta na tela; ou adotar a condensada aberta em tudo. Se optar por não licenciar, apague os três `@font-face` da Built Titling: o `--font-titulo` cai sozinho em Oswald, que é OFL e tem largura e ritmo próximos.

**Downcome** (Eduardo Recife, Misprinted Type). Freeware para trabalho comercial, mas o autor pede que a fonte não seja redistribuída nem modificada, e servir o `.woff2` é uma forma de redistribuição. Em tela ela também não sustenta texto pequeno, porque a textura desgastada some abaixo de 32 px. Use só no logotipo, em SVG com os contornos já convertidos, do jeito que a W5 fez no manual. A classe `.marca-topo` existe para o caso de você optar por licenciar; se não, troque por uma imagem.

## Mapeamento de cores do tema

| Papel daisyUI | Cor | De onde vem |
|---|---|---|
| `primary` | `#0D6C3E` | verde da floresta preservada, cor de ação |
| `secondary` | `#9E0A0E` | bordô, cabeçalhos de seção e tabela |
| `accent` | `#F5821F` | laranja do fogo ativo, destaque e foco |
| `neutral` | `#231F20` | preto das áreas devastadas |
| `error` | `#9E0A0E` | bordô, não o vermelho oficial |
| `warning` | `#F5821F` | laranja com texto preto |
| `success` | `#0D6C3E` | verde |
| `info` | `#575751` | cinza das cinzas |

Duas decisões que valem explicar para quem for mexer depois:

O verde virou a cor de ação em vez do vermelho da marca. Numa plataforma de fogo, vermelho e laranja precisam significar risco. Se o botão de salvar for vermelho, o alerta perde força.

O `error` usa bordô e não o vermelho oficial `#ED1C24`. O vermelho do manual dá 4,4:1 no branco, reprovando em texto normal pelo WCAG AA. O bordô dá 8,4:1. O vermelho oficial continua disponível como `bg-vermelho-500` para dataviz, ícone e texto grande.

## Utilitárias que o tema cria

```
bg-bordo-700   text-verde-700   border-laranja-400   bg-cinza-50
bg-queimada-1 ... bg-queimada-7     rampa de área queimada e severidade
bg-veg-1 ... bg-veg-5              rampa de vegetação e regeneração
bg-faixa-1 ... bg-faixa-7          degradê das faixas de metodologia
bg-sem-info                        cinza de ausência de dado
font-titulo  font-texto  font-marca
```

Classes próprias, para os recursos que o daisyUI não tem: `.rotulo-bloco`, `.linha-fogo`, `.secao-cab` com `.secao-num`, `.cartao-eixo`, `.faixas`, `.legenda-mapa`.

## Se algo não aparecer

Toda classe nova exige rebuild, porque o Tailwind só inclui o que encontrou nos arquivos. Rode `npm run dev` de novo e faça hard refresh. Se a classe estiver em um arquivo fora dos caminhos varridos, acrescente um `@source` no `site-tailwind.css`.
