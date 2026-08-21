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
      card.style.display = card.dataset.search.includes(q) ? "flex" : "none";
    });
  });
}

const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const chatMessages = document.getElementById("chatMessages");

function addMessage(text, type) {
  const row = document.createElement("div");
  row.className = `message ${type}`;
  row.innerHTML = type === "ai"
    ? `<div class="chat-avatar">✦</div><div><span class="message-name">InboxAI</span><div class="bubble">${text}</div></div>`
    : `<div><div class="bubble">${text}</div></div>`;
  chatMessages.appendChild(row);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function getTaskCount() {
    const response = await fetch("http://localhost:8007/tasks/count");
    const data = await response.json();

    document.getElementById("email-count").textContent = data.count;
}

getTaskCount();
setInterval(getTaskCount, 1000);










// function demoReply(q) {
//   const text = q.toLowerCase();
//   if (text.includes("urgent") || text.includes("attention")) {
//     return "You have <strong>3 urgent emails</strong>: the Google Careers internship email, the AI project submission, and the team meeting invitation.";
//   }
//   if (text.includes("tomorrow") || text.includes("deadline")) {
//     return "You have <strong>2 time-sensitive items</strong>: submit the AI project report tomorrow and reply to the internship email by tomorrow.";
//   }
//   return "I found the key items in your inbox. You currently have <strong>3 urgent emails</strong>, <strong>5 pending tasks</strong>, and <strong>4 upcoming deadlines</strong>.";
// }

chatForm.addEventListener("submit", async e => {
    e.preventDefault();

    const value = chatInput.value.trim();
    if (!value) return;

    addMessage(value, "user");
    chatInput.value = "";

    try {
        const response = await fetch("http://localhost:8007/analyze", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: value
            })
        });

        const data = await response.json();

        addMessage(data.response, "ai");

    } catch (error) {
        console.error("Error:", error);
        addMessage("Sorry, something went wrong.", "ai");
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
    const response = await fetch("http://localhost:8007/tasks/priorities");
    const tasks = await response.json();

    const items = document.querySelectorAll(".priority-item");

    tasks.slice(0, 3).forEach((task, index) => {

        const item = items[index];

        const title = item.querySelector("strong");
        const description = item.querySelector("p");
        const dot = item.querySelector(".priority-dot");
        const tag = item.querySelector(".tag");

        title.textContent = task.task;
        description.textContent = `Deadline: ${task.deadline}`;

        tag.textContent = task.priority;

        // تحديث الـpriority
        dot.className = `priority-dot ${task.priority.toLowerCase()}`;

        const priority = task.priority.toLowerCase();

      tag.className = `tag ${
        priority === "high"
          ? "red"
          : priority === "medium"
          ? "amber"
          : "green"
      }`;
    });
}

getPriorities();

setInterval(getPriorities, 1000);



async function pendingTasksCount() {
    const response = await fetch("http://localhost:8007/tasks/pending/count");
    const data = await response.json();
    document.getElementById("pending_tasks").textContent = data.count;
}

pendingTasksCount();

setInterval(pendingTasksCount, 2000);



async function getAllTasks() {
    const response = await fetch("http://localhost:8007/tasks/all");

    const tasks = await response.json();

    console.log("TASKS:", tasks);

    const todoList = document.getElementById("todo-list");
    const todoCount = document.getElementById("todo-count");

    todoList.innerHTML = "";
    todoCount.textContent = tasks.length;

    tasks.forEach(task => {

        const priority = task.priority.toLowerCase();

        let tagClass;

        if (priority === "high") {
            tagClass = "red";
        } else if (priority === "medium") {
            tagClass = "amber";
        } else {
            tagClass = "green";
        }

        const taskElement = document.createElement("div");

        taskElement.className = "task";

        taskElement.innerHTML = `
            <input type="checkbox" ${task.status === "Completed" ? "checked" : ""}>

            <div>
                <strong>${task.task}</strong>
                <p>Deadline · ${task.deadline}</p>
            </div>

            <span class="tag ${tagClass}">
                ${task.priority}
            </span>
        `;

        todoList.appendChild(taskElement);

        const checkbox = taskElement.querySelector("input");

        checkbox.addEventListener("change", async () => {

            const status = checkbox.checked
                ? "Completed"
                : "pending";

            await fetch(
                `http://localhost:8007/tasks/status?task_name=${encodeURIComponent(task.task)}&status=${status}`,
                {
                    method: "PUT"
                }
            );

            getAllTasks();
            pendingTasksCount();
        });
    });
}


getAllTasks();

