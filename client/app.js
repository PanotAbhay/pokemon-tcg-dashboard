const API_BASE = window.location.origin.startsWith('http')
  ? `${window.location.origin}/api`
  : 'http://127.0.0.1:5000/api';

const state = {
  filters: {
    q: '',
    supertype: '',
    series: '',
    set: '',
    rarity: '',
    type: '',
    year_from: '',
    year_to: '',
  },
  sort_by: 'name',
  order: 'asc',
  page: 1,
  page_size: 24,
};

let debounceTimer = null;

const charts = {};

// ---------- Utilities ----------

function qs(params) {
  const usp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== '' && v !== null && v !== undefined) usp.set(k, v);
  });
  return usp.toString();
}

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `Request failed: ${res.status}`);
  }
  return res.json();
}

function setConnStatus(status, label) {
  const el = document.getElementById('conn-status');
  el.classList.remove('ok', 'error');
  if (status) el.classList.add(status);
  el.querySelector('.conn-label').textContent = label;
}

const numberFmt = new Intl.NumberFormat('en-GB');

// ---------- Chart color palette (matches CSS design tokens) ----------

const CHART_COLORS = {
  red: '#E63946',
  teal: '#2A9D8F',
  gold: '#FFB703',
  cream: '#F5F1E8',
  dim: 'rgba(245, 241, 232, 0.5)',
  grid: 'rgba(245, 241, 232, 0.08)',
};

const TYPE_COLOR_MAP = {
  Fire: '#E63946',
  Water: '#2A9D8F',
  Grass: '#6BBF59',
  Lightning: '#FFB703',
  Psychic: '#B388EB',
  Fighting: '#C97A4A',
  Darkness: '#5C5470',
  Metal: '#9AA5B1',
  Dragon: '#F4845F',
  Fairy: '#F2A6D8',
  Colorless: '#D9D2C1',
};

Chart.defaults.color = CHART_COLORS.dim;
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.font.size = 11.5;

// ---------- Overview stats ----------

async function loadOverview() {
  const data = await fetchJSON(`${API_BASE}/stats/overview`);
  document.getElementById('stat-total-cards').textContent = numberFmt.format(data.total_cards);
  document.getElementById('stat-total-sets').textContent = numberFmt.format(data.total_sets);
  document.getElementById('stat-total-series').textContent = numberFmt.format(data.total_series);
  document.getElementById('stat-total-artists').textContent = numberFmt.format(data.total_artists);
  document.getElementById('stat-years').textContent = `${data.year_min}–${data.year_max}`;
  document.getElementById('stat-avg-hp').textContent = data.avg_hp;
}

// ---------- Charts ----------

async function loadRarityChart() {
  const data = await fetchJSON(`${API_BASE}/stats/by-rarity`);
  const top = data.slice(0, 10);
  const ctx = document.getElementById('chart-rarity');
  charts.rarity = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: top.map((d) => d.rarity),
      datasets: [
        {
          label: 'Card count',
          data: top.map((d) => d.card_count),
          backgroundColor: CHART_COLORS.red,
          borderRadius: 3,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `${numberFmt.format(ctx.parsed.x)} cards`,
          },
        },
      },
      scales: {
        x: { grid: { color: CHART_COLORS.grid }, ticks: { callback: (v) => numberFmt.format(v) } },
        y: { grid: { display: false } },
      },
    },
  });
}

