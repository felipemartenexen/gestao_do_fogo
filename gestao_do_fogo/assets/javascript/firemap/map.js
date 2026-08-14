import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './map.css';
import './painel.js';
import { Controles } from './filtros.js';
import { Estatisticas } from './estatisticas.js';

const BRAZIL_CENTER = [-14.5, -52.0];
const BRAZIL_ZOOM = 4;

/**
 * Mapa do fogo: um mapa base + N camadas raster vindas do Earth Engine.
 *
 * Cada camada acesa busca sua URL de tiles no backend levando o recorte territorial e o
 * seu próprio período. O empilhamento e a opacidade vêm do backend (catalog.Layer), para
 * que a ordem das camadas seja decidida num lugar só.
 */
class FireMap {
  constructor(root) {
    this.root = root;
    // o Django gera a rota com um id fictício; trocamos pelo id real na hora de chamar
    this.tilesUrlTemplate = root.dataset.tilesUrl;
    this.layers = new Map(); // id -> L.TileLayer
    this.requests = new Map(); // id -> AbortController
    this.cores = new Map(); // id -> cor da legenda flutuante
    this.pendentes = 0;
    this.progresso = root.querySelector('#mapa-progresso');
    this.legenda = root.querySelector('[data-legenda]');

    this.map = this.buildMap();
    this.controles = new Controles(root, {
      aoMudarTerritorio: () => {
        this.reloadActiveLayers();
        this.estatisticas.atualizar();
      },
      aoMudarPeriodo: (camadas) => {
        this.reloadActiveLayers(camadas);
        this.estatisticas.atualizar(camadas);
      },
    });
    this.estatisticas = new Estatisticas(root, this.controles);
    this.bindLayerToggles();
    this.lerCoresDaLegenda();
    this.restoreDefaultLayer();
    this.estatisticas.atualizar();
  }

