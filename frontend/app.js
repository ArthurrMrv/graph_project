const API_URL = "http://localhost:8000/api/pipeline/dataset_to_graph";

document.getElementById('pipelineForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const runBtn = document.getElementById('runBtn');
    const btnText = runBtn.querySelector('.btn-text');
    const spinner = runBtn.querySelector('.loading-spinner');
    const outputArea = document.getElementById('outputArea');

    outputArea.classList.add('hidden');
    btnText.classList.add('hidden');
    spinner.classList.remove('hidden');
    runBtn.disabled = true;

    const formData = new FormData(e.target);
    const payload = {
        stock: formData.get('stock'),
        start_date: formData.get('start_date'),
        end_date: formData.get('end_date'),
        chunk_size: 2000
    };

    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        outputArea.classList.remove('hidden');
        const badge = document.getElementById('statusBadge');

        if (response.ok && data.status === "success") {
            badge.textContent = "Success";
            badge.className = "badge success";

            document.getElementById('stockRecords').textContent = data.prices_synced || 0;
            document.getElementById('tweetRecords').textContent = data.tweets_imported || 0;

            if (data.sentiment_processing) {
                document.getElementById('sentimentProcessed').textContent = data.sentiment_processing.tweets_processed || 0;
                document.getElementById('sentimentUpdated').textContent = data.sentiment_processing.tweets_updated || 0;
            } else {
                document.getElementById('sentimentProcessed').textContent = "N/A";
                document.getElementById('sentimentUpdated').textContent = "N/A";
            }

        } else {
            badge.textContent = "Error";
            badge.className = "badge error";
        }

        document.getElementById('jsonOutput').textContent = JSON.stringify(data, null, 2);

    } catch (err) {
        outputArea.classList.remove('hidden');
        document.getElementById('statusBadge').textContent = "Network Error";
        document.getElementById('statusBadge').className = "badge error";
        document.getElementById('jsonOutput').textContent = "Error connecting to server: " + err.message;
    } finally {
        btnText.classList.remove('hidden');
        spinner.classList.add('hidden');
        runBtn.disabled = false;
    }
});

const ANALYTICS_API_URL = "http://localhost:8000/api/analytics/stock-sentiment";
let chartInstance = null;

document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const tabName = btn.dataset.tab;
        document.querySelectorAll('.view-section').forEach(view => view.classList.add('hidden'));
        document.getElementById(`${tabName}-view`).classList.remove('hidden');
    });
});

document.getElementById('loadAnalyticsBtn').addEventListener('click', async () => {
    const stock = document.getElementById('analytics-stock').value;
    const btn = document.getElementById('loadAnalyticsBtn');

    const originalText = btn.textContent;
    btn.textContent = "Loading...";
    btn.disabled = true;

    try {
        const response = await fetch(`${ANALYTICS_API_URL}/${stock}`);
        const result = await response.json();

        if (result.error) {
            alert("Error fetching data: " + result.error);
            return;
        }

        renderChart(result.data, stock);
        renderDonutChart(result.data);

    } catch (err) {
        alert("Network Error: " + err.message);
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
});

function renderChart(data, stock) {
    const ctx = document.getElementById('correlationChart').getContext('2d');

    const labels = data.map(d => d.date);
    const prices = data.map(d => d.price);
    const sentiments = data.map(d => d.sentiment);

    if (chartInstance) {
        chartInstance.destroy();
    }

    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Stock Price ($)',
                    data: prices,
                    borderColor: '#06b6d4',
                    backgroundColor: 'rgba(6, 182, 212, 0.1)',
                    yAxisID: 'y',
                    tension: 0.4,
                    fill: true
                },
                {
                    label: 'Avg Sentiment (0-1)',
                    data: sentiments,
                    borderColor: '#8b5cf6',
                    backgroundColor: 'rgba(139, 92, 246, 0.5)',
                    yAxisID: 'y1',
                    type: 'bar',
                    barThickness: 10
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                title: {
                    display: true,
                    text: `Correlation: ${stock} Price vs Sentiment`,
                    color: '#fff',
                    font: { size: 16 }
                },
                legend: {
                    labels: { color: '#cbd5e1' }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#94a3b8' },
                    grid: { color: 'rgba(255, 255, 255, 0.05)' }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    ticks: { color: '#06b6d4' },
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    title: { display: true, text: 'Price ($)', color: '#06b6d4' }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    ticks: { color: '#8b5cf6' },
                    grid: { drawOnChartArea: false },
                    min: 0,
                    max: 1,
                    title: { display: true, text: 'Sentiment Score', color: '#8b5cf6' }
                }
            }
        }
    });
}

let donutInstance = null;

function renderDonutChart(data) {
    const ctx = document.getElementById('sentimentDonut').getContext('2d');

    // Calculate High-Level stats
    // sentiment is 0-1 avg. Volume is count.
    // Est Positive = sum(sentiment * volume)
    // Est Negative = Total Volume - Est Positive

    let totalVolume = 0;
    let weightedPos = 0;

    data.forEach(d => {
        totalVolume += d.volume;
        weightedPos += (d.sentiment * d.volume);
    });

    const positiveCount = Math.round(weightedPos);
    const negativeCount = totalVolume - positiveCount;

    if (donutInstance) {
        donutInstance.destroy();
    }

    donutInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Positive', 'Negative/Neutral'],
            datasets: [{
                data: [positiveCount, negativeCount],
                backgroundColor: [
                    '#8b5cf6', // Violet (Pos)
                    '#f472b6'  // Pink (Neg)
                ],
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#cbd5e1', padding: 20 }
                },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            const val = context.raw;
                            const pct = totalVolume > 0 ? ((val / totalVolume) * 100).toFixed(1) : 0;
                            return ` ${context.label}: ${val} (${pct}%)`;
                        }
                    }
                }
            },
            cutout: '70%'
        }
    });
}