async function loadTypeChart() {
  const data = await fetchJSON(`${API_BASE}/stats/by-type`);
  const ctx = document.getElementById('chart-type');
  charts.type = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: data.map((d) => d.primary_type),
      datasets: [
        {
          data: data.map((d) => d.card_count),
          backgroundColor: data.map((d) => TYPE_COLOR_MAP[d.primary_type] || CHART_COLORS.dim),
          borderColor: '#22223B',
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'right',
          labels: { boxWidth: 10, padding: 10, font: { size: 11 } },
        },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.label}: ${numberFmt.format(ctx.parsed)} cards`,
          },
        },
      },
    },
  });
}

async function loadYearChart() {
  const data = await fetchJSON(`${API_BASE}/stats/by-year`);
  const ctx = document.getElementById('chart-year');
  charts.year = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.map((d) => d.release_year),
      datasets: [
        {
          label: 'Cards printed',
          data: data.map((d) => d.card_count),
          borderColor: CHART_COLORS.gold,
          backgroundColor: 'rgba(255, 183, 3, 0.12)',
          fill: true,
          tension: 0.25,
          pointRadius: 2,
          pointBackgroundColor: CHART_COLORS.gold,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `${numberFmt.format(ctx.parsed.y)} cards in ${ctx.label}`,
          },
        },
      },
      scales: {
        x: { grid: { display: false } },
        y: { grid: { color: CHART_COLORS.grid }, ticks: { callback: (v) => numberFmt.format(v) } },
      },
    },
  });
}

// ---------- Filters ----------

async function loadFilterOptions() {
  const data = await fetchJSON(`${API_BASE}/filters`);
  populateSelect('f-series', data.series);
  populateSelect('f-set', data.sets);
  populateSelect('f-rarity', data.rarities);
  populateSelect('f-type', data.types);
  populateSelect('f-supertype', data.supertypes);
  document.getElementById('f-year-from').placeholder = `From (${data.year_min})`;
  document.getElementById('f-year-to').placeholder = `To (${data.year_max})`;
}

function populateSelect(id, values) {
  const select = document.getElementById(id);
  values.forEach((v) => {
    const opt = document.createElement('option');
    opt.value = v;
    opt.textContent = v;
    select.appendChild(opt);
  });
}

function readFiltersFromForm() {
  state.filters.q = document.getElementById('f-search').value.trim();
  state.filters.supertype = document.getElementById('f-supertype').value;
  state.filters.series = document.getElementById('f-series').value;
  state.filters.set = document.getElementById('f-set').value;
  state.filters.rarity = document.getElementById('f-rarity').value;
  state.filters.type = document.getElementById('f-type').value;
  state.filters.year_from = document.getElementById('f-year-from').value;
  state.filters.year_to = document.getElementById('f-year-to').value;
}

function clearFilters() {
  document.getElementById('f-search').value = '';
  document.getElementById('f-supertype').value = '';
  document.getElementById('f-series').value = '';
  document.getElementById('f-set').value = '';
  document.getElementById('f-rarity').value = '';
  document.getElementById('f-type').value = '';
  document.getElementById('f-year-from').value = '';
  document.getElementById('f-year-to').value = '';
  state.page = 1;
  readFiltersFromForm();
  loadCards();
}

// ---------- Cards list ----------

function renderCardSkeletons(n = 12) {
  const grid = document.getElementById('pocket-grid');
  grid.innerHTML = '';
  for (let i = 0; i < n; i++) {
    const div = document.createElement('div');
    div.className = 'skeleton';
    grid.appendChild(div);
  }
}

function renderCards(cards) {
  const grid = document.getElementById('pocket-grid');
  grid.innerHTML = '';
  cards.forEach((card) => {
    const el = document.createElement('div');
    el.className = 'card-pocket';

    const top = document.createElement('div');
    top.className = 'card-pocket-top';

    const name = document.createElement('span');
    name.className = 'card-name';
    name.textContent = card.name;
    top.appendChild(name);

    if (card.hp !== null && card.hp !== undefined) {
      const hp = document.createElement('span');
      hp.className = 'card-hp';
      hp.textContent = `${Math.round(card.hp)} HP`;
      top.appendChild(hp);
    }

    el.appendChild(top);

    const meta = document.createElement('div');
    meta.className = 'card-meta';
    meta.textContent = `${card.set} · ${card.release_date}`;
    el.appendChild(meta);

    const tags = document.createElement('div');
    tags.className = 'card-tags';

    const rarityTag = document.createElement('span');
    rarityTag.className = 'tag rarity';
    rarityTag.textContent = card.rarity;
    tags.appendChild(rarityTag);

    if (card.primary_type) {
      const typeTag = document.createElement('span');
      typeTag.className = 'tag type';
      typeTag.textContent = card.primary_type;
      tags.appendChild(typeTag);
    }

    const supertypeTag = document.createElement('span');
    supertypeTag.className = 'tag';
    supertypeTag.textContent = card.supertype;
    tags.appendChild(supertypeTag);

    el.appendChild(tags);
    grid.appendChild(el);
  });
}

async function loadCards() {
  const grid = document.getElementById('pocket-grid');
  const empty = document.getElementById('pocket-empty');
  const errorBox = document.getElementById('pocket-error');
  const pagination = document.getElementById('pagination');

  empty.classList.add('hidden');
  errorBox.classList.add('hidden');
  pagination.classList.remove('hidden');
  renderCardSkeletons();

  const params = {
    q: state.filters.q,
    supertype: state.filters.supertype,
    series: state.filters.series,
    set: state.filters.set,
    rarity: state.filters.rarity,
    type: state.filters.type,
    year_from: state.filters.year_from,
    year_to: state.filters.year_to,
    sort_by: state.sort_by,
    order: state.order,
    page: state.page,
    page_size: state.page_size,
  };

  try {
    const data = await fetchJSON(`${API_BASE}/cards?${qs(params)}`);
    setConnStatus('ok', 'Connected');

    document.getElementById('result-count').textContent = `${numberFmt.format(data.total)} card${data.total === 1 ? '' : 's'}`;

    if (data.results.length === 0) {
      grid.innerHTML = '';
      pagination.classList.add('hidden');
      empty.classList.remove('hidden');
      return;
    }

    renderCards(data.results);

    document.getElementById('page-info').textContent = `Page ${data.page} of ${data.total_pages}`;
    document.getElementById('page-prev').disabled = data.page <= 1;
    document.getElementById('page-next').disabled = data.page >= data.total_pages;
  } catch (err) {
    grid.innerHTML = '';
    pagination.classList.add('hidden');
    errorBox.classList.remove('hidden');
    setConnStatus('error', 'Disconnected');
    console.error(err);
  }
}

// ---------- Event wiring ----------

function onFilterChange() {
  state.page = 1;
  readFiltersFromForm();
  loadCards();
}

function debouncedFilterChange() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(onFilterChange, 350);
}

function wireEvents() {
  document.getElementById('f-search').addEventListener('input', debouncedFilterChange);
  document.getElementById('f-supertype').addEventListener('change', onFilterChange);
  document.getElementById('f-series').addEventListener('change', onFilterChange);
  document.getElementById('f-set').addEventListener('change', onFilterChange);
  document.getElementById('f-rarity').addEventListener('change', onFilterChange);
  document.getElementById('f-type').addEventListener('change', onFilterChange);
  document.getElementById('f-year-from').addEventListener('input', debouncedFilterChange);
  document.getElementById('f-year-to').addEventListener('input', debouncedFilterChange);

  document.getElementById('f-clear').addEventListener('click', clearFilters);
  document.getElementById('empty-clear').addEventListener('click', clearFilters);

  document.getElementById('f-sort').addEventListener('change', (e) => {
    state.sort_by = e.target.value;
    state.page = 1;
    loadCards();
  });

  document.getElementById('f-order').addEventListener('click', (e) => {
    state.order = state.order === 'asc' ? 'desc' : 'asc';
    e.target.textContent = state.order === 'asc' ? '↑ Asc' : '↓ Desc';
    state.page = 1;
    loadCards();
  });

  document.getElementById('page-prev').addEventListener('click', () => {
    if (state.page > 1) {
      state.page -= 1;
      loadCards();
      window.scrollTo({ top: document.querySelector('.binder').offsetTop - 80, behavior: 'smooth' });
    }
  });

  document.getElementById('page-next').addEventListener('click', () => {
    state.page += 1;
    loadCards();
    window.scrollTo({ top: document.querySelector('.binder').offsetTop - 80, behavior: 'smooth' });
  });
}

// ---------- Init ----------

async function init() {
  wireEvents();
  try {
    await fetchJSON(`${API_BASE}/health`);
    setConnStatus('ok', 'Connected');
  } catch (err) {
    setConnStatus('error', 'Disconnected');
  }

  await Promise.allSettled([
    loadOverview(),
    loadRarityChart(),
    loadTypeChart(),
    loadYearChart(),
    loadFilterOptions(),
  ]);

  loadCards();
}

init();
