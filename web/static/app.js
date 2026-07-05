const $ = (id) => document.getElementById(id);

const workflowSteps = [
  { id: "init", number: 1, title: "Initialize Workspace", description: "Create workspace and prepare requirements", status: "pending", active: false },
  { id: "requirements", number: 2, title: "Requirements Dialogue", description: "Extract Terraform requirements through dialogue with the model", status: "pending", active: false },
  { id: "generate", number: 3, title: "Generate Terraform", description: "Let the model output Terraform files", status: "pending", active: false },
  { id: "policy", number: 4, title: "Policy Check", description: "Audit whether Terraform conforms to security policy", status: "pending", active: false },
  { id: "showplan", number: 5, title: "Generate Plan", description: "Execute show-plan and generate summary", status: "pending", active: false },
  { id: "review", number: 6, title: "Review Plan", description: "Let the model audit the plan summary", status: "pending", active: false },
  { id: "apply", number: 7, title: "Execute Apply", description: "Execute Terraform apply after approval", status: "pending", active: false },
];

function workspace() {
  return $("workspace").value.trim() || "demo-web";
}

function logOutput(data) {
  const text = typeof data === "string" ? data : JSON.stringify(data, null, 2);
  $("output").textContent = text;
}

function appendChat(role, content, style = "skill") {
  const el = document.createElement("div");
  el.className = `msg ${style}`;
  el.innerHTML = `<div class="role">${escapeHtml(role)}</div><div>${escapeHtml(content).replace(/\n/g, "<br>")}</div>`;
  $("chatLog").appendChild(el);
  $("chatLog").scrollTop = $("chatLog").scrollHeight;
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderWorkflow() {
  const container = $("workflow");
  container.innerHTML = "";
  workflowSteps.forEach((step) => {
    const el = document.createElement("div");
    el.className = `workflow-step ${step.status}${step.active ? " active" : ""}`;
    el.dataset.step = step.id;
    el.innerHTML = `
      <div class="node-icon">${step.number}</div>
      <div>
        <div class="node-title">${escapeHtml(step.title)}</div>
        <div class="node-desc">${escapeHtml(step.description)}</div>
      </div>
    `;
    el.onclick = () => setActiveStep(step.id);
    container.appendChild(el);
  });
}

function setActiveStep(stepId) {
  workflowSteps.forEach((step) => {
    step.active = step.id === stepId;
    if (step.active && step.status === "pending") {
      step.status = "active";
    }
  });
  const current = workflowSteps.find((step) => step.active);
  $("currentStep").textContent = current ? current.title : "Waiting for action";
  renderWorkflow();
}

function setStepStatus(stepId, status) {
  const step = workflowSteps.find((item) => item.id === stepId);
  if (!step) return;
  step.status = status;
  step.active = false;
  renderWorkflow();
}

async function api(path, body = null, method = "POST") {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body !== null) opts.body = JSON.stringify(body);
  const resp = await fetch(path, opts);
  const text = await resp.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { raw: text }; }
  if (!resp.ok) {
    throw new Error(data.detail || text || `HTTP ${resp.status}`);
  }
  return data;
}

async function refreshHealth() {
  try {
    const data = await api("/api/health", null, "GET");
    $("healthBox").textContent = `status: ${data.status}\nLLM: ${data.llm_base_url}\nmodel: ${data.llm_model}\nALLOW_APPLY: ${data.allow_apply}\nPython tools: ${data.python_tools?.enabled || 0}/${data.python_tools?.registered || 0}\nHuawei AK: ${data.huaweicloud_auth?.HW_ACCESS_KEY || "unknown"}\nHuawei SK: ${data.huaweicloud_auth?.HW_SECRET_KEY || "unknown"}`;
  } catch (e) {
    $("healthBox").textContent = `health failed: ${e.message}`;
  }
}

async function loadExamples() {
  const data = await api("/api/examples", null, "GET");
  const sel = $("exampleSelect");
  sel.innerHTML = "";
  data.examples.forEach((name) => {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    sel.appendChild(opt);
  });
}

async function loadRequirements() {
  const data = await api(`/api/workspace/${encodeURIComponent(workspace())}/requirements`, null, "GET");
  $("requirementsEditor").value = JSON.stringify(data.requirements, null, 2);
  return data.requirements;
}

async function initWorkspace(fromExample) {
  setActiveStep("init");
  appendChat("System", "Starting to initialize workspace.", "skill");
  const body = { workspace: workspace(), force: true };
  if (fromExample) body.from_example = $("exampleSelect").value;
  const data = await api("/api/workspace/init", body);
  $("requirementsEditor").value = JSON.stringify(data.requirements, null, 2);
  appendChat("Audit", "Workspace initialized, requirements written.", "audit");
  logOutput(data);
  setStepStatus("init", "success");
}

