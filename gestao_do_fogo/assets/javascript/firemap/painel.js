/**
 * Chrome do mapa do fogo: abrir/fechar os painéis e trocar de aba.
 *
 * O Alpine cuida só disso. Quem fala com o Leaflet e com o backend é a classe FireMap,
 * em map.js. Os dois se comunicam apenas por atributos `data-*` no DOM - nenhum lê o
 * estado interno do outro.
 */
const ESTREITO = '(max-width: 1024px)';

document.addEventListener('alpine:init', () => {
  window.Alpine.data('mapaPainel', () => ({
    esq: true,
    dir: true,
    abaEsq: 'filtros',
    // abre na mesma camada que o mapa acende por padrão
    abaDir: 'area_queimada',

    get estreito() {
      return window.matchMedia(ESTREITO).matches;
    },

    init() {
      // em tela estreita cada painel cobre a largura toda; abrir os dois de saída
      // esconderia o mapa inteiro logo na chegada
      if (this.estreito) {
        this.esq = false;
        this.dir = false;
      }
    },

    alternar(lado) {
      this[lado] = !this[lado];
      if (this.estreito && this[lado]) {
        this[lado === 'esq' ? 'dir' : 'esq'] = false;
      }
    },

    fecharTudo() {
      this.esq = false;
      this.dir = false;
    },
  }));
});
