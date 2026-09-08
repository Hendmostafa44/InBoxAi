// Dynamic Backend API Host Resolution
const getApiBaseUrl = () => {
    if (window.INBOXAI_CONFIG && window.INBOXAI_CONFIG.API_BASE_URL) {
        return window.INBOXAI_CONFIG.API_BASE_URL;
    }
    const isLocalhost = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
    return isLocalhost ? "http://localhost:8007" : "https://inboxai.fastapicloud.dev";

};

const API_BASE_URL = getApiBaseUrl();

// Visitor Session Storage for Isolated Sandboxes
let sessionId = sessionStorage.getItem("inboxai_session_id");
if (!sessionId) {
    sessionId = "session_" + Math.random().toString(36).substring(2, 11);
    sessionStorage.setItem("inboxai_session_id", sessionId);
}

const getHeaders = (extraHeaders = {}) => ({
    "Content-Type": "application/json",
    "X-Session-ID": sessionId,
    ...extraHeaders
});

// Load authenticated user from server session
// Load authenticated user from server session
async function loadCurrentUser() {
    try {
        const response = await fetch(`${API_BASE_URL}/auth/me`, {
            credentials: "include"
        });

        if (!response.ok) {
            throw new Error(`Auth request failed: ${response.status}`);
        }

        const data = await response.json();
        console.log("AUTH ME DATA:", data);

        if (data.logged_in || data.authenticated) {

            const displayName = data.name || data.email || "User";
            const email = data.email || "";

            // Update all username elements
            document.querySelectorAll(".user-name").forEach(element => {
                element.textContent = displayName;
            });

            // Update all email elements
            document.querySelectorAll(".user-email").forEach(element => {
                element.textContent = email;
            });

            // Get first letter for avatar
            const firstLetter = displayName
                .trim()
                .charAt(0)
                .toUpperCase() || "U";

            const userAvatar = document.getElementById("userAvatar");
            if (userAvatar) {
                userAvatar.textContent = firstLetter;
            }

            const topAvatar = document.getElementById("topAvatar");
            if (topAvatar) {
                topAvatar.textContent = firstLetter;
            }

        } else {
            console.log("User is not authenticated.");
        }

        return data;

    } catch (error) {
        console.error("Error loading current user:", error);
        return null;
    }
}

