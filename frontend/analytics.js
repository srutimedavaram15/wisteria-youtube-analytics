const ANALYTICS_CHANNEL_ID = 'UCpB959t8iPrxQWj7G6n0ctQ';
let weekdayChart = null;
let baselineChart = null;

async function loadAnalytics(days) {
  let url = `http://127.0.0.1:8000/analytics?channel_id=${ANALYTICS_CHANNEL_ID}`;
  if (days) url += `&days=${days}`;

  const res = await fetch(url);
  const data = await res.json();

  document.getElementById('stat-videos').textContent = data.total_videos.toLocaleString();
  document.getElementById('stat-views').textContent = Math.round(data.avg_views).toLocaleString();
  document.getElementById('stat-likes').textContent = Math.round(data.avg_likes).toLocaleString();

  const banner = document.getElementById('best-day-banner');
  if (data.best_day) {
    banner.textContent = `🪷 Best day to post: ${data.best_day} (avg ${Math.round(data.best_day_avg_views).toLocaleString()} views) 🪷`;
  } else {
    banner.textContent = `🌱 Not enough data yet to recommend a best day`;
  }

  const labels = data.weekday_performance.map(d => d.weekday);
  const values = data.weekday_performance.map(d => d.avg_views);
  const colors = labels.map(l => l === data.best_day ? '#b7cbb7' : '#9EACCA');

  if (weekdayChart) weekdayChart.destroy();
  weekdayChart = new Chart(document.getElementById('weekday-chart'), {
    type: 'bar',
    data: { labels, datasets: [{ data: values, backgroundColor: colors, borderRadius: 8, borderSkipped: false }] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 1200, easing: 'easeOutQuart' },
      plugins: {
        legend: { display: false },
        title: { display: true, text: 'Performance by Weekday', font: { size: 16, family: 'Space Grotesk' }, color: '#545454' }
      },
      scales: {
        y: { grid: { color: '#e5e5e5' }, ticks: { font: { family: 'Space Grotesk' } } },
        x: { grid: { display: false }, ticks: { font: { family: 'Space Grotesk' } } }
      }
    }
  });

  const above = data.videos_above_average;
  const below = data.videos_with_baseline_data - data.videos_above_average;

  if (baselineChart) baselineChart.destroy();
  baselineChart = new Chart(document.getElementById('baseline-chart'), {
    type: 'doughnut',
    data: {
      labels: ['Above Average', 'Below Average'],
      datasets: [{ data: [above, below], backgroundColor: ['#b7cbb7', '#BCC6E0'] }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: { display: true, text: 'Videos vs. Channel Average', font: { size: 16, family: 'Space Grotesk' }, color: '#545454' },
        legend: { position: 'bottom', labels: { font: { family: 'Space Grotesk' } } }
      }
    }
  });
}

document.querySelectorAll('.date-filter').forEach(function (btn) {
  btn.addEventListener('click', function () {
    document.querySelectorAll('.date-filter').forEach(function (b) { b.classList.remove('active'); });
    btn.classList.add('active');
    loadAnalytics(btn.dataset.days || null);
  });
});

document.addEventListener('DOMContentLoaded', function () {
  loadAnalytics(30);
});