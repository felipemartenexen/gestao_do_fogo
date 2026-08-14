import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.markercluster';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import './map.css';

// enquadramento inicial: Brasil inteiro
const BRAZIL_CENTER = [-14.5, -52.0];
const BRAZIL_ZOOM = 4;

// O Leaflet resolve os ícones padrão por caminho relativo, o que quebra sob bundling
// (vira /static/node_modules/...). Usamos um marcador próprio em SVG: sem arquivo de
// imagem para servir e combina com a paleta do site.
const markerIcon = L.divIcon({
  className: 'researcher-marker',
  html: `<svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">
           <path fill="currentColor" stroke="white" stroke-width="1.2"
                 d="M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7z"/>
           <circle cx="12" cy="9" r="2.6" fill="white"/>
         </svg>`,
  iconSize: [26, 26],
  iconAnchor: [13, 26],
  popupAnchor: [0, -24],
});

function escapeHtml(value) {
  const div = document.createElement('div');
  div.textContent = value == null ? '' : String(value);
  return div.innerHTML;
}

function buildPopup(point) {
  const parts = [`<strong class="block text-base">${escapeHtml(point.name)}</strong>`];
  if (point.institution) {
    parts.push(`<span class="block text-sm opacity-80">${escapeHtml(point.institution)}</span>`);
  }
  if (point.location) {
    parts.push(`<span class="block text-xs opacity-60 mt-1">${escapeHtml(point.location)}</span>`);
  }
  parts.push(`<a class="link link-primary text-sm mt-2 inline-block" href="${escapeHtml(point.url)}">Ver perfil →</a>`);
  return `<div class="min-w-[12rem]">${parts.join('')}</div>`;
}

export function initResearcherMap(container) {
  const dataUrl = container.dataset.url;
  const statusEl = document.getElementById('map-status');

  const map = L.map(container, { scrollWheelZoom: false }).setView(BRAZIL_CENTER, BRAZIL_ZOOM);
  // clicar habilita a roda do mouse: evita capturar o scroll da página sem querer
  map.on('click', () => map.scrollWheelZoom.enable());
  map.on('mouseout', () => map.scrollWheelZoom.disable());

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(map);

  const clusters = L.markerClusterGroup({
    showCoverageOnHover: false,
    maxClusterRadius: 45,
    spiderfyDistanceMultiplier: 1.6,
  });

  fetch(dataUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
    .then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then((data) => {
      const points = data.points || [];
      points.forEach((point) => {
        L.marker([point.lat, point.lon], { title: point.name, icon: markerIcon })
          .bindPopup(buildPopup(point))
          .addTo(clusters);
      });
      map.addLayer(clusters);

      // Enquadra TODOS os pontos, inclusive os do exterior: a rede tem pesquisadores
      // fora do Brasil e eles precisam aparecer no enquadramento inicial.
      if (points.length) {
        map.fitBounds(L.latLngBounds(points.map((p) => [p.lat, p.lon])), {
          padding: [40, 40],
          maxZoom: 9,
        });
      }
      if (statusEl) {
        const by = data.mode === 'moradia' ? 'pela cidade onde moram' : 'pelo município da instituição';
        statusEl.textContent = points.length
          ? `${points.length} pesquisadores no mapa, posicionados ${by}`
          : 'Nenhum pesquisador com localização para os filtros atuais';
      }
    })
    .catch((error) => {
      if (statusEl) statusEl.textContent = 'Não foi possível carregar os pontos do mapa.';
      console.error('researchers map:', error);
    });

  return map;
}

document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('researchers-map');
  if (container) initResearcherMap(container);
});
