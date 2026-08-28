# 📧 InboxAI — Intelligent Email Management with AI Agents

## 📌 Overview

**InboxAI** is an AI-powered email management system designed to help users understand and organize their emails automatically.

Instead of manually reading every email and deciding what needs to be done, InboxAI uses **Generative AI and multiple specialized AI agents** to analyze emails, identify important information, determine priority, and extract actionable tasks.

The main goal of the project is to demonstrate how **Agentic AI** can be used to automate a real-world workflow.

---

## 🎯 Problem

People receive many emails every day, and important information can easily be missed.

For example, an email may contain:

* An important task
* A deadline
* An urgent request
* Information that requires a response
* A low-priority notification

Normally, the user has to read the email, understand its meaning, decide how important it is, and manually create a task.

**InboxAI automates this process.**

---

# 💡 Solution

InboxAI processes an email through a workflow of specialized AI agents.

The system can:

1. Understand the email.
2. Generate a short summary.
3. Identify whether the email requires an action.
4. Determine its priority.
5. Extract the task.
6. Extract the deadline.
7. Store the resulting task.
8. Return the structured information to the user.

The system is designed as an **Agentic AI workflow**, where each agent has a specific responsibility.

---

# 🏗️ System Architecture

```text
                     ┌───────────────────┐
                     │       Email       │
                     └─────────┬─────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    Orchestrator     │
                    │        Agent        │
                    └──────────┬──────────┘
                               │
             ┌─────────────────┼─────────────────┐
             │                 │                 │
             ▼                 ▼                 ▼
      ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
      │    Email    │   │  Priority   │   │    Task     │
      │ Understanding│   │    Agent    │   │    Agent    │
      │    Agent    │   │             │   │             │
      └──────┬──────┘   └──────┬──────┘   └──────┬──────┘
             │                 │                 │
             └─────────────────┼─────────────────┘
                               │
                               ▼
                     ┌──────────────────┐
                     │     FastAPI      │
                     │      Backend     │
                     └────────┬─────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │      Redis       │
                     │   Task Storage   │
                     └──────────────────┘
```

---

# 🤖 AI Agents

## 1. Email Understanding Agent

The first agent is responsible for understanding the content of the email.

It analyzes:

* The main purpose of the email
* Important information
* Required actions
* Possible deadlines

It then produces a structured analysis that can be used by the other agents.

### Example

Input:

```text
Subject: AI Project Report

Please submit the final AI project report by August 16.
Make sure to include the project documentation and GitHub link.
```

The agent understands that the email contains an actionable request with a deadline.

---

## 2. Priority Agent

The priority agent determines how important the email is.

It classifies emails into:

```text
HIGH
MEDIUM
LOW
```

For example, an email containing:

```text
"Please submit the report by tomorrow."
```

would most likely be classified as:

```text
HIGH
```

The agent considers the urgency and context of the email when determining its priority.

---

## 3. Task Extraction Agent

The task agent converts the actionable information from the email into a structured task.

For example:

```json
{
    "task": "Submit the AI project report",
    "deadline": "2026-08-16",
    "priority": "High"
}
```

This makes the information easier for the backend and frontend to process.

---

## 4. Orchestrator Agent

The **Orchestrator** coordinates the complete workflow.

Instead of the user interacting with every agent separately, the orchestrator manages the sequence of operations.

The workflow is approximately:

```text
Email
  ↓
Orchestrator
  ↓
Email Understanding
  ↓
Priority Detection
  ↓
Task Extraction
  ↓
Create / Save Task
  ↓
Redis
```

This architecture makes it possible to add additional agents in the future without redesigning the entire application.

---

# 🔄 Complete Example

### Input Email

```text
Subject: AI Project Report Submission

Hi,

Please submit the final AI project report by August 16.

The report should contain the project documentation
and the GitHub repository link.

Best regards
```

### Step 1 — Understanding

The AI identifies:

```text
Purpose:
Submit an AI project report.

Action required:
Yes.

Deadline:
August 16.
```

### Step 2 — Priority

The priority agent determines:

```text
Priority: HIGH
```

because the email contains a specific submission deadline.

### Step 3 — Task Extraction

The task agent generates:

```json
{
    "task": "Submit the AI project report",
    "deadline": "2026-08-16",
    "priority": "High"
}
```

### Step 4 — Backend

The structured task is sent to the backend through an API.

```text
AI Agents
    ↓
FastAPI
    ↓
Redis
```

### Final Result

