const chatForm = document.getElementById("chatForm");
const requestInput = document.getElementById("requestInput");
const userIdInput = document.getElementById("userIdInput");
const submitButton = document.getElementById("submitButton");
const chatWindow = document.getElementById("chatWindow");
const refreshButton = document.getElementById("refreshButton");
const tasksList = document.getElementById("tasksList");
const eventsList = document.getElementById("eventsList");
const notesList = document.getElementById("notesList");
const panelToggle = document.getElementById("panelToggle");
const appShell = document.querySelector(".app-shell");
const taskCount = document.getElementById("taskCount");
const eventCount = document.getElementById("eventCount");
const noteCount = document.getElementById("noteCount");
const runCount = document.getElementById("runCount");

document.querySelectorAll(".prompt-chip").forEach((button) => {
  button.addEventListener("click", () => {
    requestInput.value = button.dataset.prompt || "";
    requestInput.focus();
  });
});

refreshButton.addEventListener("click", () => {
  loadDashboard();
});

panelToggle.addEventListener("click", () => {
  const collapsed = appShell.classList.toggle("panel-collapsed");
  panelToggle.textContent = collapsed ? "Show panel" : "Hide panel";
  panelToggle.setAttribute("aria-expanded", String(!collapsed));
});

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const request = requestInput.value.trim();
  const userId = userIdInput.value.trim() || "demo-user";
  if (!request) return;

  appendUserMessage(request);
  requestInput.value = "";
  submitButton.disabled = true;
  submitButton.textContent = "Working...";

  try {
    const response = await fetch("/workflows/run", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        user_id: userId,
        request,
      }),
    });

    if (!response.ok) {
      let message = `Request failed with ${response.status}`;
      try {
        const errorPayload = await response.json();
        if (errorPayload.detail) {
          message = errorPayload.detail;
        }
      } catch (error) {
      }
      throw new Error(message);
    }

    const payload = await response.json();
    appendAssistantMessage(payload);
    await loadDashboard();
  } catch (error) {
    appendAssistantError(error.message);
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "Send";
  }
});

