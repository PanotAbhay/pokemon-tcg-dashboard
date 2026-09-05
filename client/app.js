const API_BASE = window.location.origin.startsWith('http')
  ? `${window.location.origin}/api`
  : 'http://127.0.0.1:5000/api';

const state = {
  filters: {
    q: '',
    supertype: [],
    series: [],
    set: [],
    rarity: [],
    artist: [],
    year_from: '',
    year_to: '',
  },
  sort_by: 'release_date',
  order: 'desc',
  page: 1,
  page_size: 24,
};

let debounceTimer = null;

const charts = {};

// ---------- Utilities ----------

function qs(params) {
  const usp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (Array.isArray(v)) {
      v.forEach((item) => usp.append(k, item));
    } else if (v !== '' && v !== null && v !== undefined) {
      usp.set(k, v);
    }
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

// ---------- Multi-select dropdown ----------

function createMultiSelect(rootId) {
  const root = document.getElementById(rootId);
  const trigger = root.querySelector('.ms-trigger');
  const panel = root.querySelector('.ms-panel');
  let options = []; // [{ value, label }]
  let selected = new Set();
  let onChangeCb = () => {};

  function render() {
    panel.innerHTML = '';
    if (options.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'ms-empty';
      empty.textContent = 'No options';
      panel.appendChild(empty);
      return;
    }
    options.forEach(({ value, label }) => {
      const row = document.createElement('label');
      row.className = 'ms-option';
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.value = value;
      cb.checked = selected.has(value);
      cb.addEventListener('change', () => {
        if (cb.checked) selected.add(value);
        else selected.delete(value);
        updateTrigger();
        onChangeCb();
      });
      const span = document.createElement('span');
      span.textContent = label;
      row.appendChild(cb);
      row.appendChild(span);
      panel.appendChild(row);
    });
  }

  function updateTrigger() {
    const n = selected.size;
    if (n === 0) {
      trigger.textContent = 'All';
    } else if (n === 1) {
      const only = options.find((o) => selected.has(o.value));
      trigger.textContent = only ? only.label : '1 selected';
    } else {
      trigger.textContent = `${n} selected`;
    }
    trigger.classList.toggle('active', n > 0);
  }

  trigger.addEventListener('click', (e) => {
    e.stopPropagation();
    document.querySelectorAll('.ms-panel').forEach((p) => {
      if (p !== panel) p.classList.add('hidden');
    });
    panel.classList.toggle('hidden');
  });

  document.addEventListener('click', (e) => {
    if (!root.contains(e.target)) panel.classList.add('hidden');
  });

  return {
    setOptions(newOptions) {
      const validValues = new Set(newOptions.map((o) => o.value));
      selected = new Set([...selected].filter((v) => validValues.has(v)));
      options = newOptions;
      render();
      updateTrigger();
    },
    getSelected: () => [...selected],
    clear() {
      selected = new Set();
      render();
      updateTrigger();
    },
    onChange(cb) {
      onChangeCb = cb;
    },
  };
}

// ---------- Chart color palette (matches CSS design tokens) ----------

const CHART_COLORS = {
  red: '#E63946',
  teal: '#457B9D',
  frosted: '#A8DADC',
  gold: '#FFB703',
  cream: '#F1FAEE',
  dim: 'rgba(241, 250, 238, 0.5)',
  grid: 'rgba(241, 250, 238, 0.08)',
};

// Validated categorical palette (dataviz skill reference palette, dark steps),
// re-checked against this app's --ink surface (#1D3557) — CVD-safe adjacent
// ordering, do not reorder or regenerate hues at runtime.
const CATEGORICAL_PALETTE = [
  '#3987e5', // blue
  '#d95926', // orange
  '#199e70', // aqua
  '#c98500', // yellow
  '#d55181', // magenta
  '#008300', // green
  '#9085e9', // violet
  '#e66767', // red
];

function categoricalColor(index, alpha = 1) {
  const hex = CATEGORICAL_PALETTE[index % CATEGORICAL_PALETTE.length];
  if (alpha === 1) return hex;
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

const TYPE_COLOR_MAP = {
  Fire: categoricalColor(7),
  Water: categoricalColor(0),
  Grass: categoricalColor(2),
  Lightning: categoricalColor(3),
  Fighting: categoricalColor(1),
  Psychic: categoricalColor(6),
  Darkness: CHART_COLORS.dim,
  Metal: categoricalColor(4),
  Dragon: categoricalColor(0, 0.6),
  Fairy: categoricalColor(4, 0.6),
  Colorless: CHART_COLORS.cream,
};

// ---------- Rarity chart helpers ----------

// Pixel span of one horizontal bar's actual rendered length (not the whole chart
// width) — needed so a gradient painted on a short bar isn't just its leftmost sliver.
function barPixelRange(chart, dataIndex) {
  const scale = chart.scales.x;
  const value = chart.data.datasets[0].data[dataIndex];
  return [scale.getPixelForValue(0), scale.getPixelForValue(value)];
}

function makeGradient(chart, dataIndex, colorStops, fallback) {
  const { ctx, chartArea } = chart;
  if (!chartArea) return fallback;
  const [x0, x1] = barPixelRange(chart, dataIndex);
  const gradient = ctx.createLinearGradient(x0, 0, x1, 0);
  colorStops.forEach((color, i, arr) => {
    gradient.addColorStop(i / (arr.length - 1), color);
  });
  return gradient;
}

const RAINBOW_STOPS = ['#FF0000', '#FF9900', '#FFEE00', '#33CC33', '#3388FF', '#6633CC', '#CC33CC'];
const CHROME_STOPS = ['#5B6470', '#E8ECF0', '#FFFFFF', '#AEB6BF', '#8A94A0', '#F4F6F8'];

// Special-styled bars, keyed by rarity value; anything else falls back to categoricalColor().
const RARITY_BAR_STYLE = {
  'Rainbow Rare': (chart, i) => makeGradient(chart, i, RAINBOW_STOPS, CHART_COLORS.red),
  'Secret Rare': (chart, i) => makeGradient(chart, i, CHROME_STOPS, CHART_COLORS.frosted),
};

function rarityBarColor(context, rarities) {
  const rarity = rarities[context.dataIndex].rarity;
  const styleFn = RARITY_BAR_STYLE[rarity];
  return styleFn ? styleFn(context.chart, context.dataIndex) : categoricalColor(context.dataIndex);
}

Chart.defaults.color = CHART_COLORS.dim;
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.font.size = 11.5;

// Shared axis/legend shapes reused across the count-based charts below.
function countAxis() {
  return { grid: { color: CHART_COLORS.grid }, ticks: { callback: (v) => numberFmt.format(v) } };
}

function hiddenGridAxis() {
  return { grid: { display: false } };
}

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
          backgroundColor: (context) => rarityBarColor(context, top),
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
        x: countAxis(),
        y: { ...hiddenGridAxis(), ticks: { autoSkip: false } },
      },
    },
  });
}

