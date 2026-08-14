/**
 * Painel direito: números do recorte atual, vindos das planilhas já consolidadas.
 *
 * Cada aba busca sozinha e só quando o recorte ou o ano dela muda - abrir o mapa não
 * dispara quatro consultas de uma vez.
 */

const ha = (valor) => `${Math.round(valor).toLocaleString('pt-BR')} ha`;

const pct = (valor) => `${valor > 0 ? '+' : ''}${valor.toFixed(0)}%`;

/** Barra proporcional ao maior item da lista - comparação relativa sem eixo nem biblioteca. */
function barras(itens, rotuloDe, valorDe) {
  const maior = Math.max(...itens.map(valorDe), 1);
  return itens
    .map((item) => {
      const largura = (valorDe(item) / maior) * 100;
      return `
        <div class="mapa-barra">
          <div class="mapa-barra-topo">
            <span class="mapa-barra-rotulo">${rotuloDe(item)}</span>
            <span class="mapa-barra-valor tabular">${ha(valorDe(item))}</span>
          </div>
          <div class="mapa-barra-trilho"><i style="width:${largura.toFixed(1)}%"></i></div>
        </div>`;
    })
    .join('');
}

function serieAnual(serie, anoAtivo) {
  const maior = Math.max(...serie.map((p) => p.ha), 1);
  const colunas = serie
    .map(
      (p) => `<i class="mapa-serie-col${p.ano === anoAtivo ? ' is-ativo' : ''}"
                 style="height:${Math.max((p.ha / maior) * 100, 1).toFixed(1)}%"
                 title="${p.ano}: ${ha(p.ha)}"></i>`,
    )
    .join('');
  const primeiro = serie[0]?.ano;
  const ultimo = serie[serie.length - 1]?.ano;
  return `
    <div class="mapa-card">
      <p class="rotulo text-[0.65rem] text-base-content/50">Série anual</p>
      <div class="mapa-serie">${colunas}</div>
      <div class="mapa-serie-eixo tabular"><span>${primeiro}</span><span>${ultimo}</span></div>
    </div>`;
}

function kpi(rotulo, valor, apoio = '') {
  return `
    <div class="mapa-kpi">
      <p class="mapa-kpi-rot">${rotulo}</p>
      <p class="mapa-kpi-num tabular">${valor}</p>
      ${apoio ? `<p class="mapa-kpi-apoio">${apoio}</p>` : ''}
    </div>`;
}

const RENDERIZADORES = {
  area_queimada(d) {
    // sem ranking quando o recorte é o Brasil: não há par com quem comparar
    let posicao = '';
    if (d.ranking) {
      posicao = d.ranking.posicao ? `${d.ranking.posicao}º de ${d.ranking.de} no ano` : 'não queimou no ano';
    }
    const anomalia =
      d.anomalia_pct === null
        ? ''
        : kpi('Contra a média histórica', pct(d.anomalia_pct), `média: ${ha(d.media_ha)}`);
    return kpi(`Queimado em ${d.ano}`, ha(d.total_ha), posicao) + anomalia + serieAnual(d.serie, d.ano);
  },

  monitor_fogo(d) {
    const aviso = d.rebaixado
      ? '<p class="mapa-nota">A planilha mensal para no estado: estes números são do estado inteiro.</p>'
      : '';
    const meses = `
      <div class="mapa-card">
        <p class="rotulo text-[0.65rem] text-base-content/50">Sazonalidade de ${d.ano}</p>
        ${barras(d.meses, (m) => m.nome, (m) => m.ha)}
      </div>`;
    const cobertura = `
      <div class="mapa-card">
        <p class="rotulo text-[0.65rem] text-base-content/50">O que queimou</p>
        ${barras(d.cobertura, (c) => c.classe, (c) => c.ha)}
      </div>`;
    return aviso + kpi(`Queimado em ${d.ano}`, ha(d.total_ha)) + meses + cobertura;
  },

  risco_potencial(d) {
    // a unidade aqui é território classificado, não área queimada: sem o aviso, o número
    // (dezenas de milhões de hectares) é lido como queimada
    const nota = `<p class="mapa-nota">
      Território classificado por risco na temporada ${d.temporada} — não é área queimada.
    </p>`;
    const classes = `
      <div class="mapa-card">
        <p class="rotulo text-[0.65rem] text-base-content/50">Classes de risco</p>
        ${barras(d.classes, (c) => c.classe, (c) => c.ha)}
      </div>`;
    const fundiaria = `
      <div class="mapa-card">
        <p class="rotulo text-[0.65rem] text-base-content/50">Por categoria fundiária</p>
        ${barras(d.fundiaria, (f) => f.categoria, (f) => f.ha)}
      </div>`;
    return nota + classes + fundiaria;
  },
};

export class Estatisticas {
  constructor(root, controles) {
    this.root = root;
    this.controles = controles;
    this.urlTemplate = root.dataset.statsUrl;
    this.requisicoes = new Map();
    this.alvos = [...root.querySelectorAll('[data-stats]')].map((el) => el.dataset.stats);
  }

  /** Recarrega as abas indicadas, ou todas quando o recorte muda. */
  atualizar(camadas = this.alvos) {
    camadas.filter((id) => this.alvos.includes(id)).forEach((id) => this.buscar(id));
  }

  async buscar(camadaId) {
    const destino = this.root.querySelector(`[data-stats="${camadaId}"]`);
    if (!destino) return;

    this.requisicoes.get(camadaId)?.abort();
    const controlador = new AbortController();
    this.requisicoes.set(camadaId, controlador);
    destino.innerHTML = '<p class="mapa-nota">Calculando…</p>';

    try {
      const url = `${this.urlTemplate.replace('PLACEHOLDER', camadaId)}?${this.controles.parametros(camadaId)}`;
      const resposta = await fetch(url, { signal: controlador.signal });
      const dados = await resposta.json();
      if (!dados.disponivel) {
        destino.innerHTML = `<p class="mapa-nota">${dados.motivo || dados.error || 'Sem dado.'}</p>`;
        return;
      }
      destino.innerHTML = RENDERIZADORES[camadaId]?.(dados) ?? '';
    } catch (erro) {
      if (erro.name === 'AbortError') return;
      destino.innerHTML = '<p class="mapa-nota">Não foi possível calcular.</p>';
      console.error('firemap: estatística', camadaId, erro);
    }
  }
}