async function sendChat() {
  const message = $("messageInput").value.trim();
  if (!message) return;
  setActiveStep("requirements");
  appendChat("User", message, "user");
  $("messageInput").value = "";
  const data = await api("/api/chat", { workspace: workspace(), message });
  $("requirementsEditor").value = JSON.stringify(data.requirements, null, 2);
  let reply = "Requirements updated.";
  if (data.next_question) reply += `\n\nNext question: ${data.next_question}`;
  if (data.missing_fields && data.missing_fields.length) reply += `\n\nMissing fields:\n${JSON.stringify(data.missing_fields, null, 2)}`;
  if (data.risk_notes && data.risk_notes.length) reply += `\n\nRisk notes:\n${data.risk_notes.join("\n")}`;
  appendChat("Skill", reply, "skill");
  logOutput(data);
  setStepStatus("requirements", "success");
}

async function saveRequirements() {
  let requirements;
  try { requirements = JSON.parse($("requirementsEditor").value); }
  catch (e) {
    appendChat("Error", `requirements JSON format error: ${e.message}`, "error");
    return;
  }
  const data = await api("/api/workspace/requirements", { workspace: workspace(), requirements });
  appendChat("System", "Requirements saved.", "skill");
  logOutput(data);
}

async function generateTerraform() {
  setActiveStep("generate");
  appendChat("System", "Starting to generate Terraform files.", "skill");
  const data = await api("/api/generate", { workspace: workspace() });
  appendChat("Skill", `Terraform generated, files written: ${data.written.join(", ")}`);
  if (data.assumptions?.length) appendChat("Audit", `Model assumptions:\n${data.assumptions.join("\n")}`, "audit");
  if (data.risk_notes?.length) appendChat("Audit", `Risk notes:\n${data.risk_notes.join("\n")}`, "audit");
  logOutput(data);
  setStepStatus("generate", "success");
}

async function policyCheck() {
  setActiveStep("policy");
  appendChat("System", "Starting policy check.", "skill");
  const data = await api("/api/policy-check", { workspace: workspace() });
  if (!data.ok) {
    appendChat("Audit", `Policy check found ${data.violations.length} violations:\n${data.violations.join("\n")}`, "audit");
    setStepStatus("policy", "error");
  } else {
    appendChat("Audit", "Policy check passed, no violations found. Please proceed to the next step.", "audit");
    setStepStatus("policy", "success");
  }
  logOutput(data);
}

async function showPlan() {
  setActiveStep("showplan");
  appendChat("System", "Starting to generate Terraform plan and extract summary.", "skill");
  const data = await api("/api/terraform", { workspace: workspace(), command: "show-plan" });
  if (data.ok) {
    appendChat("Skill", "Plan generated and successfully parsed, summary written to plan_summary.json.", "skill");
    appendChat("Audit", `Plan Summary:\n${JSON.stringify(data.summary, null, 2)}`, "audit");
    setStepStatus("showplan", "success");
  } else {
    appendChat("Error", `Failed to generate Plan: ${JSON.stringify(data.result || data)}`, "error");
    setStepStatus("showplan", "error");
  }
  logOutput(data);
}

async function reviewPlan() {
  setActiveStep("review");
  appendChat("System", "Starting to audit the plan summary with the model.", "skill");
  const data = await api("/api/review-plan", { workspace: workspace() });
  appendChat("Audit", data.review || "No audit results returned.", "audit");
  logOutput(data);
  setStepStatus("review", "success");
}

async function applyPlan() {
  setActiveStep("apply");
  appendChat("System", "Attempting to execute apply operation.", "skill");
  try {
    const data = await api("/api/terraform", { workspace: workspace(), command: "apply", approval: $("approval").value });
    appendChat("Audit", "Apply executed successfully.", "audit");
    logOutput(data);
    setStepStatus("apply", "success");
  } catch (e) {
    appendChat("Error", `Apply blocked: ${e.message}`, "error");
    logOutput(e.message);
    setStepStatus("apply", "error");
  }
}

function bind() {
  $("initEmptyBtn").onclick = () => initWorkspace(false).catch((e) => appendChat("Error", e.message, "error"));
  $("initExampleBtn").onclick = () => initWorkspace(true).catch((e) => appendChat("Error", e.message, "error"));
  $("sendBtn").onclick = () => sendChat().catch((e) => appendChat("Error", e.message, "error"));
  $("reloadReqBtn").onclick = () => loadRequirements().catch((e) => appendChat("Error", e.message, "error"));
  $("saveReqBtn").onclick = () => saveRequirements().catch((e) => appendChat("Error", e.message, "error"));
  $("generateBtn").onclick = () => generateTerraform().catch((e) => appendChat("Error", e.message, "error"));
  $("policyBtn").onclick = () => policyCheck().catch((e) => appendChat("Error", e.message, "error"));
  $("showPlanBtn").onclick = () => showPlan().catch((e) => appendChat("Error", e.message, "error"));
  $("reviewPlanBtn").onclick = () => reviewPlan().catch((e) => appendChat("Error", e.message, "error"));
  $("applyBtn").onclick = () => applyPlan().catch((e) => appendChat("Error", e.message, "error"));
}

(async function main() {
  renderWorkflow();
  bind();
  await refreshHealth();
  await loadExamples();
  try { await loadRequirements(); } catch (e) { appendChat("Error", e.message, "error"); }
})();