async function loadTypeChart() {
  const data = await fetchJSON(`${API_BASE}/stats/by-type`);
  const ctx = document.getElementById('chart-type');
  charts.type = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map((d) => d.primary_type),
      datasets: [
        {
          label: 'Card count',
          data: data.map((d) => d.card_count),
          backgroundColor: data.map((d) => TYPE_COLOR_MAP[d.primary_type] || CHART_COLORS.dim),
          borderRadius: 3,
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
            label: (ctx) => `${numberFmt.format(ctx.parsed.y)} cards`,
          },
        },
      },
      scales: {
        x: hiddenGridAxis(),
        y: countAxis(),
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
        x: hiddenGridAxis(),
        y: countAxis(),
      },
    },
  });
}

async function loadArtistChart() {
  const data = await fetchJSON(`${API_BASE}/stats/artist-rarity?limit=-1`);
  document.getElementById('chart-artist-wrap').style.height = `${Math.max(620, data.length * 16)}px`;
  const ctx = document.getElementById('chart-artist');
  charts.artist = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map((d) => d.artist),
      datasets: [
        {
          label: 'Secret-rare rate (%)',
          data: data.map((d) => d.chase_pct),
          backgroundColor: data.map((d, i) => categoricalColor(i, 0.85)),
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
            label: (ctx) => {
              const d = data[ctx.dataIndex];
              return `${d.chase_pct}% — ${d.chase_count} of ${d.card_count} cards were secret rare`;
            },
          },
        },
      },
      scales: {
        x: { ...countAxis(), min: 0, ticks: { callback: (v) => `${v}%` } },
        y: { ...hiddenGridAxis(), ticks: { autoSkip: false } },
      },
    },
  });
}

