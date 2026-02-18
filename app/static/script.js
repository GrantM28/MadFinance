/**
 * Finance Strategy Engine - Frontend Logic
 */

function destroyIfExists(key) {
  if (window[key]) {
    window[key].destroy();
    window[key] = null;
  }
}

function initDtiChart(obligations, freeCashflow) {
  const el = document.getElementById('dtiChart');
  if (!el) return;

  const ctx = el.getContext('2d');
  destroyIfExists("dtiChartInstance");

  window.dtiChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Obligations', 'Free Cashflow'],
      datasets: [{
        data: [obligations, freeCashflow],
        backgroundColor: ['#fb7185', '#34d399'],
        hoverOffset: 10,
        borderWidth: 0,
        borderRadius: 6
      }]
    },
    options: {
      cutout: '74%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: '#cbd5e1',
            padding: 16,
            font: { size: 12, weight: '600' }
          }
        },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.label}: $${Math.round(ctx.raw).toLocaleString()}`
          }
        }
      }
    }
  });
}

function initDebtBarChart(debts) {
  const el = document.getElementById('debtBarChart');
  if (!el) return;

  const ctx = el.getContext('2d');
  destroyIfExists("debtBarChartInstance");

  const labels = debts.map(d => d.name);
  const data = debts.map(d => d.balance);

  window.debtBarChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Balance',
        data,
        borderWidth: 0,
        borderRadius: 10
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `$${Math.round(ctx.raw).toLocaleString()}`
          }
        }
      },
      scales: {
        x: {
          ticks: { color: '#cbd5e1', font: { weight: '600' } },
          grid: { color: 'rgba(148,163,184,0.10)' }
        },
        y: {
          ticks: { color: '#cbd5e1' },
          grid: { color: 'rgba(148,163,184,0.10)' }
        }
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