```text
┌────────────────────────────────────┐
│ 🔴 HIGH PRIORITY                   │
│                                    │
│ Submit the AI project report       │
│                                    │
│ Deadline: August 16, 2026          │
└────────────────────────────────────┘
```

---

# 🧠 Why Multiple Agents?

A single LLM could perform the entire task, but InboxAI uses specialized agents to separate responsibilities.

For example:

```text
Email Agent
     ↓
"What does this email mean?"

Priority Agent
     ↓
"How important is it?"

Task Agent
     ↓
"What should the user do?"

Orchestrator
     ↓
"How should the complete workflow run?"
```

This approach makes the application easier to:

* Maintain
* Debug
* Extend
* Test
* Improve

New agents can also be added later for features such as sentiment analysis, email categorization, automatic replies, or calendar integration.

---

# 🛠️ Technologies Used

## Generative AI & Agentic AI

* **Python**
* **Google ADK**
* **LangChain**
* **Google Gemini**
* **Groq**
* **LLMs**
* **Prompt Engineering**
* **AI Agents**
* **Multi-Agent Systems**
* **Tool / Function Calling**
* **Structured Outputs**
* **Pydantic**

## Backend

* **FastAPI**
* **REST APIs**
* **Requests**

## Database / Storage

* **Redis**

## Development

* **Git**
* **GitHub**
* **VS Code**
* **Environment Variables / `.env`**

---

# 📂 Project Structure

```text
InboxAI/
│
├── agents/
│   ├── understand_mails.py
│   ├── priority_agent.py
│   ├── task_from_mails.py
│   └── orchestrator.py
│
├── backend/
│   └── server.py
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
│
├── .env
├── requirements.txt
└── README.md
```

---

# 🔌 Backend Communication

The AI agents communicate with the backend through APIs.

For example, a task can be sent to FastAPI:

```http
POST /save_task
```

with structured data such as:

```json
{
    "task": "Submit the AI project report",
    "deadline": "2026-08-16",
    "priority": "High"
}
```

The backend then stores the information in Redis.

```text
Agent
  ↓
HTTP Request
  ↓
FastAPI
  ↓
Redis
```

This separation between the **AI layer** and **backend layer** makes the architecture cleaner and easier to maintain.

---

# ⚙️ Installation

## 1. Clone the repository

```bash
git clone https://github.com/Hendmostafa44/InBoxAi.git
cd InBoxAi
```

## 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on Windows:

```bash
.venv\Scripts\activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Configure environment variables

Create a `.env` file:

```env
GOOGLE_API_KEY=your_google_api_key
GROQ_API_KEY=your_groq_api_key

REDIS_HOST=your_redis_host
REDIS_PORT=your_redis_port
REDIS_PASSWORD=your_redis_password
```

**Do not upload `.env` or API keys to GitHub.**

---

# ▶️ Running the Backend

Start the FastAPI server:

```bash
uvicorn server:app --reload --port 8007
```

The backend will then be available locally.

The frontend communicates with the FastAPI backend to send and retrieve information.

---

# 🔐 Security

API keys and database credentials are stored using environment variables.

The `.env` file should be added to `.gitignore`:

```text
.env
.venv/
__pycache__/
```

---

# 🚀 Future Improvements

The project can be extended with:

* Gmail integration
* Outlook integration
* Automatic email fetching
* Automatic reminders
* Calendar integration
* User authentication
* Email embeddings
* Semantic search
* RAG
* Email classification
* Automatic email replies
* Task dashboard
* Cloud deployment

---

# 📚 What This Project Demonstrates

InboxAI demonstrates practical experience in **Generative AI and AI Engineering**, including:

* Designing AI agent workflows
* Building multi-agent systems
* Integrating LLMs into applications
* Using Google ADK and LangChain
* Working with structured LLM outputs
* Implementing tool/function calling
* Building REST APIs with FastAPI
* Connecting AI applications to databases
* Managing communication between AI agents and backend services
* Developing an end-to-end AI application

---

# 👩‍💻 Author

**Hend Mostafa**

Computer & AI Student

GitHub:
https://github.com/Hendmostafa44/InBoxAi

---

## ⭐ Conclusion

InboxAI is more than an email summarization tool. It is an **Agentic AI application** that demonstrates how multiple specialized AI agents can collaborate to transform unstructured email content into useful, structured tasks.

The project combines **Generative AI, AI Agents, backend APIs, and database storage** into one end-to-end application.

