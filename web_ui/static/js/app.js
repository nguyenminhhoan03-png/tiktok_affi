// FRONTEND LOGIC FOR TIKTOK AUTO UPLOADER DASHBOARD

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  fetchStats();
  fetchJobs();
  fetchVideos();
  fetchLogs();
  initModals();
  initPipelineRun();
  
  // Auto refresh stats & logs every 5 seconds
  setInterval(fetchStats, 5000);
  setInterval(fetchJobs, 5000);
});

// TAB SWITCHING
function initTabs() {
  const navItems = document.querySelectorAll('.nav-item');
  navItems.forEach(item => {
    item.addEventListener('click', () => {
      const targetTab = item.getAttribute('data-tab');
      switchTab(targetTab);
    });
  });
}

function switchTab(tabId) {
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  
  const activeBtn = document.querySelector(`.nav-item[data-tab="${tabId}"]`);
  const activeTab = document.getElementById(tabId);
  
  if (activeBtn) activeBtn.classList.add('active');
  if (activeTab) activeTab.classList.add('active');
  
  if (tabId === 'tab-logs') fetchLogs();
  if (tabId === 'tab-videos') fetchVideos();
}

// FETCH STATS
async function fetchStats() {
  try {
    const res = await fetch('/api/stats');
    const data = await res.json();
    
    document.getElementById('stat-total').textContent = data.total_jobs;
    document.getElementById('stat-pending').textContent = data.pending;
    document.getElementById('stat-processing').textContent = data.processing;
    document.getElementById('stat-failed').textContent = data.failed;
    
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');
    
    if (data.pipeline_running) {
      dot.className = 'dot running';
      text.textContent = 'Đang chạy Pipeline...';
    } else {
      dot.className = 'dot';
      text.textContent = 'Đang sẵn sàng';
    }
  } catch (err) {
    console.error('Lỗi lấy stats:', err);
  }
}

// FETCH JOBS
async function fetchJobs() {
  try {
    const res = await fetch('/api/jobs');
    const jobs = await res.json();
    
    renderDashJobs(jobs);
    renderJobsTable(jobs);
  } catch (err) {
    console.error('Lỗi lấy danh sách jobs:', err);
  }
}

function renderDashJobs(jobs) {
  const tbody = document.getElementById('dash-jobs-tbody');
  if (!tbody) return;
  
  if (jobs.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="text-center">Chưa có job nào trong danh sách.</td></tr>';
    return;
  }
  
  tbody.innerHTML = jobs.slice(0, 5).map((job, idx) => `
    <tr>
      <td>${idx + 1}</td>
      <td><strong>${job.product_name || 'Tự động cào'}</strong><br><small class="text-muted">${job.product_url.substring(0, 40)}...</small></td>
      <td><span class="badge badge-info">${job.video_segments || 2} clips</span></td>
      <td>${job.tiktok_account || 'acc1'}</td>
      <td>${getStatusBadge(job.status)}</td>
    </tr>
  `).join('');
}

function renderJobsTable(jobs) {
  const tbody = document.getElementById('jobs-tbody');
  if (!tbody) return;
  
  if (jobs.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center">Chưa có job nào. Bấm "Thêm Hàng Loạt Link" để tạo mới!</td></tr>';
    return;
  }
  
  tbody.innerHTML = jobs.map((job, idx) => `
    <tr>
      <td>${idx + 1}</td>
      <td><a href="${job.product_url}" target="_blank" style="color:var(--accent-cyan);">${job.product_url.substring(0, 35)}...</a></td>
      <td>${job.product_name || '<i class="text-muted">Tự động cào từ link</i>'}</td>
      <td>${job.prompt || 'auto'}</td>
      <td>${job.video_segments || 2} phân đoạn</td>
      <td>${getStatusBadge(job.status)} ${job.error_msg ? `<br><small class="text-danger">${job.error_msg}</small>` : ''}</td>
      <td>
        <button class="btn btn-sm btn-secondary" onclick="resetJob(${idx})" title="Chạy lại"><i class="fa-solid fa-rotate"></i></button>
        <button class="btn btn-sm btn-secondary" onclick="deleteJob(${idx})" title="Xóa"><i class="fa-solid fa-trash" style="color:var(--accent-red)"></i></button>
      </td>
    </tr>
  `).join('');
}

function getStatusBadge(status) {
  if (status === 'pending') return '<span class="badge badge-pending"><i class="fa-solid fa-clock"></i> Pending</span>';
  if (status === 'processing') return '<span class="badge badge-processing"><i class="fa-solid fa-spinner fa-spin"></i> Processing</span>';
  if (status === 'failed') return '<span class="badge badge-failed"><i class="fa-solid fa-triangle-exclamation"></i> Failed</span>';
  return '<span class="badge badge-success"><i class="fa-solid fa-check"></i> Success</span>';
}

