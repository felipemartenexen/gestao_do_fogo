/**
 * Controles do mapa: recorte territorial (global) e período (de cada camada).
 *
 * Fica separado de map.js porque não fala com o Leaflet - só lê o DOM e avisa quem
 * precisa recarregar. É também o que mantém os dois arquivos abaixo de 300 linhas.
 */

/** Rótulo do recorte, do mais específico ao mais amplo - a mesma regra que o backend usa. */
const NIVEIS = ['municipio', 'uf', 'bioma'];

export class Controles {
  /**
   * @param {HTMLElement} root
   * @param {{aoMudarTerritorio: Function, aoMudarPeriodo: Function}} eventos
   */
  constructor(root, eventos) {
    this.root = root;
    this.eventos = eventos;
    this.ligarTerritorio();
    this.ligarPeriodos();
    this.atualizarRecorte();
  }

  // --- recorte territorial ----------------------------------------------------

  get territorio() {
    const valor = (nome) => this.root.querySelector(`[name="${nome}"]`)?.value || '';
    return { bioma: valor('bioma'), uf: valor('uf'), municipio: valor('municipio') };
  }

  ligarTerritorio() {
    this.root.querySelectorAll('[data-filter]').forEach((el) => {
      el.addEventListener('change', () => {
        if (el.name === 'uf') this.carregarMunicipios(el.value);
        this.atualizarRecorte();
        // mudar UF e município em seguida dispararia duas rodadas de getMapId,
        // que é a parte cara: o debounce deixa só a última valer
        clearTimeout(this.timer);
        this.timer = setTimeout(() => this.eventos.aoMudarTerritorio(), 250);
      });
    });

    this.root.querySelector('[data-limpar-filtros]')?.addEventListener('click', () => {
      this.root.querySelectorAll('[data-filter]').forEach((el) => {
        el.selectedIndex = 0;
      });
      this.carregarMunicipios('');
      this.atualizarRecorte();
      this.eventos.aoMudarTerritorio();
    });
  }

  async carregarMunicipios(uf) {
    const select = this.root.querySelector('[name="municipio"]');
    if (!select) return;
    select.innerHTML = '<option value="">Carregando…</option>';
    select.disabled = true;
    if (!uf) {
      select.innerHTML = '<option value="">Todos os municípios</option>';
      return;
    }
    try {
      const url = this.root.dataset.municipalitiesUrl;
      const resposta = await fetch(`${url}?uf=${encodeURIComponent(uf)}`);
      const dados = await resposta.json();
      const opcoes = ['<option value="">Todos os municípios</option>'];
      (dados.municipios || []).forEach((m) => {
        opcoes.push(`<option value="${m.code}">${m.name}</option>`);
      });
      select.innerHTML = opcoes.join('');
      select.disabled = false;
    } catch (erro) {
      select.innerHTML = '<option value="">Não foi possível carregar</option>';
      console.error('firemap: municípios', erro);
    }
  }

  // --- período por camada -----------------------------------------------------

  get sincronizado() {
    return this.root.querySelector('[data-sincronizar]')?.checked ?? false;
  }

  periodo(camadaId) {
    const ano = this.root.querySelector(`[data-ano="${camadaId}"]`)?.value || '';
    const mes = this.root.querySelector(`[data-mes="${camadaId}"]`)?.value || '';
    return { ano, mes };
  }

  /** Ano de cada camada que tem controle de período, para o cabeçalho e a legenda. */
  get anos() {
    const mapa = {};
    this.root.querySelectorAll('[data-ano]').forEach((el) => {
      mapa[el.dataset.ano] = el.value;
    });
    return mapa;
  }

  parametros(camadaId) {
    return new URLSearchParams({ ...this.territorio, ...this.periodo(camadaId) });
  }

  ligarPeriodos() {
    this.root.querySelectorAll('[data-ano]').forEach((range) => {
      // `input` só pinta o número: arrastar de 1985 a 2025 pediria 40 vezes o mesmo tile
      range.addEventListener('input', () => this.pintarAno(range));
      range.addEventListener('change', () => this.aplicarAno(range));
    });
    this.root.querySelectorAll('[data-mes]').forEach((select) => {
      select.addEventListener('change', () => this.eventos.aoMudarPeriodo([select.dataset.mes]));
    });
    this.root.querySelector('[data-sincronizar]')?.addEventListener('change', (evento) => {
      if (!evento.target.checked) return;
      // ao religar, alinha todo mundo pelo maior ano em uso, senão fica ambíguo qual vence
      const anos = Object.values(this.anos).map(Number);
      this.definirAno(String(Math.max(...anos)));
      this.atualizarRecorte();
      this.eventos.aoMudarPeriodo(Object.keys(this.anos));
    });
  }

  pintarAno(range) {
    const saida = this.root.querySelector(`[data-ano-valor="${range.dataset.ano}"]`);
    if (saida) saida.textContent = range.value;
  }

  definirAno(ano) {
    this.root.querySelectorAll('[data-ano]').forEach((outro) => {
      // cada camada tem sua própria faixa: o FIRMS começa em 2000, a Coleção 5 em 1985
      const limitado = Math.min(Math.max(Number(ano), Number(outro.min)), Number(outro.max));
      outro.value = String(limitado);
      this.pintarAno(outro);
    });
  }

  aplicarAno(range) {
    if (this.sincronizado) {
      this.definirAno(range.value);
      this.atualizarRecorte();
      this.eventos.aoMudarPeriodo(Object.keys(this.anos));
      return;
    }
    this.pintarAno(range);
    this.atualizarRecorte();
    this.eventos.aoMudarPeriodo([range.dataset.ano]);
  }

  // --- rótulo do recorte ------------------------------------------------------

  /**
   * Escreve o recorte no cabeçalho.
   *
   * Com um ano por camada, o cabeçalho precisa avisar quando eles divergem: senão o
   * usuário compara 2010 com 2025 sem perceber e leva o print para o relatório.
   */
  atualizarRecorte() {
    const rotulo = (nome) => {
      const select = this.root.querySelector(`[name="${nome}"]`);
      return select?.value ? select.options[select.selectedIndex].text : '';
    };
    const lugar = NIVEIS.map(rotulo).find(Boolean) || 'Brasil';

    const ativas = [...this.root.querySelectorAll('[data-layer]:checked')].map((i) => i.dataset.layer);
    const anos = [...new Set(ativas.map((id) => this.anos[id]).filter(Boolean))];

    let periodo = '';
    if (anos.length === 1) {
      periodo = anos[0];
    } else if (anos.length > 1) {
      const ordenados = anos.map(Number).sort((a, b) => a - b);
      periodo = `anos diversos (${ordenados[0]}–${ordenados[ordenados.length - 1]})`;
    }

    this.root.querySelectorAll('[data-recorte]').forEach((el) => {
      el.textContent = [lugar, periodo].filter(Boolean).join(' · ');
    });

    // cada aba da direita fala de uma camada só, então mostra o ano DELA - a de risco não
    // tem ano nenhum, e herdar o ano da vizinha faria o painel mentir
    this.root.querySelectorAll('[data-recorte-resumo]').forEach((el) => {
      const ano = this.anos[el.dataset.recorteResumo];
      el.textContent = [lugar, ano].filter(Boolean).join(' · ');
    });
  }
}