  buildMap() {
    const map = L.map(this.root.querySelector('#firemap-canvas'), {
      center: BRAZIL_CENTER,
      zoom: BRAZIL_ZOOM,
      // a página não rola mais (tela cheia), então a roda pode ser do mapa sem sequestrar nada
      scrollWheelZoom: true,
      zoomControl: true,
    });
    L.control.scale({ imperial: false, position: 'bottomleft' }).addTo(map);

    this.basemaps = {
      claro: L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        maxZoom: 19,
        zIndex: 0,
        attribution: '&copy; OpenStreetMap &copy; CARTO',
      }),
      satelite: L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        { maxZoom: 19, zIndex: 0, attribution: 'Esri, Maxar, Earthstar Geographics' },
      ),
    };
    this.basemaps.claro.addTo(map);
    this.currentBasemap = 'claro';

    this.root.querySelectorAll('[data-basemap]').forEach((button) => {
      button.addEventListener('click', () => this.setBasemap(button.dataset.basemap));
    });
    return map;
  }

  setBasemap(name) {
    if (!this.basemaps[name] || name === this.currentBasemap) return;
    this.map.removeLayer(this.basemaps[this.currentBasemap]);
    // o zIndex 0 do mapa base contra o das camadas já garante a ordem: não é preciso
    // reordenar nada na mão depois da troca
    this.basemaps[name].addTo(this.map);
    this.currentBasemap = name;
    this.root.querySelectorAll('[data-basemap]').forEach((b) => {
      const ativo = b.dataset.basemap === name;
      b.classList.toggle('is-ativo', ativo);
      b.setAttribute('aria-checked', ativo ? 'true' : 'false');
    });
  }

  // --- barra de progresso ------------------------------------------------------

  beginRequest() {
    this.pendentes += 1;
    if (this.progresso) this.progresso.hidden = false;
  }

  endRequest() {
    this.pendentes = Math.max(0, this.pendentes - 1);
    if (this.progresso && this.pendentes === 0) this.progresso.hidden = true;
  }

  // --- camadas ---------------------------------------------------------------

  bindLayerToggles() {
    this.root.querySelectorAll('[data-layer]').forEach((input) => {
      input.addEventListener('change', () => {
        const id = input.dataset.layer;
        // período e legenda só fazem sentido na camada ligada
        this.root.querySelector(`[data-corpo="${id}"]`)?.toggleAttribute('hidden', !input.checked);
        if (input.checked) this.showLayer(id);
        else this.hideLayer(id);
        this.controles.atualizarRecorte();
      });
      this.root.querySelector(`[data-corpo="${input.dataset.layer}"]`)?.toggleAttribute('hidden', !input.checked);
    });
  }

  /** Guarda a cor de cada camada, lida do próprio swatch da legenda do painel. */
  lerCoresDaLegenda() {
    this.root.querySelectorAll('[data-camada]').forEach((bloco) => {
      const swatch = bloco.querySelector('.mapa-swatch');
      if (swatch) this.cores.set(bloco.dataset.camada, getComputedStyle(swatch).backgroundColor);
    });
  }

  restoreDefaultLayer() {
    this.root.querySelectorAll('[data-layer]:checked').forEach((input) => this.showLayer(input.dataset.layer));
  }

  setStatus(layerId, state, message = '') {
    const el = this.root.querySelector(`[data-layer-status="${layerId}"]`);
    if (!el) return;
    el.dataset.state = state;
    el.textContent = message;
  }

  async showLayer(layerId) {
    // cancela um carregamento anterior da mesma camada (troca rápida de período)
    this.requests.get(layerId)?.abort();
    const controller = new AbortController();
    this.requests.set(layerId, controller);

    this.setStatus(layerId, 'loading', 'carregando…');
    this.beginRequest();
    try {
      const url = `${this.tilesUrlTemplate.replace('PLACEHOLDER', layerId)}?${this.controles.parametros(layerId)}`;
      const response = await fetch(url, { signal: controller.signal });
      const data = await response.json();
      if (response.status === 409 && data.pending) {
        // camada catalogada mas ainda sem asset: não é erro, é dado que falta
        this.setStatus(layerId, 'pending', data.error);
        return;
      }
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);

      this.hideLayer(layerId, { keepStatus: true });
      const tileLayer = L.tileLayer(data.url, {
        opacity: data.opacity ?? 0.85,
        attribution: data.attribution,
        zIndex: data.zIndex ?? 20,
      });
      tileLayer.addTo(this.map);
      this.layers.set(layerId, tileLayer);
      this.setStatus(layerId, 'ok', '');
      this.fitTo(data.bounds);
    } catch (error) {
      if (error.name === 'AbortError') return;
      this.setStatus(layerId, 'error', error.message);
      console.error('firemap: camada', layerId, error);
    } finally {
      this.endRequest();
      this.atualizarLegenda();
    }
  }

  /**
   * Enquadra o território filtrado.
   *
   * `undefined` é "não sei" e `null` é "esta camada ignora o recorte" - um contorno não
   * pode desfazer o zoom do usuário. Fora isso, só reenquadra quando o recorte muda de
   * verdade: sem isso, ligar uma segunda camada jogaria o mapa de volta para o extent.
   */
  fitTo(bounds) {
    if (bounds === null || bounds === undefined) return;
    const key = JSON.stringify(bounds);
    if (key === this.lastBoundsKey) return;
    this.lastBoundsKey = key;
    this.map.fitBounds(bounds, { padding: [24, 24] });
  }

  hideLayer(layerId, { keepStatus = false } = {}) {
    const layer = this.layers.get(layerId);
    if (layer) {
      this.map.removeLayer(layer);
      this.layers.delete(layerId);
    }
    if (!keepStatus) {
      this.setStatus(layerId, 'off', '');
      this.atualizarLegenda();
    }
  }

  /** Legenda sobre o mapa: com um ano por camada, um print precisa se explicar sozinho. */
  atualizarLegenda() {
    if (!this.legenda) return;
    const anos = this.controles.anos;
    const linhas = [...this.layers.keys()].map((id) => {
      const nome = this.root.querySelector(`[data-camada="${id}"] .mapa-camada-nome`)?.textContent.trim() ?? id;
      const ano = anos[id] ? ` <b class="tabular">${anos[id]}</b>` : '';
      const cor = this.cores.get(id) ?? 'currentColor';
      return `<li><i style="background:${cor}"></i><span>${nome}${ano}</span></li>`;
    });
    this.legenda.innerHTML = linhas.length ? `<ul>${linhas.join('')}</ul>` : '';
    this.legenda.hidden = linhas.length === 0;
  }

  reloadActiveLayers(apenas = null) {
    this.root.querySelectorAll('[data-layer]:checked').forEach((input) => {
      const id = input.dataset.layer;
      if (apenas && !apenas.includes(id)) return;
      this.showLayer(id);
    });
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('firemap');
  if (root) new FireMap(root);
});