// JOB ACTIONS
async function resetJob(idx) {
  try {
    await fetch(`/api/jobs/${idx}/reset`, { method: 'POST' });
    fetchJobs();
    fetchStats();
  } catch (err) {
    alert('Lỗi khi reset job: ' + err);
  }
}

async function deleteJob(idx) {
  if (!confirm('Bạn có chắc chắn muốn xóa job này?')) return;
  try {
    await fetch(`/api/jobs/${idx}`, { method: 'DELETE' });
    fetchJobs();
    fetchStats();
  } catch (err) {
    alert('Lỗi khi xóa job: ' + err);
  }
}

// FETCH VIDEOS
async function fetchVideos() {
  try {
    const res = await fetch('/api/videos');
    const videos = await res.json();
    const container = document.getElementById('video-container');
    if (!container) return;
    
    if (videos.length === 0) {
      container.innerHTML = '<p class="text-muted">Chưa có video nào được tạo.</p>';
      return;
    }
    
    container.innerHTML = videos.map(v => `
      <div class="video-card">
        <video controls preload="metadata">
          <source src="${v.path}" type="video/mp4">
        </video>
        <div class="video-info">
          <span>${v.name.substring(0, 20)}...</span>
          <span class="badge ${v.type === 'done' ? 'badge-success' : 'badge-info'}">${v.type.toUpperCase()}</span>
        </div>
      </div>
    `).join('');
  } catch (err) {
    console.error('Lỗi tải video:', err);
  }
}

// FETCH LOGS
async function fetchLogs() {
  try {
    const res = await fetch('/api/logs');
    const data = await res.json();
    const consoleEl = document.getElementById('log-console');
    if (consoleEl) {
      consoleEl.textContent = data.log || 'Không có dữ liệu log.';
      consoleEl.scrollTop = consoleEl.scrollHeight;
    }
  } catch (err) {
    console.error('Lỗi tải log:', err);
  }
}

// MODAL BATCH ADD
function initModals() {
  const modalBatch = document.getElementById('modal-batch');
  const btnQuick = document.getElementById('btn-quick-batch');
  const closeBtns = document.querySelectorAll('.close-modal');
  
  if (btnQuick) {
    btnQuick.addEventListener('click', () => modalBatch.classList.add('active'));
  }
  
  closeBtns.forEach(btn => {
    btn.addEventListener('click', () => modalBatch.classList.remove('active'));
  });
  
  const submitBatch = document.getElementById('btn-submit-batch');
  if (submitBatch) {
    submitBatch.addEventListener('click', async () => {
      const urlsText = document.getElementById('batch-urls').value;
      if (!urlsText.trim()) return alert('Vui lòng nhập ít nhất 1 link!');
      
      try {
        const res = await fetch('/api/jobs/batch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ urls: urlsText })
        });
        const result = await res.json();
        if (result.success) {
          alert(`Đã thêm thành công ${result.added} jobs!`);
          modalBatch.classList.remove('active');
          document.getElementById('batch-urls').value = '';
          fetchJobs();
          fetchStats();
        }
      } catch (err) {
        alert('Lỗi khi thêm jobs: ' + err);
      }
    });
  }
}

// RUN PIPELINE
function initPipelineRun() {
  const btnRun = document.getElementById('btn-run-pipeline');
  if (btnRun) {
    btnRun.addEventListener('click', async () => {
      if (!confirm('Bạn có muốn bắt đầu chạy Pipeline tự động ngay bây giờ không?')) return;
      try {
        const res = await fetch('/api/pipeline/run', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          alert('🚀 Pipeline đã bắt đầu chạy! Theo dõi trạng thái tại tab Dashboard hoặc Nhật ký Logs.');
          fetchStats();
        } else {
          alert('⚠️ Lỗi: ' + data.error);
        }
      } catch (err) {
        alert('Lỗi khi gọi chạy pipeline: ' + err);
      }
    });
  }
  
  const btnRefreshLogs = document.getElementById('btn-refresh-logs');
  if (btnRefreshLogs) {
    btnRefreshLogs.addEventListener('click', fetchLogs);
  }
  
  const btnRefreshHeader = document.getElementById('btn-refresh');
  if (btnRefreshHeader) {
    btnRefreshHeader.addEventListener('click', () => {
      fetchStats();
      fetchJobs();
      fetchVideos();
    });
  }
}