function appendUserMessage(text) {
  const template = document.getElementById("userMessageTemplate");
  const node = template.content.firstElementChild.cloneNode(true);
  node.querySelector(".bubble").textContent = text;
  chatWindow.appendChild(node);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function appendAssistantMessage(payload) {
  const template = document.getElementById("assistantMessageTemplate");
  const node = template.content.firstElementChild.cloneNode(true);
  const content = node.querySelector(".message-content");

  const summary = document.createElement("p");
  summary.textContent = payload.assistant_message || "Workflow completed.";
  content.appendChild(summary);

  const planCard = document.createElement("div");
  planCard.className = "result-card";
  planCard.innerHTML = `
    <strong>Execution summary</strong>
    <div class="mono">Run #${payload.workflow_run_id} | ${payload.status}</div>
    <p>${payload.plan.summary}</p>
  `;
  content.appendChild(planCard);

  if (Array.isArray(payload.plan.steps) && payload.plan.steps.length > 0) {
    const searchOnly =
      payload.plan.steps.length === 1 &&
      ["search_web", "search", "lookup"].includes(payload.plan.steps[0].action);

    if (searchOnly) {
      chatWindow.appendChild(node);
      chatWindow.scrollTop = chatWindow.scrollHeight;
      return;
    }

    const stepsWrapper = document.createElement("div");
    stepsWrapper.className = "result-grid";
    payload.plan.steps.forEach((step, index) => {
      const card = document.createElement("div");
      card.className = "result-card";
      card.innerHTML = `
        <strong>Step ${index + 1}</strong>
        <div class="mono">${step.agent} -> ${step.tool}</div>
        <p>${step.action}</p>
      `;
      stepsWrapper.appendChild(card);
    });
    content.appendChild(stepsWrapper);
  }

  if (Array.isArray(payload.results?.tool_results) && payload.results.tool_results.length > 0) {
    const toolWrapper = document.createElement("div");
    toolWrapper.className = "result-grid";
    payload.results.tool_results.forEach((item) => {
      const card = document.createElement("div");
      card.className = "result-card";
      const title = document.createElement("strong");
      title.textContent = item.tool;
      const meta = document.createElement("div");
      meta.className = "mono";
      meta.textContent = item.action;
      card.appendChild(title);
      card.appendChild(meta);
      card.appendChild(renderToolResponse(item.response));
      toolWrapper.appendChild(card);
    });
    content.appendChild(toolWrapper);
  }

  chatWindow.appendChild(node);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function appendAssistantError(message) {
  const template = document.getElementById("assistantMessageTemplate");
  const node = template.content.firstElementChild.cloneNode(true);
  const content = node.querySelector(".message-content");
  const error = document.createElement("p");
  error.textContent = `I hit an error while running the workflow: ${message}`;
  content.appendChild(error);
  chatWindow.appendChild(node);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

async function loadDashboard() {
  const [tasks, events, notes, runs] = await Promise.all([
    fetchJson("/data/tasks"),
    fetchJson("/data/events"),
    fetchJson("/data/notes"),
    fetchJson("/data/workflow_runs"),
  ]);

  taskCount.textContent = tasks.length;
  eventCount.textContent = events.length;
  noteCount.textContent = notes.length;
  runCount.textContent = runs.length;

  renderList(tasksList, tasks, (item) => ({
    title: item.title,
    body: item.status + (item.due_date ? ` | due ${item.due_date}` : ""),
  }));
  renderList(eventsList, events, (item) => ({
    title: item.title,
    body: `${item.start_time} -> ${item.end_time}`,
  }));
  renderList(notesList, notes, (item) => ({
    title: item.title,
    body: item.content,
  }));
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) return [];
  return response.json();
}

function renderList(container, items, formatter) {
  container.innerHTML = "";
  if (!items.length) {
    const item = document.createElement("li");
    item.className = "empty-state";
    item.textContent = "No records yet.";
    container.appendChild(item);
    return;
  }

  items.slice(0, 4).forEach((entry) => {
    const formatted = formatter(entry);
    const item = document.createElement("li");
    item.innerHTML = `<strong>${formatted.title}</strong><span>${formatted.body}</span>`;
    container.appendChild(item);
  });
}

function renderToolResponse(response) {
  if (response?.events && Array.isArray(response.events)) {
    return renderTable(response.events, [
      ["title", "Title"],
      ["start_time", "Start"],
      ["end_time", "End"],
      ["created_at", "Created"],
    ]);
  }

  if (response?.tasks && Array.isArray(response.tasks)) {
    return renderTable(response.tasks, [
      ["title", "Title"],
      ["status", "Status"],
      ["due_date", "Due"],
      ["created_at", "Created"],
    ]);
  }

  if (response?.notes && Array.isArray(response.notes)) {
    return renderTable(response.notes, [
      ["title", "Title"],
      ["content", "Content"],
      ["created_at", "Created"],
    ]);
  }

  if (response?.results && Array.isArray(response.results)) {
    return renderTable(response.results, [
      ["title", "Title"],
      ["snippet", "Snippet"],
      ["source", "Source"],
      ["url", "URL"],
    ]);
  }

  const text = document.createElement("p");
  text.textContent = JSON.stringify(response);
  return text;
}

function renderTable(rows, columns) {
  const wrapper = document.createElement("div");
  wrapper.className = "table-shell";

  const table = document.createElement("table");
  table.className = "data-table";

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  columns.forEach(([, label]) => {
    const th = document.createElement("th");
    th.textContent = label;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);

  const tbody = document.createElement("tbody");
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    columns.forEach(([key]) => {
      const td = document.createElement("td");
      td.textContent = formatCellValue(row[key]);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });

  table.appendChild(thead);
  table.appendChild(tbody);
  wrapper.appendChild(table);
  return wrapper;
}

function formatCellValue(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  const text = String(value);
  return text.length > 80 ? `${text.slice(0, 77)}...` : text;
}

loadDashboard();