async function loadRarityByYearChart() {
  const data = await fetchJSON(`${API_BASE}/stats/rarity-by-year`);
  const ctx = document.getElementById('chart-rarity-year');
  charts.rarityYear = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.years,
      datasets: data.rarities.map((rarity, i) => ({
        label: rarity,
        data: data.series[rarity],
        borderColor: categoricalColor(i),
        backgroundColor: categoricalColor(i, 0.85),
        fill: 'stack',
        tension: 0.2,
        pointRadius: 0,
        borderWidth: 1,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'bottom',
          labels: { boxWidth: 10, padding: 8, font: { size: 10.5 } },
        },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y}%`,
          },
        },
      },
      scales: {
        x: hiddenGridAxis(),
        y: {
          ...countAxis(),
          stacked: true,
          min: 0,
          max: 100,
          ticks: { callback: (v) => `${v}%` },
        },
      },
    },
  });
}

// ---------- Filters ----------

const multiSelects = {};
let allSets = [];
let seriesSetsMap = {};

function toOptions(values, labelFn = (v) => v) {
  return values.map((v) => ({ value: v, label: labelFn(v) }));
}

// Options available in the Set filter, given whichever series are currently selected.
function setOptionsForSelectedSeries() {
  const selectedSeries = multiSelects.series.getSelected();
  if (selectedSeries.length === 0) return toOptions(allSets);
  const union = new Set();
  selectedSeries.forEach((s) => (seriesSetsMap[s] || []).forEach((set) => union.add(set)));
  return toOptions([...union].sort());
}

async function loadFilterOptions() {
  const data = await fetchJSON(`${API_BASE}/filters`);
  allSets = data.sets;
  seriesSetsMap = data.series_sets;

  multiSelects.supertype = createMultiSelect('ms-supertype');
  multiSelects.series = createMultiSelect('ms-series');
  multiSelects.set = createMultiSelect('ms-set');
  multiSelects.rarity = createMultiSelect('ms-rarity');
  multiSelects.artist = createMultiSelect('ms-artist');

  multiSelects.supertype.setOptions(toOptions(data.supertypes));
  multiSelects.series.setOptions(toOptions(data.series));
  multiSelects.set.setOptions(toOptions(allSets));
  multiSelects.rarity.setOptions(toOptions(data.rarities));
  multiSelects.artist.setOptions(toOptions(data.artists));

  // Selecting a series narrows the Set dropdown to only sets within that series.
  multiSelects.series.onChange(() => {
    multiSelects.set.setOptions(setOptionsForSelectedSeries());
    onFilterChange();
  });

  Object.entries(multiSelects).forEach(([key, ms]) => {
    if (key === 'series') return; // already wired above with the extra set-narrowing step
    ms.onChange(onFilterChange);
  });

  document.getElementById('f-year-from').placeholder = `From (${data.year_min})`;
  document.getElementById('f-year-to').placeholder = `To (${data.year_max})`;
}

function readFiltersFromForm() {
  state.filters.q = document.getElementById('f-search').value.trim();
  state.filters.supertype = multiSelects.supertype.getSelected();
  state.filters.series = multiSelects.series.getSelected();
  state.filters.set = multiSelects.set.getSelected();
  state.filters.rarity = multiSelects.rarity.getSelected();
  state.filters.artist = multiSelects.artist.getSelected();
  state.filters.year_from = document.getElementById('f-year-from').value;
  state.filters.year_to = document.getElementById('f-year-to').value;
}

function clearFilters() {
  document.getElementById('f-search').value = '';
  Object.values(multiSelects).forEach((ms) => ms.clear());
  multiSelects.set.setOptions(toOptions(allSets));
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
    el.tabIndex = 0;
    el.setAttribute('role', 'button');
    el.setAttribute('aria-expanded', 'false');

    // Tier 1 (always visible): name, rarity, set.
    const tier1 = document.createElement('div');
    tier1.className = 'card-tier card-tier-1';

    const name = document.createElement('span');
    name.className = 'card-name';
    name.textContent = card.name;
    tier1.appendChild(name);

    const rarityTag = document.createElement('span');
    rarityTag.className = 'tag rarity';
    rarityTag.textContent = card.rarity;
    tier1.appendChild(rarityTag);

    const setLine = document.createElement('div');
    setLine.className = 'card-set';
    setLine.textContent = card.set_number ? `${card.set} · ${card.set_number}` : card.set;
    tier1.appendChild(setLine);

    el.appendChild(tier1);

    // Tier 2 (hover, or expanded): series + release date.
    const tier2 = document.createElement('div');
    tier2.className = 'card-tier card-tier-2';
    tier2.textContent = `${card.series} · ${card.release_date}`;
    el.appendChild(tier2);

    // Tier 3 (click to expand): everything else.
    const tier3 = document.createElement('div');
    tier3.className = 'card-tier card-tier-3';

    const img = document.createElement('img');
    img.className = 'card-art';
    img.loading = 'lazy';
    img.alt = card.name;
    const dashIndex = card.id.lastIndexOf('-');
    img.src = `https://images.pokemontcg.io/${card.id.slice(0, dashIndex)}/${card.id.slice(dashIndex + 1)}.png`;
    img.onerror = () => img.remove();
    tier3.appendChild(img);

    const tags = document.createElement('div');
    tags.className = 'card-tags';

    if (card.hp !== null && card.hp !== undefined) {
      const hp = document.createElement('span');
      hp.className = 'tag hp';
      hp.textContent = `${Math.round(card.hp)} HP`;
      tags.appendChild(hp);
    }

    if (card.primary_type) {
      const typeTag = document.createElement('span');
      typeTag.className = 'tag type';
      typeTag.textContent = card.types_display || card.primary_type;
      tags.appendChild(typeTag);
    }

    const supertypeTag = document.createElement('span');
    supertypeTag.className = 'tag';
    supertypeTag.textContent = card.supertype;
    tags.appendChild(supertypeTag);

    if (card.retreat_cost !== null && card.retreat_cost !== undefined) {
      const retreatTag = document.createElement('span');
      retreatTag.className = 'tag';
      retreatTag.textContent = `Retreat: ${Math.round(card.retreat_cost)}`;
      tags.appendChild(retreatTag);
    }

    tier3.appendChild(tags);

    const details = document.createElement('div');
    details.className = 'card-details';

    const genLine = document.createElement('span');
    genLine.textContent = `Generation: ${card.generation ?? '—'}`;
    details.appendChild(genLine);

    const artistLine = document.createElement('span');
    artistLine.textContent = `Artist: ${card.artist ?? 'Unknown'}`;
    details.appendChild(artistLine);

    tier3.appendChild(details);

    el.appendChild(tier3);

    el.addEventListener('click', () => {
      const willExpand = !el.classList.contains('expanded');
      grid.querySelectorAll('.card-pocket.expanded').forEach((other) => {
        if (other !== el) {
          other.classList.remove('expanded');
          other.setAttribute('aria-expanded', 'false');
        }
      });
      el.classList.toggle('expanded', willExpand);
      el.setAttribute('aria-expanded', String(willExpand));
    });
    el.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        el.click();
      }
    });

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
    ...state.filters,
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

