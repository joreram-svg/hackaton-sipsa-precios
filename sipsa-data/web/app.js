const state = { products: [] };

const byId = (id) => document.getElementById(id);
const money = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });
const percent = new Intl.NumberFormat('es-CO', { style: 'percent', maximumFractionDigits: 1 });

async function requestJson(url) {
  const response = await fetch(url);
  const payload = await response.json();
  if (!response.ok || payload.error) {
    const error = payload.error || { code: 'UPSTREAM_DOWN', message: 'No fue posible cargar los datos.' };
    throw new Error(`${error.code}: ${error.message}`);
  }
  return payload;
}

function showError(error) {
  byId('error').textContent = error.message;
  byId('error').hidden = false;
}

function clearError() { byId('error').hidden = true; }

function priceCard(item) {
  const card = document.createElement('article');
  card.className = 'price-card';
  const title = document.createElement('h3');
  title.textContent = item.nombre;
  const price = document.createElement('p');
  price.className = 'price';
  price.textContent = money.format(item.precio_actual);
  const reason = document.createElement('p');
  reason.className = 'reason';
  reason.textContent = item.razon;
  card.append(title, price, reason);
  return card;
}

function renderCards(target, items) {
  target.replaceChildren(...items.map(priceCard));
}

function renderAlerts(items) {
  const body = byId('alerts-body');
  const empty = byId('alerts-empty');
  body.replaceChildren();
  empty.hidden = items.length > 0;
  for (const item of items) {
    const row = document.createElement('tr');
    const values = [item.nombre, item.direccion, percent.format(item.var_pct), money.format(item.precio_actual)];
    values.forEach((value, index) => {
      const cell = document.createElement('td');
      cell.textContent = value;
      if (index === 1) cell.className = item.direccion === 'SUBE' ? 'direction--up' : 'direction--down';
      row.append(cell);
    });
    body.append(row);
  }
}

async function loadSummary() {
  clearError();
  const params = new URLSearchParams({ ciudad: byId('city').value, perfil: byId('profile').value });
  try {
    const data = await requestJson(`/v1/resumen-semanal?${params}`);
    byId('summary-text').textContent = data.texto;
    renderCards(byId('buy-list'), data.top_comprar);
    renderCards(byId('avoid-list'), data.top_evitar);
    renderAlerts(data.alertas);
  } catch (error) { showError(error); }
}

function drawSparkline(series) {
  const svg = byId('sparkline');
  const values = series.map((item) => Number(item.precio));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const points = values.map((value, index) => {
    const x = 10 + index * (460 / Math.max(values.length - 1, 1));
    const y = 135 - ((value - min) / span) * 120;
    return `${x},${y}`;
  });
  const ns = 'http://www.w3.org/2000/svg';
  const area = document.createElementNS(ns, 'polygon');
  area.setAttribute('class', 'sparkline-area');
  area.setAttribute('points', `10,145 ${points.join(' ')} 470,145`);
  const line = document.createElementNS(ns, 'polyline');
  line.setAttribute('class', 'sparkline-line');
  line.setAttribute('points', points.join(' '));
  svg.replaceChildren(area, line);
}

async function loadTrend(event) {
  event.preventDefault();
  clearError();
  const query = byId('product-search').value.trim().toLocaleLowerCase('es');
  const product = state.products.find((item) =>
    item.producto_id.toLocaleLowerCase('es') === query || item.nombre.toLocaleLowerCase('es') === query
  );
  if (!product) { showError(new Error('NOT_FOUND: Seleccione un producto de la lista.')); return; }
  const params = new URLSearchParams({ ciudad: byId('city').value, semanas: '12' });
  try {
    const data = await requestJson(`/v1/tendencia/${encodeURIComponent(product.producto_id)}?${params}`);
    byId('trend-name').textContent = product.nombre;
    byId('trend-change').textContent = `Última semana: ${percent.format(data.var_1w_pct || 0)}`;
    drawSparkline(data.serie);
    byId('trend-result').hidden = false;
  } catch (error) { showError(error); }
}

async function initialize() {
  try {
    const [cities, products] = await Promise.all([requestJson('/v1/ciudades'), requestJson('/v1/productos')]);
    byId('city').replaceChildren(...cities.map(({ ciudad }) => new Option(ciudad, ciudad, ciudad === 'Bogotá', ciudad === 'Bogotá')));
    state.products = products;
    byId('products').replaceChildren(...products.map((item) => {
      const option = document.createElement('option'); option.value = item.nombre; return option;
    }));
    await loadSummary();
  } catch (error) { showError(error); }
}

byId('city').addEventListener('change', loadSummary);
byId('profile').addEventListener('change', loadSummary);
byId('trend-form').addEventListener('submit', loadTrend);
initialize();
