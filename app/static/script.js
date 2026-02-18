/**
 * Finance Strategy Engine - Frontend Logic
 */

function destroyIfExists(key) {
  if (window[key]) { window[key].destroy(); window[key] = null; }
}

function initDtiChart(obligations, freeCashflow) {
  const el = document.getElementById('dtiChart');
  if (!el) return;

  destroyIfExists("dtiChartInstance");
  const ctx = el.getContext('2d');

  window.dtiChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Obligations', 'Free Cashflow'],
      datasets: [{
        data: [obligations, freeCashflow],
        backgroundColor: ['#fb7185', '#34d399'],
        borderWidth: 0,
        borderRadius: 6,
        hoverOffset: 10
      }]
    },
    options: {
      cutout: '74%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: '#cbd5e1', padding: 16, font: { size: 12, weight: '600' } }
        },
        tooltip: {
          callbacks: { label: (ctx) => `${ctx.label}: $${Math.round(ctx.raw).toLocaleString()}` }
        }
      }
    }
  });
}

function initDebtBarChart(debtChart) {
  const el = document.getElementById('debtBarChart');
  if (!el) return;

  destroyIfExists("debtBarChartInstance");
  const ctx = el.getContext('2d');

  const labels = debtChart.map(d => d.name);
  const data = debtChart.map(d => d.balance);

  window.debtBarChartInstance = new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets: [{ label: 'Balance', data, borderWidth: 0, borderRadius: 10 }] },
    options: {
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (ctx) => `$${Math.round(ctx.raw).toLocaleString()}` } }
      },
      scales: {
        x: { ticks: { color: '#cbd5e1', font: { weight: '600' } }, grid: { color: 'rgba(148,163,184,0.10)' } },
        y: { ticks: { color: '#cbd5e1' }, grid: { color: 'rgba(148,163,184,0.10)' } }
      }
    }
  });
}

function initPayoffCompareCharts(payoff) {
  // Months chart
  const monthsEl = document.getElementById('payoffMonthsChart');
  if (monthsEl) {
    const ctx = monthsEl.getContext('2d');
    destroyIfExists("payoffMonthsChartInstance");

    window.payoffMonthsChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: ['Avalanche', 'Snowball'],
        datasets: [{
          label: 'Months',
          data: [payoff.avalanche.months, payoff.snowball.months],
          borderWidth: 0,
          borderRadius: 10
        }]
      },
      options: {
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: '#cbd5e1', font: { weight: '700' } }, grid: { display: false } },
          y: { ticks: { color: '#cbd5e1' }, grid: { color: 'rgba(148,163,184,0.10)' } }
        }
      }
    });
  }

  // Interest chart
  const intEl = document.getElementById('payoffInterestChart');
  if (intEl) {
    const ctx = intEl.getContext('2d');
    destroyIfExists("payoffInterestChartInstance");

    window.payoffInterestChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: ['Avalanche', 'Snowball'],
        datasets: [{
          label: 'Interest',
          data: [payoff.avalanche.interest, payoff.snowball.interest],
          borderWidth: 0,
          borderRadius: 10
        }]
      },
      options: {
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => `$${Math.round(ctx.raw).toLocaleString()}`
            }
          }
        },
        scales: {
          x: { ticks: { color: '#cbd5e1', font: { weight: '700' } }, grid: { display: false } },
          y: { ticks: { color: '#cbd5e1' }, grid: { color: 'rgba(148,163,184,0.10)' } }
        }
      }
    });
  }
}

if (window.Chart) {
  Chart.defaults.color = "#cbd5e1";
  Chart.defaults.borderColor = "rgba(148,163,184,0.12)";
  Chart.defaults.font.family = "Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif";
}


(function initScheduleKindSync() {
  function syncRow(form) {
    const sel = form.querySelector('.js-kind-select');
    const kindInput = form.querySelector('.js-kind-input');
    const customInput = form.querySelector('.js-custom-name');
    if (!sel || !kindInput || !customInput) return;

    const opt = sel.options[sel.selectedIndex];
    const kind = (opt?.dataset?.kind || 'debt').toLowerCase();
    kindInput.value = kind;

    const isCustom = sel.value === "__custom__";
    customInput.disabled = !isCustom;
    if (!isCustom) customInput.value = "";
  }

  function init() {
    // only on schedule page
    if (!document.querySelector('.schedule-grid')) return;

    const forms = document.querySelectorAll('form.addform');
    forms.forEach(form => {
      const sel = form.querySelector('.js-kind-select');
      if (!sel) return;

      // initial state
      syncRow(form);

      // update on change
      sel.addEventListener('change', () => syncRow(form));
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