async function loadInboxEmails() {
    try {
        const response = await fetch(`${API_BASE_URL}/emails`, {
            credentials: "include"
        });

        if (response.status === 401) {
            return;
        }

        if (!response.ok) {
            throw new Error(`Failed to fetch emails: ${response.status}`);
        }

        const data = await response.json();

        console.log("INBOX EMAILS:", data);

        const emailList = document.getElementById("emailList");

        if (!emailList) return;

        emailList.innerHTML = "";

        if (!data.emails || data.emails.length === 0) {
            emailList.innerHTML = `
                <div class="empty-feature" style="padding: 50px 20px;">
                    <div class="big-icon">✉</div>
                    <h2>Your Inbox is Clear</h2>
                    <p>No emails found in your Gmail inbox.</p>
                </div>
            `;
            return;
        }

        data.emails.forEach(email => {

            const senderText = email.sender || "Unknown Sender";

            const senderName = senderText
                .replace(/<.*?>/g, "")
                .replace(/"/g, "")
                .trim();

            const firstLetter =
                senderName.charAt(0).toUpperCase() || "U";

            const avatarColors = [
                "purple-bg",
                "blue-bg",
                "green-bg"
            ];

            const colorClass =
                avatarColors[
                    Math.abs(firstLetter.charCodeAt(0)) %
                    avatarColors.length
                ];

            const date = email.received_at
                ? new Date(email.received_at)
                : null;

            const formattedDate =
                date && !isNaN(date)
                    ? date.toLocaleDateString()
                    : "Today";

            const body = email.body || "";

            const preview = body
                .replace(/\s+/g, " ")
                .trim()
                .substring(0, 180);

            const searchStr = `
                ${senderName}
                ${email.subject || ""}
                ${body}
            `.toLowerCase();

            const emailCard = document.createElement("div");

            emailCard.className = "email-card unread";

            emailCard.setAttribute(
                "data-search",
                searchStr
            );

            emailCard.innerHTML = `
                <div class="sender-avatar ${colorClass}">
                    ${firstLetter}
                </div>

                <div class="email-body">

                    <div class="email-line">

                        <strong>
                            ${senderName}
                        </strong>

                        <span>
                            ${formattedDate}
                        </span>

                    </div>

                    <h3>
                        ${email.subject || "No Subject"}
                    </h3>

                    <p>
                        ${preview}
                        ${body.length > 180 ? "..." : ""}
                    </p>

                    <div class="email-meta">

                        <span>
                            ✉ Gmail
                        </span>

                        <span>
                            ◷ ${formattedDate}
                        </span>

                        <span>
                            ✓ Email received
                        </span>

                    </div>

                </div>
            `;

            emailList.appendChild(emailCard);
        });

        const inboxSubtitle =
            document.getElementById("inboxSubtitle");

        if (inboxSubtitle) {
            inboxSubtitle.textContent =
                `${data.count} messages · Gmail synced`;
        }

        const countEl =
            document.getElementById("email-count");

        if (countEl) {
            countEl.textContent = data.count;
        }

    } catch (error) {
        console.error(
            "Error loading inbox emails:",
            error
        );
    }
}

(async () => {
    const data = await loadCurrentUser();
    const isLoggedIn = data && (data.logged_in || data.authenticated);

    if (isLoggedIn) {
        try {
            await fetch(`${API_BASE_URL}/gmail/emails`, {
                credentials: "include"
            });
        } catch (error) {
            console.error("Error syncing Gmail:", error);
        }
    }

    await loadInboxEmails();
})();

const pages = document.querySelectorAll(".page");
const navItems = document.querySelectorAll(".nav-item");

function showPage(id) {
  pages.forEach(p => p.classList.toggle("active-page", p.id === id));
  navItems.forEach(n => n.classList.toggle("active", n.dataset.page === id));
  window.scrollTo({top: 0, behavior: "smooth"});
}

document.addEventListener("click", e => {
  const target = e.target.closest("[data-page-target]");
  if (target) showPage(target.dataset.pageTarget);
  const nav = e.target.closest(".nav-item[data-page]");
  if (nav) showPage(nav.dataset.page);
});

const search = document.getElementById("emailSearch");
if (search) {
  search.addEventListener("input", () => {
    const q = search.value.toLowerCase().trim();
    document.querySelectorAll("#emailList .email-card").forEach(card => {
      const searchTarget = ((card.dataset.search || "") + " " + card.textContent).toLowerCase();
      card.style.display = searchTarget.includes(q) ? "flex" : "none";
    });
  });
}

const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const chatMessages = document.getElementById("chatMessages");

function addMessage(text, type) {
  const row = document.createElement("div");
  row.className = `message ${type}`;
  const formattedText = text ? text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') : '';
  row.innerHTML = type === "ai"
    ? `<div class="chat-avatar">✦</div><div><span class="message-name">InboxAI</span><div class="bubble">${formattedText}</div></div>`
    : `<div><div class="bubble">${formattedText}</div></div>`;
  chatMessages.appendChild(row);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function getTaskCount() {
    try {
        const response = await fetch(`${API_BASE_URL}/tasks/count`, { headers: getHeaders() });
        const data = await response.json();
        const count = (data && typeof data.count === 'number') ? data.count : 0;
        const countEl = document.getElementById("email-count");
        if (countEl) countEl.textContent = count;

        const inboxSubtitle = document.getElementById("inboxSubtitle");
        if (inboxSubtitle) {
            inboxSubtitle.textContent = `${count} messages · ${count > 0 ? 'AI prioritized' : 'no pending items'}`;
        }
    } catch (err) {
        console.warn("Task count fetch error:", err);
        const countEl = document.getElementById("email-count");
        if (countEl) countEl.textContent = 0;
    }
}

getTaskCount();

function addThinkingIndicator() {
    const row = document.createElement("div");
    row.id = "thinkingIndicator";
    row.className = "message ai thinking-message";
    row.innerHTML = `
        <div class="chat-avatar">✦</div>
        <div>
            <span class="message-name">InboxAI</span>
            <div class="bubble">
                <span>InboxAI is thinking</span>
                <div class="thinking-dots">
                    <div class="thinking-dot"></div>
                    <div class="thinking-dot"></div>
                    <div class="thinking-dot"></div>
                </div>
            </div>
        </div>
    `;
    chatMessages.appendChild(row);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return row;
}

function removeThinkingIndicator() {
    const indicator = document.getElementById("thinkingIndicator");
    if (indicator) indicator.remove();
}

chatForm.addEventListener("submit", async e => {
    e.preventDefault();

    const value = chatInput.value.trim();
    if (!value) return;

    addMessage(value, "user");
    chatInput.value = "";
    
    const submitBtn = chatForm.querySelector("button[type='submit']");
    chatInput.disabled = true;
    if (submitBtn) submitBtn.classList.add("loading");
    addThinkingIndicator();

    try {
        const response = await fetch(`${API_BASE_URL}/analyze`, {
            method: "POST",
            headers: getHeaders(),
            body: JSON.stringify({
                message: value
            })
        });

        const data = await response.json();

        removeThinkingIndicator();
        addMessage(data.response, "ai");

        if (typeof getAllTasks === "function") getAllTasks();
        if (typeof pendingTasksCount === "function") pendingTasksCount();
        if (typeof getPriorities === "function") getPriorities();
        if (typeof getTaskCount === "function") getTaskCount();
        if (typeof getDeadlines === "function") getDeadlines();

    } catch (error) {
        console.error("Error:", error);
        removeThinkingIndicator();
        addMessage("Sorry, something went wrong while processing your request.", "ai");
    } finally {
        chatInput.disabled = false;
        if (submitBtn) submitBtn.classList.remove("loading");
        chatInput.focus();
    }
});

document.querySelectorAll(".quick-prompts button").forEach(btn => {
  btn.addEventListener("click", () => {
    const q = btn.textContent;
    chatInput.value = q;
    chatForm.requestSubmit();
  });
});

document.querySelectorAll(".task input").forEach(box => {
  box.addEventListener("change", () => {
    box.closest(".task").classList.toggle("done", box.checked);
  });
});

async function getPriorities() {
    try {
        const response = await fetch(`${API_BASE_URL}/tasks/priorities`, { headers: getHeaders() });
        const tasks = await response.json();

        const items = document.querySelectorAll(".priority-item");

        tasks.slice(0, 3).forEach((task, index) => {
            const item = items[index];
            if (!item) return;

            const title = item.querySelector("strong");
            const description = item.querySelector("p");
            const dot = item.querySelector(".priority-dot");
            const tag = item.querySelector(".tag");

            if (title) title.textContent = task.task;
            if (description) description.textContent = `Deadline: ${task.deadline}`;
            if (tag) tag.textContent = task.priority;

            const priority = (task.priority || "medium").toLowerCase();
            if (dot) dot.className = `priority-dot ${priority}`;
            if (tag) {
                tag.className = `tag ${
                    priority === "high" ? "red" : priority === "medium" ? "amber" : "green"
                }`;
            }
        });
    } catch (err) {
        console.warn("Priorities fetch error:", err);
    }
}

getPriorities();

async function pendingTasksCount() {
    try {
        const response = await fetch(`${API_BASE_URL}/tasks/pending/count`, { headers: getHeaders() });
        const data = await response.json();
        const pendingEl = document.getElementById("pending_tasks");
        if (pendingEl) pendingEl.textContent = data.count ?? 0;
    } catch (err) {
        console.warn("Pending tasks count fetch error:", err);
    }
}

pendingTasksCount();
async function getAllTasks() {
    try {
        const response = await fetch(
            `${API_BASE_URL}/tasks/all`,
            {
                headers: getHeaders()
            }
        );

        if (!response.ok) {
            throw new Error(`Failed to fetch tasks: ${response.status}`);
        }

        const tasks = await response.json();

        const todoList =
            document.getElementById("todo-list");

        const todoCount =
            document.getElementById("todo-count");

        const completedList =
            document.getElementById("completed-list");

        const completedCount =
            document.getElementById("completed-count");

        if (todoList) {
            todoList.innerHTML = "";
        }

        if (completedList) {
            completedList.innerHTML = "";
        }

        let pendingNum = 0;
        let completedNum = 0;

        tasks.forEach(task => {

            const priority =
                (task.priority || "medium").toLowerCase();

            let tagClass =
                priority === "high"
                    ? "red"
                    : priority === "medium"
                    ? "amber"
                    : "green";

            const isCompleted =
                task.status === "Completed";

            if (isCompleted) {
                completedNum++;
            } else {
                pendingNum++;
            }

            // =========================
            // Render Task
            // =========================

            const taskElement =
                document.createElement("div");

            taskElement.className =
                `task ${isCompleted ? "done" : ""}`;

            taskElement.innerHTML = `
                <input
                    type="checkbox"
                    ${isCompleted ? "checked" : ""}
                >

                <div>
                    <strong>
                        ${task.task || "No task"}
                    </strong>

                    <p>
                        Deadline · ${task.deadline || "No deadline"}
                    </p>
                </div>

                <span class="tag ${tagClass}">
                    ${task.priority || "Medium"}
                </span>
            `;

            if (isCompleted) {

                if (completedList) {
                    completedList.appendChild(taskElement);
                }

            } else {

                if (todoList) {
                    todoList.appendChild(taskElement);
                }
            }

            // =========================
            // Checkbox
            // =========================

            const checkbox =
                taskElement.querySelector("input");

            if (checkbox) {

                checkbox.addEventListener(
                    "change",
                    async () => {

                        const status =
                            checkbox.checked
                                ? "Completed"
                                : "pending";

                        await fetch(
                            `${API_BASE_URL}/tasks/status?task_id=${encodeURIComponent(task.id || "")}&task_name=${encodeURIComponent(task.task || "")}&status=${status}`,
                            {
                                method: "PUT",
                                headers: getHeaders()
                            }
                        );

                        getAllTasks();
                        pendingTasksCount();
                        getDeadlines();
                    }
                );
            }
        });

        if (todoCount) {
            todoCount.textContent = pendingNum;
        }

        if (completedCount) {
            completedCount.textContent = completedNum;
        }

    } catch (err) {
        console.warn(
            "All tasks fetch error:",
            err
        );
    }
}


const priorityRank = {
    "high": 1,
    "medium": 2,
    "low": 3
};

async function getDeadlines() {
    try {
        const response = await fetch(`${API_BASE_URL}/tasks/all`, { headers: getHeaders() });
        const tasks = await response.json();
        const deadlineGrid = document.getElementById("deadlineGrid");
        if (!deadlineGrid) return;

        // Filter pending tasks with valid deadlines
        const validTasks = tasks.filter(t => 
            t.deadline && 
            t.deadline.toLowerCase() !== "no deadline" && 
            t.deadline.trim() !== "" &&
            t.status !== "Completed"
        );

        // Sort strictly by Priority: High (1) -> Medium (2) -> Low (3)
        validTasks.sort((a, b) => {
            const pA = priorityRank[(a.priority || "medium").toLowerCase()] || 99;
            const pB = priorityRank[(b.priority || "medium").toLowerCase()] || 99;
            return pA - pB;
        });

        deadlineGrid.innerHTML = "";

        if (validTasks.length === 0) {
            deadlineGrid.innerHTML = `<div class="empty-deadlines">✦ No upcoming deadlines detected. Add a new task or analyze an email to extract deadlines!</div>`;
            return;
        }

        validTasks.forEach(task => {
            const priority = (task.priority || "medium").toLowerCase();
            const cardClass = priority === "high" ? "high-priority" : priority === "medium" ? "medium-priority" : "low-priority";
            const tagClass = priority === "high" ? "red" : priority === "medium" ? "amber" : "green";

            const card = document.createElement("div");
            card.className = `deadline-card ${cardClass}`;
            card.innerHTML = `
                <div class="deadline-card-top">
                    <span class="date-tag">◷ ${task.deadline}</span>
                    <span class="tag ${tagClass}">${task.priority} Priority</span>
                </div>
                <strong>${task.task}</strong>
                <p>${task.summary || "Extracted from email inbox"}</p>
            `;
            deadlineGrid.appendChild(card);
        });
    } catch (err) {
        console.warn("Deadlines fetch error:", err);
    }
}

getAllTasks();
getDeadlines();

// New Task Modal Logic
const newTaskModal = document.getElementById("newTaskModal");
const openNewTaskBtn = document.getElementById("openNewTaskModal");
const closeNewTaskBtn = document.getElementById("closeNewTaskModal");
const cancelNewTaskBtn = document.getElementById("cancelNewTaskModal");
const newTaskForm = document.getElementById("newTaskForm");

function toggleModal(show) {
    if (newTaskModal) {
        newTaskModal.classList.toggle("active", show);
    }
}

if (openNewTaskBtn) openNewTaskBtn.addEventListener("click", () => toggleModal(true));
if (closeNewTaskBtn) closeNewTaskBtn.addEventListener("click", () => toggleModal(false));
if (cancelNewTaskBtn) cancelNewTaskBtn.addEventListener("click", () => toggleModal(false));

if (newTaskModal) {
    newTaskModal.addEventListener("click", (e) => {
        if (e.target === newTaskModal) toggleModal(false);
    });
}

if (newTaskForm) {
    newTaskForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const taskTitle = document.getElementById("taskTitleInput").value.trim();
        const taskDeadline = document.getElementById("taskDeadlineInput").value.trim();
        const taskPriority = document.getElementById("taskPriorityInput").value;

        if (!taskTitle || !taskDeadline) return;

        try {
            await fetch(`${API_BASE_URL}/save_task`, {
                method: "POST",
                headers: getHeaders(),
                body: JSON.stringify({
                    summary: taskTitle,
                    task: taskTitle,
                    deadline: taskDeadline,
                    priority: taskPriority
                })
            });

            newTaskForm.reset();
            toggleModal(false);
            getAllTasks();
            pendingTasksCount();
            getPriorities();
            getTaskCount();
            getDeadlines();
        } catch (err) {
            console.error("Error creating task:", err);
        }
    });
}

const urgentCountEl = document.getElementById("urgent-emails");
async function updateUrgentCount() {
    try {
        const response = await fetch(`${API_BASE_URL}/tasks/urgent`);
        urgentCountEl.textContent = await response.text();
    } catch (err) {
        console.error("Error updating urgent count:", err);
    }
}
updateUrgentCount();
setInterval(updateUrgentCount, 2000); 


const connectGmailBtn = document.getElementById("connectGmailBtn");

if (connectGmailBtn) {
    connectGmailBtn.addEventListener("click", () => {
        window.location.href = `${API_BASE_URL}/auth/google/login`;
    });
}