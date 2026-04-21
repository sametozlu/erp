/* Tasks Realtime Updates */

document.addEventListener('DOMContentLoaded', () => {
    // Socket initialization is handled in base.html usually, but if not, we use the global one
    const socket = window.__socket || (window.io ? window.io() : null);

    if (!socket) {
        console.error("Socket.io not initialized");
        return;
    }

    // Join the tasks room
    socket.on('connect', () => {
        console.log('Connected to socket, joining task_updates');
        socket.emit('join_task_updates');
    });

    // If already connected
    if (socket.connected) {
        socket.emit('join_task_updates');
    }

    // Listeners
    socket.on('task_created', (data) => {
        handleTaskCreated(data.task);
    });

    socket.on('task_updated', (data) => {
        handleTaskUpdated(data.task, data.changes);
    });

    // Optional: handle comments to show a small indicator or toast
    socket.on('task_commented', (data) => {
        // Find the task row and maybe flash it or show a notification
        const row = document.querySelector(`.task-item[data-task-id="${data.task_id}"]`);
        if (row) {
            // Flash effect
            const originalBg = row.style.backgroundColor;
            row.style.backgroundColor = "rgba(59, 130, 246, 0.1)"; // blue tint
            setTimeout(() => {
                row.style.backgroundColor = originalBg;
            }, 1000);
        }
    });

    window.addEventListener('beforeunload', () => {
        socket.emit('leave_task_updates');
    });
});

function handleTaskCreated(task) {
    // 1. Check if the new task matches current filters
    // This is hard to do perfectly on frontend without duplicating backend logic, 
    // but we can do basic checks (status, etc.)

    // Update Stats
    updateStats(task.status, 'add');

    // If we are on the first page and sorting is default (created_at desc), prepend it
    // Or just prepend it regardless if it passes filters

    const taskList = document.querySelector('.task-list');
    if (!taskList) return;

    // Basic Client-Side Filtering Check
    if (!shouldShowTask(task)) return;

    // Create DOM element
    const newItem = createTaskElement(task);

    // Insert at top
    taskList.insertBefore(newItem, taskList.firstChild);

    // Flash Animation
    newItem.style.animation = "highlight-fade 2s ease-out";
}

function handleTaskUpdated(task, changes) {
    const row = document.querySelector(`.task-item[data-task-id="${task.id}"]`);

    // 1. Update stats (if status changed)
    // We need the OLD status to decrement count. 
    // The backend sends 'changes' list: [('status', 'Old Status', 'New Status', 'Label')]
    if (changes) {
        const statusChange = changes.find(c => c[0] === 'status');
        if (statusChange) {
            const oldStatus = statusChange[1];
            const newStatus = statusChange[2];
            updateStats(oldStatus, 'remove');
            updateStats(newStatus, 'add');
        }
    }

    // 2. If row exists, update it
    if (row) {
        // Check if it still passes filters
        if (!shouldShowTask(task)) {
            row.remove();
            return;
        }

        updateTaskRow(row, task);

        // Flash animation
        const originalBg = row.style.backgroundColor;
        row.style.backgroundColor = "rgba(255, 241, 242, 0.5)"; // light red/warm tint for update
        row.style.transition = "background-color 0.5s";
        setTimeout(() => {
            row.style.backgroundColor = "";
        }, 1000);

    } else {
        // Row doesn't exist, maybe it now matches filters?
        if (shouldShowTask(task)) {
            const newItem = createTaskElement(task);
            const taskList = document.querySelector('.task-list');
            // Try to find correct position or just prepend
            if (taskList) taskList.insertBefore(newItem, taskList.firstChild);
        }
    }
}

function updateStats(status, action) {
    // Stats: Toplam, Açık, Kapalı, Bana Atanan (handled separately usually)

    // Helper to safe update text content number
    const safeUpdate = (selector, delta) => {
        const el = document.querySelector(selector);
        if (el) {
            let val = parseInt(el.textContent) || 0;
            val += delta;
            el.textContent = val;
        }
    };

    const delta = action === 'add' ? 1 : -1;

    // Total
    safeUpdate('.stat-item[data-stat="total"] .stat-value', delta);

    // Check status type
    const closedStatuses = ["İş Halledildi", "Reddedildi", "Hatalı Giriş", "İptal"];
    const isClosed = closedStatuses.includes(status);

    if (isClosed) {
        safeUpdate('.stat-item[data-stat="closed"] .stat-value', delta);
    } else {
        safeUpdate('.stat-item[data-stat="open"] .stat-value', delta);
    }

    // 'Bana Atanan' is tricky because we need to know if it's assigned to CURRENT user.
    // The 'task' object has 'assigned_user_id'. match with session user id.
    const currentUserId = window.__sessionData ? window.__sessionData.userId : 0;
    // This requires passing task object to updateStats which we didn't do fully for creation... 
    // For simplicity, we might skip 'Bana Atanan' real-time update or need to pass the whole task object.
}

function shoudHideTaskBasedOnFilters() {
    // Read current filter values from DOM inputs
    const statusFilter = document.querySelector('select[name="status"]')?.value;
    const priorityFilter = document.querySelector('select[name="priority"]')?.value;
    const searchFilter = document.querySelector('input[name="search"]')?.value?.toLowerCase();

    // Implementation would go here, but for now we trust backend or just append
    return false;
}

