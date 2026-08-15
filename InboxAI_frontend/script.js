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
