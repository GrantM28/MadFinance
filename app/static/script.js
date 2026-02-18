/**
 * Finance Strategy Engine - Frontend Logic
 */

function initDtiChart(obligations, freeCashflow) {
    const el = document.getElementById('dtiChart');
    if (!el) return; // guard: only init if canvas exists

    const ctx = el.getContext('2d');

    if (window.dtiChartInstance) {
        window.dtiChartInstance.destroy();
    }

    window.dtiChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Obligations (Bills + Min Debt)', 'Free Cashflow'],
            datasets: [{
                data: [obligations, freeCashflow],
                backgroundColor: ['#fb7185', '#34d399'],
                hoverOffset: 12,
                borderWidth: 0,
                borderRadius: 6
            }]
        },
        options: {
            cutout: '76%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#94a3b8',
                        padding: 18,
                        font: { size: 12, weight: '600' }
                    }
                }
            }
        }
    });
}