function shouldShowTask(task) {
    // Simple client-side filter check
    const statusFilter = document.getElementById('filterStatus')?.value;
    const priorityFilter = document.getElementById('filterPriority')?.value;
    const userFilter = document.getElementById('filterUser')?.value;
    const searchFilter = document.getElementById('searchInput')?.value?.toLowerCase();

    // Status
    if (statusFilter && task.status !== statusFilter) return false;

    // Priority
    if (priorityFilter && task.priority.toString() !== priorityFilter) return false;

    // User
    if (userFilter && task.assigned_user_id.toString() !== userFilter) return false;

    // Search (simple)
    if (searchFilter) {
        const text = (task.task_no + " " + task.subject + " " + (task.description || "")).toLowerCase();
        if (!text.includes(searchFilter)) return false;
    }

    return true;
}

function createTaskElement(task) {
    const div = document.createElement('div');
    div.className = 'task-item';
    div.setAttribute('data-task-id', task.id);
    div.setAttribute('data-status', task.status);
    div.setAttribute('data-priority', task.priority); // For sorting/styling if needed

    // Determine priority color class or style
    const pColor = getPriorityColor(task.priority);

    // Status badge class
    let statusClass = 'waiting';
    if (["İş Halledildi", "Tamamlandı"].includes(task.status)) statusClass = 'closed';
    else if (["İptal", "Reddedildi"].includes(task.status)) statusClass = 'closed'; // or danger
    else if (["Devam Ediyor", "Tasarlanıyor"].includes(task.status)) statusClass = 'progress';
    else if (["İlk Giriş", "Açık"].includes(task.status)) statusClass = 'open';

    div.innerHTML = `
        <div class="task-priority-indicator" data-priority="${task.priority}"></div>
        <div class="task-item-content">
            <div class="task-header-line">
                <span class="task-no-badge task-no">${task.task_no}</span>
                <div class="task-subject">${escapeHtml(task.subject)}</div>
            </div>
            <div class="task-meta">
                <div class="task-meta-item">
                    <span class="task-status-badge ${statusClass}">${task.status}</span>
                </div>
                <div class="task-meta-item" title="Atanan">
                    <span style="font-weight:600; color:var(--text-light);">${task.assigned_user_name || '-'}</span>
                </div>
                <div class="task-meta-item" title="Hedef Tarih">
                    <span>${task.target_date_display || '-'}</span>
                </div>
            </div>
        </div>
    `;

    // Add click event for detail modal
    div.addEventListener('click', () => {
        // Assuming openTaskDetail is a global function from tasks.html script
        if (window.openTaskDetail) window.openTaskDetail(task.id);
    });

    return div;
}

function updateTaskRow(row, task) {
    // Update attributes
    row.setAttribute('data-status', task.status);
    row.setAttribute('data-priority', task.priority);

    // Update content
    // Specifically Priority Indicator
    const indicator = row.querySelector('.task-priority-indicator');
    if (indicator) indicator.setAttribute('data-priority', task.priority);

    // Subject
    const subjectEl = row.querySelector('.task-subject');
    if (subjectEl) subjectEl.textContent = task.subject;

    // Status Badge
    const statusBadge = row.querySelector('.task-status-badge');
    if (statusBadge) {
        statusBadge.textContent = task.status;
        // Update class
        statusBadge.className = 'task-status-badge'; // reset
        let statusClass = 'waiting';
        if (["İş Halledildi", "Tamamlandı"].includes(task.status)) statusClass = 'closed';
        else if (["İptal", "Reddedildi"].includes(task.status)) statusClass = 'closed';
        else if (["Devam Ediyor", "Tasarlanıyor"].includes(task.status)) statusClass = 'progress';
        else if (["İlk Giriş", "Açık"].includes(task.status)) statusClass = 'open';
        statusBadge.classList.add(statusClass);
    }

    // Assigned User
    // We need to find the element, it is the second span in meta usually, but relying on order is risky.
    // In createTaskElement we didn't give it a class.
    // Let's re-render the content or try to find it. 
    // Re-rendering innerHTML is safer for consistency.

    const pColor = getPriorityColor(task.priority);
    let statusClass = 'waiting';
    if (["İş Halledildi", "Tamamlandı"].includes(task.status)) statusClass = 'closed';
    else if (["İptal", "Reddedildi"].includes(task.status)) statusClass = 'closed';
    else if (["Devam Ediyor", "Tasarlanıyor"].includes(task.status)) statusClass = 'progress';
    else if (["İlk Giriş", "Açık"].includes(task.status)) statusClass = 'open';

    row.innerHTML = `
        <div class="task-priority-indicator" data-priority="${task.priority}"></div>
        <div class="task-item-content">
            <div class="task-header-line">
                <span class="task-no-badge task-no">${task.task_no}</span>
                <div class="task-subject">${escapeHtml(task.subject)}</div>
            </div>
            <div class="task-meta">
                <div class="task-meta-item">
                    <span class="task-status-badge ${statusClass}">${task.status}</span>
                </div>
                <div class="task-meta-item" title="Atanan">
                    <span style="font-weight:600; color:var(--text-light);">${task.assigned_user_name || '-'}</span>
                </div>
                <div class="task-meta-item" title="Hedef Tarih">
                    <span>${task.target_date_display || '-'}</span>
                </div>
            </div>
        </div>
    `;
}

// Helpers
function getPriorityColor(p) {
    // Map to CSS vars or values
    return ""; // handled by CSS [data-priority]
}

function escapeHtml(text) {
    if (!text) return "";
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