// ---------- Tabs ----------

let statsLoaded = false;

function switchTab(tab) {
  document.getElementById('tab-search').classList.toggle('hidden', tab !== 'search');
  document.getElementById('tab-stats').classList.toggle('hidden', tab !== 'stats');
  document.getElementById('nav-search').classList.toggle('active', tab === 'search');
  document.getElementById('nav-stats').classList.toggle('active', tab === 'stats');

  if (tab === 'stats' && !statsLoaded) {
    statsLoaded = true;
    Promise.allSettled([
      loadOverview(),
      loadRarityChart(),
      loadTypeChart(),
      loadYearChart(),
      loadArtistChart(),
      loadRarityByYearChart(),
    ]);
  }
}

function wireTabs() {
  document.getElementById('nav-search').addEventListener('click', () => switchTab('search'));
  document.getElementById('nav-stats').addEventListener('click', () => switchTab('stats'));
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

  document.getElementById('page-prev').addEventListener('click', () => changePage(-1));
  document.getElementById('page-next').addEventListener('click', () => changePage(1));
}

function changePage(delta) {
  if (state.page + delta < 1) return;
  state.page += delta;
  loadCards();
  window.scrollTo({ top: document.querySelector('.binder').offsetTop - 80, behavior: 'smooth' });
}

// ---------- Init ----------

async function init() {
  wireTabs();
  wireEvents();

  // Connection-status dot only; don't block tab/filter/card loading on it.
  fetchJSON(`${API_BASE}/health`)
    .then(() => setConnStatus('ok', 'Connected'))
    .catch(() => setConnStatus('error', 'Disconnected'));

  switchTab('stats');

  await loadFilterOptions();
  loadCards();
}

init();
